"""
数据库操作模块 — JSON 文件存储的读写与原子更新

从 __main__.py 提取，提供：
- load_db / save_db / atomic_update
- _read_json / _write_json_atomic（内部实现）
- 内存缓存：减少频繁的全量 JSON 文件读写
"""

import os
import json
from datetime import datetime
from typing import Callable

from file_lock import get_db_lock
from scheduler_log import init_logging


_logger = None
_data_dir = None

# === 内存缓存 ===
_db_cache = {}  # {filepath: (data, mtime)}
_cache_enabled = True


def enable_cache(enabled: bool = True):
    """启用/禁用数据库缓存"""
    global _cache_enabled
    _cache_enabled = enabled


def invalidate_cache(filename: str = None):
    """使缓存失效。filename=None 则清空所有缓存"""
    if filename is None:
        _db_cache.clear()
    else:
        filepath = _db_path(filename)
        _db_cache.pop(filepath, None)


def _get_logger():
    global _logger
    if _logger is None:
        _logger = init_logging()
    return _logger


def _get_data_dir() -> str:
    """获取数据目录（懒初始化）"""
    global _data_dir
    if _data_dir is None:
        env_dir = os.getenv("CREWAI_DATA_DIR")
        if env_dir:
            _data_dir = env_dir
        else:
            src_dir = os.path.dirname(os.path.abspath(__file__))
            _data_dir = os.path.join(src_dir, "data")
            if not os.path.exists(_data_dir):
                os.makedirs(_data_dir, exist_ok=True)
    return _data_dir


def set_data_dir(data_dir: str):
    """设置数据目录（由 __main__.py 调用以同步 DATA_DIR）"""
    global _data_dir
    _data_dir = data_dir


def _db_path(filename: str) -> str:
    """获取数据库文件的完整路径"""
    return os.path.join(_get_data_dir(), filename)


def _read_json(filepath: str) -> dict:
    """读取 JSON 文件，损坏时自动备份并返回空 dict"""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print("[ERROR] 数据库文件损坏: %s, 错误: %s" % (os.path.basename(filepath), e))
            _get_logger().warning("数据库文件损坏: %s, 错误: %s" % (os.path.basename(filepath), e))
            backup_name = filepath + ".backup." + datetime.now().strftime('%Y%m%d_%H%M%S')
            try:
                os.rename(filepath, backup_name)
                print("[INFO] 已备份损坏文件到: %s" % os.path.basename(backup_name))
            except Exception as ex:
                _get_logger().warning("备份损坏文件失败: %s" % ex)
            return {}
        except Exception as e:
            print("[ERROR] 加载数据库失败: %s, 错误: %s" % (os.path.basename(filepath), e))
            _get_logger().warning("加载数据库失败: %s, 错误: %s" % (os.path.basename(filepath), e))
            return {}
    return {}


def _write_json_atomic(filepath: str, data: dict):
    """原子写入 JSON：先写 .tmp 再 os.replace，防止写入中断导致数据损坏"""
    temp_file = filepath + ".tmp"
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        if os.path.exists(filepath):
            backup = filepath + ".backup"
            try:
                if os.path.exists(backup):
                    os.remove(backup)
                os.rename(filepath, backup)
            except Exception as ex:
                _get_logger().warning("备份旧文件失败: %s" % ex)
        os.replace(temp_file, filepath)
    except Exception as e:
        print("[ERROR] 保存数据库失败: %s, 错误: %s" % (os.path.basename(filepath), e))
        _get_logger().error("保存数据库失败: %s, 错误: %s" % (os.path.basename(filepath), e))
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass
        raise


def load_db(filename: str) -> dict:
    """加载数据库（带文件锁，支持内存缓存）"""
    filepath = _db_path(filename)

    # 检查缓存：如果文件未修改，直接返回缓存
    if _cache_enabled and filepath in _db_cache:
        try:
            current_mtime = os.path.getmtime(filepath)
            cached_data, cached_mtime = _db_cache[filepath]
            if current_mtime == cached_mtime:
                return cached_data
        except OSError:
            pass

    lock = get_db_lock(filepath)
    with lock.acquire():
        data = _read_json(filepath)

    # 更新缓存
    if _cache_enabled:
        try:
            mtime = os.path.getmtime(filepath)
            _db_cache[filepath] = (data, mtime)
        except OSError:
            pass

    return data


def save_db(filename: str, data: dict):
    """保存数据库（带文件锁，原子写入，自动更新缓存）"""
    filepath = _db_path(filename)
    lock = get_db_lock(filepath)
    with lock.acquire():
        _write_json_atomic(filepath, data)

    # 更新缓存（而非失效，避免下次 load 再读文件）
    if _cache_enabled:
        try:
            mtime = os.path.getmtime(filepath)
            _db_cache[filepath] = (data, mtime)
        except OSError:
            pass


def atomic_update(filename: str, update_fn: Callable):
    """
    原子更新数据库：读取 → 调用 update_fn → 写回。
    
    如果 update_fn 抛出异常，不写入（数据保持原状）。
    """
    filepath = _db_path(filename)
    lock = get_db_lock(filepath)
    with lock.acquire():
        data = _read_json(filepath)
        try:
            updated = update_fn(data)
        except Exception as e:
            _get_logger().warning("atomic_update 的 update_fn 执行失败: %s, 数据未写入" % e)
            raise
        _write_json_atomic(filepath, updated)
    return updated


# 数据库文件名常量
PROJECTS_DB = "projects.json"
WORKFLOW_DB = "workflow.json"


def compact_workflow_db(keep_result_chars: int = 200) -> dict:
    """
    压缩 workflow.json：对已完成/失败的工作流，截断阶段 result 到指定长度，
    清理 history 和 sub_tasks，显著减小文件体积。

    Args:
        keep_result_chars: 保留的 result 字符数（0 = 完全删除 result）

    Returns:
        {"compacted": int, "freed_chars": int, "remaining_size": int}
    """
    from scheduler_log import init_logging
    logger = init_logging()

    data = load_db(WORKFLOW_DB)
    wf_all = data.get("workflows", {})
    compacted = 0
    freed_chars = 0

    for name, wf in wf_all.items():
        status = wf.get("status", "unknown")
        # 只压缩已完成/失败的工作流（in_progress/paused/interrupted 保留完整数据）
        if status not in ("completed", "failed"):
            continue

        for sid, sd in wf.get("stages", {}).items():
            # 截断 result
            result = sd.get("result", "")
            if result and len(result) > keep_result_chars:
                freed_chars += len(result) - keep_result_chars
                if keep_result_chars > 0:
                    sd["result"] = result[:keep_result_chars] + "\n...(已压缩，原长度 %d 字符)" % len(result)
                else:
                    sd["result"] = "(已压缩，原长度 %d 字符)" % len(result)

            # 清理 history（回退历史，完成后不再需要）
            hist = sd.get("history", [])
            if hist:
                freed_chars += sum(len(h.get("result", "") or "") for h in hist)
                sd["history"] = [{"attempt": h.get("attempt", i+1),
                                  "duration_seconds": h.get("duration_seconds")}
                                 for i, h in enumerate(hist)]  # 只保留元数据

            # 清理 sub_tasks
            st = sd.get("sub_tasks", [])
            if st:
                sd["sub_tasks"] = [{"id": t.get("id"), "name": t.get("name"),
                                    "status": t.get("status"),
                                    "files_written": t.get("files_written", 0),
                                    "duration_seconds": t.get("duration_seconds", 0)}
                                   for t in st]  # 去掉 _files 等大字段

        compacted += 1

    if compacted > 0:
        save_db(WORKFLOW_DB, data)
        # 计算压缩后大小
        import json as _json
        remaining_size = len(_json.dumps(data, ensure_ascii=False))
        logger.info("workflow.json 压缩完成: %d 个项目, 释放 %d 字符, 剩余约 %dKB" %
                     (compacted, freed_chars, remaining_size // 1024))
    else:
        remaining_size = 0

    return {"compacted": compacted, "freed_chars": freed_chars, "remaining_size": remaining_size}
