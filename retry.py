"""
API 重试与退避策略模块

从 __main__.py 提取，提供：
- _call_with_retry: 带指数退避 + 随机抖动的重试包装器
- 上下文超限错误不重试（需要压缩后由调用方重新构建 prompt）
"""

import random
import time as _time
from typing import Dict, Any, Callable

# === 可调参数 ===
STAGE_DELAY_SECONDS = 15          # 阶段间延迟（秒）
MODULE_DELAY_SECONDS = 5          # 模块间延迟（秒）
MAX_API_RETRIES = 3               # API 调用最大重试次数
RATE_LIMIT_BACKOFF_BASE = 30      # 429 速率限制基础等待时间（秒）
MAX_JITTER_SECONDS = 5            # 退避抖动上限（秒）


def _call_with_retry(
    fn: Callable,
    max_retries: int = MAX_API_RETRIES,
    backoff_base: float = RATE_LIMIT_BACKOFF_BASE,
    is_rate_limited: Callable[[Dict], bool] = None,
) -> Dict[str, Any]:
    """
    带重试的 API 调用包装器（指数退避 + 随机抖动）。
    
    Args:
        fn: 无参调用函数，返回 result dict
        max_retries: 最大重试次数
        backoff_base: 基础退避时间（秒）
        is_rate_limited: 判断结果是否因速率限制失败的函数
    
    Returns:
        fn() 的返回值
    """
    _default_rate_check = lambda r: (
        "429" in str(r.get("result", ""))
        or "速率限制" in str(r.get("result", ""))
        or "rate limit" in str(r.get("result", "")).lower()
    )
    if is_rate_limited is None:
        is_rate_limited = _default_rate_check
    
    result = None
    for retry_idx in range(max_retries):
        result = fn()
        if result.get("success"):
            return result

        # 上下文超限错误：不重试，直接返回（调用方会压缩上下文后重试）
        if result.get("context_overflow"):
            return result

        if is_rate_limited(result) and retry_idx < max_retries - 1:
            # 指数退避 + 随机抖动：base * 2^n + jitter(0, MAX_JITTER)
            wait_time = backoff_base * (2 ** retry_idx) + random.uniform(0, MAX_JITTER_SECONDS)
            print("  [429] Rate limited, retry %d/%d after %.0fs..." % (retry_idx + 1, max_retries, wait_time))
            _time.sleep(wait_time)
        else:
            break
    return result


def _call_with_context_compress(
    fn: Callable,
    compress_fn: Callable[[], None],
    max_compress_rounds: int = 3,
    max_retries: int = MAX_API_RETRIES,
    backoff_base: float = RATE_LIMIT_BACKOFF_BASE,
) -> Dict[str, Any]:
    """
    带上下文压缩的重试包装器。
    
    当 API 返回上下文超限错误时，调用 compress_fn 压缩上下文，
    然后重试。最多压缩 max_compress_rounds 轮。
    
    Args:
        fn: 无参调用函数，返回 result dict
        compress_fn: 压缩上下文的函数（修改 previous_outputs 等外部状态）
        max_compress_rounds: 最大压缩轮数
        max_retries: 每轮压缩后的最大重试次数
        backoff_base: 基础退避时间
    
    Returns:
        fn() 的返回值
    """
    for compress_round in range(max_compress_rounds):
        result = _call_with_retry(fn, max_retries=max_retries, backoff_base=backoff_base)
        if result.get("success"):
            return result
        if not result.get("context_overflow"):
            return result  # 非上下文超限错误，直接返回

        # 上下文超限，尝试压缩
        if compress_round < max_compress_rounds - 1:
            print("  [CONTEXT] 上下文超限，第 %d 次压缩后重试..." % (compress_round + 1))
            compress_fn()
        else:
            print("  [CONTEXT] 已达最大压缩轮数 (%d)，放弃" % max_compress_rounds)

    return result
