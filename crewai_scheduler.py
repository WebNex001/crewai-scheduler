"""
CrewAI Scheduler 核心 - AI 任务执行引擎（v3.0 工作流版）

v3.0 功能:
- 配置管理（从 config.json 读取）
- 工作流多阶段执行（execute_stage）
- 上下文传递（前一阶段输出 → 下一阶段输入）
- 角色切换（不同阶段注入不同 System Prompt）
- 思考模式按阶段开关（thinking parameter）
- 回退机制（代码审查/测试不通过 → 回到开发阶段）
- Debug 详细日志输出到 Debug/ 目录
"""

import json
import time
import logging
import re
import os
import threading
from typing import Dict, Optional, Any, List
from datetime import datetime


# ==================== Function Calling 工具定义 ====================

WRITE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "创建项目文件，将代码写入指定路径。每完成一个文件的编写就立即调用此工具写入，不要等所有文件都写完再一起调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件相对路径，如 src/main.py, config/app.json"
                },
                "content": {
                    "type": "string",
                    "description": "文件的完整内容，包含所有代码和注释"
                }
            },
            "required": ["path", "content"]
        }
    }
}


class CrewAIScheduler:
    """AI 任务调度器 — 核心引擎（v3.0 工作流模式）"""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "config.json"
        )
        self.config = {}
        self.logger = None
        self._debug_logger = None

        # 加载配置
        self.load_config()
        # 初始化日志
        self._setup_logging()
        # 初始化 Debug 日志
        self._setup_debug_log()

    # ==================== 日志 ====================

    def _setup_logging(self):
        """设置标准日志"""
        self.logger = logging.getLogger("CrewAIScheduler")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(name)s] %(levelname)s %(message)s"
            ))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    # Debug 日志文件大小上限默认值（字节），可通过 config.json → system.debug_log_max_mb 覆盖
    _DEFAULT_DEBUG_LOG_MAX_SIZE = 50 * 1024 * 1024  # 50MB

    def _get_debug_log_max_size(self) -> int:
        """从配置读取 Debug 日志大小上限（字节），默认 50MB"""
        max_mb = self.config.get("system", {}).get("debug_log_max_mb", 50)
        return int(max_mb) * 1024 * 1024

    def _setup_debug_log(self):
        """设置 Debug 日志（写入 Debug/ 目录，自动轮转旧日志）"""
        if not self.is_debug():
            return

        debug_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Debug")
        if not os.path.exists(debug_dir):
            os.makedirs(debug_dir, exist_ok=True)

        # 日志轮转：清理超过 7 天的旧日志
        try:
            now = time.time()
            for f in os.listdir(debug_dir):
                fp = os.path.join(debug_dir, f)
                if f.startswith("debug_") and f.endswith(".log") and os.path.isfile(fp):
                    # 按时间轮转
                    if now - os.path.getmtime(fp) > 7 * 86400:
                        try:
                            os.remove(fp)
                        except OSError:
                            pass
                    # 按大小轮转：超大文件也清理
                    elif os.path.getsize(fp) > self._get_debug_log_max_size():
                        try:
                            os.remove(fp)
                        except OSError:
                            pass
        except Exception:
            pass

        self._debug_logger = logging.getLogger("CrewAIScheduler.Debug")
        if not self._debug_logger.handlers:
            log_file = os.path.join(debug_dir, f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
            fh = logging.FileHandler(log_file, encoding='utf-8')
            fh.setFormatter(logging.Formatter(
                "%(asctime)s.%(msecs)03d | %(levelname)-7s | %(message)s",
                datefmt="%H:%M:%S"
            ))
            self._debug_logger.addHandler(fh)
            self._debug_logger.setLevel(logging.DEBUG)
            self._debug_file = log_file
            self.debug(f"Debug 日志初始化完成 → {log_file}")

    def debug(self, msg: str):
        """输出 Debug 日志（仅 debug 模式下生效）"""
        if self._debug_logger:
            self._debug_logger.debug(msg)

    def get_debug_log_path(self) -> Optional[str]:
        """获取当前 Debug 日志文件路径"""
        return getattr(self, '_debug_file', None)

    # ==================== 配置管理 ====================

    def load_config(self):
        """加载配置文件"""
        default_config = {
            "api": {
                "openai_api_key": "",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 128000,
                "context_window": 200000,
                "timeout": 300,
            },
            "system": {
                "debug": False,
                "log_level": "INFO",
                "monitoring_interval": 30,
            },
            "workflow": {},
        }

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"[WARN] 配置文件加载失败: {e}, 使用默认配置")
                self.config = default_config
        else:
            self.config = default_config
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

        # 配置校验
        self._validate_config()

    def _validate_config(self):
        """校验配置关键字段，不合法时给出警告而非中断"""
        warnings = []
        api = self.config.get("api", {})
        if not api.get("base_url"):
            warnings.append("api.base_url 为空")
        if not api.get("model"):
            warnings.append("api.model 为空")
        timeout = api.get("timeout")
        if timeout is not None and (not isinstance(timeout, (int, float)) or timeout <= 0):
            warnings.append("api.timeout 应为正数")
        max_tokens = api.get("max_tokens")
        if max_tokens is not None and (not isinstance(max_tokens, int) or max_tokens <= 0):
            warnings.append("api.max_tokens 应为正整数")
        temperature = api.get("temperature")
        if temperature is not None and (not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2):
            warnings.append("api.temperature 应在 0-2 之间")

        # 工作流校验
        for dept_name, dept_cfg in self.config.get("workflow", {}).items():
            if not isinstance(dept_cfg, dict):
                continue
            stages = dept_cfg.get("stages", [])
            if stages and not isinstance(stages, list):
                warnings.append(f"workflow.{dept_name}.stages 应为数组")
            for i, s in enumerate(stages if isinstance(stages, list) else []):
                if not s.get("id"):
                    warnings.append(f"workflow.{dept_name}.stages[{i}] 缺少 id")
                if not s.get("name"):
                    warnings.append(f"workflow.{dept_name}.stages[{i}] 缺少 name")

        for w in warnings:
            print(f"[WARN] 配置校验: {w}")

    def save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")

    # ==================== API 配置查询 ====================

    def _get_api_key(self) -> str:
        """获取 API Key（优先 config.json 用户配置，其次环境变量 OPENAI_API_KEY）"""
        config_key = self.config.get("api", {}).get("openai_api_key", "")
        if config_key:
            return config_key
        return os.environ.get("OPENAI_API_KEY", "")

    def _get_base_url(self) -> str:
        """获取 Base URL（仅从 config.json 读取）"""
        return self.config.get("api", {}).get("base_url", "")

    def get_max_retries(self, department: str) -> int:
        """获取部门最大回退次数（默认 3）"""
        workflow_cfg = self.config.get("workflow", {})
        dept_workflow = workflow_cfg.get(department, {})
        return dept_workflow.get("max_retries", 3)

    def get_api_timeout(self) -> int:
        """获取 API 超时时间（秒），默认 300"""
        return self.config.get("api", {}).get("timeout", 300)

    def is_debug(self) -> bool:
        """是否开启调试模式"""
        return self.config.get("system", {}).get("debug", False)

    # ==================== 工作流配置查询 ====================

    def get_workflow_stages(self, department: str) -> List[Dict]:
        """获取指定部门的工作流阶段定义"""
        workflow_cfg = self.config.get("workflow", {})
        dept_workflow = workflow_cfg.get(department, {})
        return dept_workflow.get("stages", [])

    def is_workflow_enabled(self, department: str) -> bool:
        """检查部门是否启用了工作流模式"""
        workflow_cfg = self.config.get("workflow", {})
        dept_workflow = workflow_cfg.get(department, {})
        return dept_workflow.get("enabled", False)

    def get_retry_target(self, department: str, stage_id: str) -> Optional[str]:
        """获取阶段被打回后的回退目标阶段 ID"""
        workflow_cfg = self.config.get("workflow", {})
        dept_workflow = workflow_cfg.get(department, {})
        retry_rules = dept_workflow.get("retry_on_reject", {})
        return retry_rules.get(stage_id)

    # ==================== 上下文压缩 ====================

    # 安全系数：估算值超过此比例的 context_window 就触发压缩
    _CONTEXT_SAFETY_RATIO = 0.85
    # 预留给模型输出的 token 比例
    _OUTPUT_RESERVE_RATIO = 0.3
    # 压缩结果缓存：{cache_key: compressed_dict}
    _compress_cache: Dict[str, Dict[str, str]] = {}
    _compress_cache_key: str = ""  # 当前 workflow 的缓存 key

    def _estimate_tokens(self, text: str) -> int:
        """
        估算文本的 token 数（不依赖 tiktoken）。
        
        策略：区分中文和英文字符，中文约 1.5 字符/token，英文约 4 字符/token。
        混合文本按实际字符比例加权计算。
        """
        if not text:
            return 0
        # 统计中文字符数（CJK 统一汉字范围）
        cjk_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3000' <= c <= '\u303f')
        total_chars = len(text)
        non_cjk_chars = total_chars - cjk_count
        # 中文: ~1.5 字符/token, 英文/其他: ~4 字符/token
        estimated = int(cjk_count / 1.5 + non_cjk_chars / 4)
        return max(estimated, 1)

    def _get_context_window(self) -> int:
        """获取模型的 context_window（token 数）"""
        return self.config.get("api", {}).get("context_window", 200000)

    def _get_compress_cache_key(self, previous_outputs: Dict[str, str]) -> str:
        """生成压缩缓存的 key（基于各阶段输出的长度哈希）"""
        import hashlib
        parts = []
        for sid in sorted(previous_outputs.keys()):
            text = previous_outputs[sid]
            parts.append(f"{sid}:{len(text)}:{hashlib.md5(text.encode()).hexdigest()[:8]}")
        return "|".join(parts)

    def _extract_structured_summary(self, text: str, stage_id: str) -> str:
        """
        从阶段输出中提取结构化摘要，保留关键信息（文件列表、API、数据库表、模块定义等），
        只压缩描述性文字。

        策略：按 markdown 标题分段，保留结构化内容（代码块、列表、表格），
        压缩描述性段落。
        """
        if not text or len(text) <= 800:
            return text

        lines = text.split('\n')
        sections = []  # [(title, content_lines), ...]
        current_title = ""
        current_lines = []

        for line in lines:
            if line.strip().startswith('#'):
                # 遇到新标题，保存上一节
                if current_title or current_lines:
                    sections.append((current_title, current_lines))
                current_title = line.strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        # 最后一节
        if current_title or current_lines:
            sections.append((current_title, current_lines))

        # 按阶段类型决定保留策略
        keep_all_sections = set()
        if stage_id == "detailed_design":
            # 详细设计：保留模块定义、文件列表、API 定义、数据库表结构
            keep_all_sections = {
                "模块", "文件", "目录", "api", "接口", "数据库", "表结构",
                "module", "file", "json", "结构", "schema",
            }
        elif stage_id == "architecture":
            # 架构设计：保留技术栈、模块划分、核心接口
            keep_all_sections = {
                "技术栈", "模块划分", "接口", "架构", "层次", "组件",
                "tech", "stack", "module", "component",
            }
        elif stage_id == "requirements":
            # 需求分析：保留功能列表、用例、非功能需求
            keep_all_sections = {
                "功能", "用例", "需求", "用户故事", "非功能",
                "feature", "requirement", "use case",
            }

        result_parts = []
        for title, content_lines in sections:
            content_text = '\n'.join(content_lines)

            # 判断是否为结构化内容（代码块、表格、列表密集的段落）
            has_code_block = '```' in content_text
            has_table = '|' in content_text and '-|' in content_text
            list_density = sum(1 for l in content_lines if l.strip().startswith(('- ', '* ', '1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')))
            is_list_heavy = list_density >= 3

            # 判断标题是否匹配需要完整保留的关键词
            title_match_keep = any(kw in title.lower() for kw in keep_all_sections)

            if title_match_keep or has_code_block or has_table or is_list_heavy:
                # 结构化内容：完整保留
                result_parts.append(content_text)
            else:
                # 描述性段落：保留标题 + 前几行摘要
                summary_lines = content_lines[:6]
                # 保留标题行
                if len(content_lines) > 6:
                    summary_lines.append("...(描述性内容已压缩)")
                result_parts.append('\n'.join(summary_lines))

        result = '\n'.join(result_parts)

        return result

    def _compress_previous_outputs(
        self, previous_outputs: Dict[str, str], available_tokens: int
    ) -> Dict[str, str]:
        """
        按优先级压缩前置阶段输出，使总 token 数不超过 available_tokens。

        压缩策略：提取结构化摘要（保留文件列表、API、数据库等关键信息），
        而非粗暴截断。按阶段优先级逐步压缩。带缓存避免重复压缩。
        """
        if not previous_outputs:
            return previous_outputs

        # 计算当前总 token
        total_tokens = sum(self._estimate_tokens(v) for v in previous_outputs.values())

        if total_tokens <= available_tokens:
            return previous_outputs

        # 检查压缩缓存
        cache_key = self._get_compress_cache_key(previous_outputs)
        if cache_key in self._compress_cache:
            cached = self._compress_cache[cache_key]
            cached_tokens = sum(self._estimate_tokens(v) for v in cached.values())
            if cached_tokens <= available_tokens:
                self.debug(f"[CONTEXT] 使用压缩缓存 (cache_key={cache_key[:40]}..., tokens={cached_tokens})")
                return cached

        compressed = dict(previous_outputs)

        # === 按阶段差异化压缩策略 ===
        # 阶段压缩优先级：越早的阶段越先压缩，development 代码最后压缩
        # 但压缩力度因阶段类型不同而异
        priority_order = [
            "requirements", "deployment",
            "delivery", "testing", "code_review",
            "architecture", "detailed_design", "development",
        ]

        # 第一轮：提取结构化摘要（保留关键信息，压缩描述）
        for sid in priority_order:
            if sid not in compressed:
                continue
            text = compressed[sid]
            if len(text) > 800:
                compressed[sid] = self._extract_structured_summary(text, sid)
                total_tokens = sum(self._estimate_tokens(v) for v in compressed.values())
                if total_tokens <= available_tokens:
                    self._compress_cache[cache_key] = compressed
                    return compressed

        # 第二轮：进一步压缩摘要（只保留标题 + 关键结构）
        for sid in priority_order:
            if sid not in compressed:
                continue
            text = compressed[sid]
            if len(text) > 400:
                # 保留所有标题行 + 代码块 + 列表项
                lines = text.split('\n')
                keep_lines = []
                for line in lines:
                    stripped = line.strip()
                    is_heading = stripped.startswith('#')
                    is_list = stripped.startswith(('- ', '* ')) or (len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in '.)')
                    is_code = stripped.startswith('```')
                    is_table = '|' in stripped
                    if is_heading or is_list or is_code or is_table:
                        keep_lines.append(line)
                if keep_lines:
                    compressed[sid] = '\n'.join(keep_lines) + "\n...(描述已深度压缩)"
                else:
                    compressed[sid] = text[:400] + "\n...(已压缩)"
                total_tokens = sum(self._estimate_tokens(v) for v in compressed.values())
                if total_tokens <= available_tokens:
                    self._compress_cache[cache_key] = compressed
                    return compressed

        # 第三轮：极端情况，丢弃最早阶段
        for sid in priority_order:
            if sid not in compressed:
                continue
            compressed[sid] = "（该阶段输出因上下文超限已省略）"
            total_tokens = sum(self._estimate_tokens(v) for v in compressed.values())
            if total_tokens <= available_tokens:
                self._compress_cache[cache_key] = compressed
                return compressed

        return compressed

    def is_context_overflow_error(self, error_msg: str) -> bool:
        """判断错误是否为上下文超限错误"""
        msg_lower = error_msg.lower()
        return any(kw in msg_lower for kw in [
            "context_length_exceeded",
            "maximum context length",
            "too many tokens",
            "token limit",
            "context window",
            "input is too long",
            "超过上下文",
            "上下文长度",
            "token 数量超限",
        ])

    # ==================== 辅助方法 ====================

    def _build_prompts(self, stage, project_desc, stage_context, previous_outputs):
        """构建 System/User Prompt（公共逻辑，供 execute_stage 和 execute_stage_with_tools 复用）"""
        stage_id = stage["id"]
        stage_name = stage["name"]
        agent = stage["agent"]
        agent_role = stage.get("agent_role", "专业 AI 助手")

        system_prompt_template = stage.get("system_prompt", "你是一个专业的 AI 助手。")
        
        # 收集模块化开发配置，用于替换 prompt 中的占位符
        modular_cfg = self.config.get("workflow", {})
        # 兼容多部门配置：查找当前 stage 所在的部门
        for dept_name, dept_cfg in modular_cfg.items():
            if isinstance(dept_cfg, dict) and "stages" in dept_cfg:
                stages_list = dept_cfg.get("stages", [])
                if any(s.get("id") == stage_id for s in stages_list):
                    modular_cfg = dept_cfg.get("modular_development", {})
                    break
        else:
            modular_cfg = {}
        
        max_files_per_module = modular_cfg.get("max_files_per_module", 8)
        max_modules = modular_cfg.get("max_modules", 10)
        min_files_to_split = modular_cfg.get("min_files_to_split", 10)
        
        # 替换占位符
        format_vars = {
            "agent_role": agent_role,
            "max_files_per_module": max_files_per_module,
            "max_modules": max_modules,
            "min_files_to_split": min_files_to_split,
        }
        try:
            system_prompt = system_prompt_template.format(**format_vars)
        except (KeyError, ValueError):
            # system_prompt 中包含 { } 等非占位符花括号（如 JSON 示例），逐个安全替换
            system_prompt = system_prompt_template
            for key, val in format_vars.items():
                system_prompt = system_prompt.replace("{%s}" % key, str(val))

        # === 上下文超限自动压缩 ===
        context_window = self._get_context_window()
        max_input_tokens = int(context_window * self._CONTEXT_SAFETY_RATIO)
        # 预留给模型输出的 token
        output_reserve = int(context_window * self._OUTPUT_RESERVE_RATIO)
        available_for_input = max_input_tokens - output_reserve

        # 估算 system_prompt + project_desc 的 token
        base_tokens = self._estimate_tokens(system_prompt) + self._estimate_tokens(project_desc)
        if stage_context:
            base_tokens += self._estimate_tokens(stage_context)

        # 前置阶段输出可用的 token 预算
        available_for_prev = max(available_for_input - base_tokens, 2000)  # 至少留 2000 token

        if previous_outputs:
            previous_outputs = self._compress_previous_outputs(previous_outputs, available_for_prev)

        user_content_parts = []
        user_content_parts.append(f"## 项目信息\n{project_desc}")

        if previous_outputs:
            context_lines = ["\n## 前置阶段成果（上下文）"]
            for prev_sid, prev_result in previous_outputs.items():
                context_lines.append(f"\n### {prev_sid} 阶段输出:\n{prev_result}")
            user_content_parts.append("\n".join(context_lines))

        if stage_context:
            user_content_parts.append(f"\n## 当前阶段任务\n{stage_context}")

        user_content_parts.append(
            f"\n## 你的角色\n你是 {agent}，负责「{stage_name}」阶段的工作。"
            "\n请基于以上信息，完成该阶段的任务并输出完整结果。"
        )

        user_content = "\n".join(user_content_parts)

        # Debug: 上下文压缩日志
        total_est_tokens = self._estimate_tokens(system_prompt) + self._estimate_tokens(user_content)
        self.debug(f"[CONTEXT] 估算总输入 tokens≈{total_est_tokens}, context_window={context_window}, "
                   f"安全上限={max_input_tokens}, 预留输出={output_reserve}")

        return system_prompt, user_content

    def _check_rejection(self, stage_id, result_text):
        """检查审查类阶段是否打回（公共逻辑）"""
        rejected = False
        reject_reason = ""
        if stage_id in ("code_review", "testing"):
            result_lower = result_text.lower()
            if "打回" in result_text or "reject" in result_lower or "不通过" in result_text:
                rejected = True
                if "原因" in result_text:
                    reason_start = result_text.find("原因") + 2
                    reason_end = result_text.find("\n", reason_start)
                    if reason_end > reason_start:
                        reject_reason = result_text[reason_start:reason_end].strip()
                    else:
                        reject_reason = result_text[reason_start:reason_start+200].strip()
                elif "建议" in result_text:
                    suggest_start = result_text.find("建议") + 2
                    reject_reason = result_text[suggest_start:suggest_start+200].strip()
        return rejected, reject_reason

    def _make_error_result(self, stage_id, stage_name, agent, msg, duration,
                           files_written=None):
        """构建统一的错误返回值（消除 6 处重复）"""
        return {
            "success": False,
            "result": msg,
            "stage_id": stage_id,
            "stage_name": stage_name,
            "agent": agent,
            "duration_seconds": round(duration, 2),
            "rejected": False,
            "reject_reason": "",
            "files_written": files_written or [],
        }

    # ==================== 核心执行引擎 (v3.0) ====================

    def execute_stage(
        self,
        stage: Dict,
        project_desc: str,
        stage_context: str = "",
        previous_outputs: Dict[str, str] = None,
        project_id: str = "",
    ) -> Dict[str, Any]:
        """
        执行工作流的单个阶段（核心方法）

        Args:
            stage: 阶段定义字典（id/name/agent/system_prompt/agent_role/thinking）
            project_desc: 项目原始描述
            stage_context: 当前阶段的特定输入
            previous_outputs: 前置所有阶段的输出 {stage_id: result_text}
            project_id: 项目 ID（用于 Debug 日志命名）

        Returns:
            {
                "success": bool,
                "result": str,
                "stage_id": str,
                "stage_name": str,
                "agent": str,
                "duration_seconds": float,
                "rejected": bool,
                "reject_reason": str
            }
        """
        import openai

        start_time = time.time()
        stage_id = stage["id"]
        stage_name = stage["name"]
        agent = stage["agent"]
        agent_role = stage.get("agent_role", "专业 AI 助手")
        thinking_enabled = stage.get("thinking", True)

        api_key = self._get_api_key()
        base_url = self._get_base_url()
        model = self.config.get("api", {}).get("model", "gpt-4")
        api_config = self.config.get("api", {})

        if not api_key:
            return self._make_error_result(stage_id, stage_name, agent, "错误: API 密钥未配置", 0)

        # 构建 Prompt（公共方法）
        system_prompt, user_content = self._build_prompts(
            stage, project_desc, stage_context, previous_outputs
        )

        # === Debug 日志：请求详情 ===
        self.debug(f"{'='*60}")
        self.debug(f"[STAGE START] {stage_id} | {stage_name} | Agent: {agent}")
        self.debug(f"[PROJECT] {project_id or 'N/A'}")
        self.debug(f"[THINKING] {'ON' if thinking_enabled else 'OFF'}")
        self.debug(f"[MODEL] {model} | timeout={self.get_api_timeout()}s | max_tokens={api_config.get('max_tokens', 128000)} | temp={api_config.get('temperature', 0.7)}")
        self.debug(f"[SYSTEM PROMPT] ({len(system_prompt)} chars):\n{system_prompt}")
        self.debug(f"[USER PROMPT] ({len(user_content)} chars):\n{user_content}")

        self.logger.info(f"[工作流] 开始执行阶段 [{stage_id}] {stage_name} (负责人: {agent}, 思考模式: {'开启' if thinking_enabled else '关闭'})")
        self.logger.info(f"[工作流] HTTP Request: POST {base_url}/chat/completions")

        try:
            client = openai.OpenAI(api_key=api_key, base_url=base_url)
            api_timeout = self.get_api_timeout()

            extra_body = {
                "thinking": {
                    "type": "enabled" if thinking_enabled else "disabled"
                }
            }

            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                temperature=api_config.get("temperature", 0.7),
                max_tokens=api_config.get("max_tokens", 128000),
                timeout=api_timeout,
                extra_body=extra_body,
            )

            result = response.choices[0].message.content
            duration = time.time() - start_time

            # Debug: 响应详情
            usage = getattr(response, 'usage', None)
            usage_info = ""
            token_usage = {}
            if usage:
                usage_info = f" | prompt={usage.prompt_tokens} completion={usage.completion_tokens} total={usage.total_tokens}"
                token_usage = {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                }
                # 记录 token 用量到监控
                try:
                    from usage_monitor import get_monitor
                    monitor = get_monitor()
                    if not monitor.data["summary"].get("token_usage"):
                        monitor.data["summary"]["token_usage"] = {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                        }
                    tu = monitor.data["summary"]["token_usage"]
                    tu["prompt_tokens"] += usage.prompt_tokens
                    tu["completion_tokens"] += usage.completion_tokens
                    tu["total_tokens"] += usage.total_tokens
                except Exception:
                    pass
            self.debug(f"[RESPONSE] status=OK | duration={duration:.1f}s | output={len(result)} chars{usage_info}")
            self.debug(f"[OUTPUT PREVIEW] ({min(len(result), 500)} chars):\n{result[:500]}{'...' if len(result) > 500 else ''}")

            # 检查是否为审查类阶段，解析是否打回
            rejected, reject_reason = self._check_rejection(stage_id, result)

            if rejected:
                self.debug(f"[REJECTED] reason={reject_reason}")

            self.logger.info(
                f"[工作流] 阶段 [{stage_id}] {stage_name} 完成 "
                f"(耗时 {duration:.1f}s, 输出 {len(result)} 字符)"
                + (f", ⚠️ 已打回" if rejected else ", ✅ 通过")
            )

            return {
                "success": True,
                "result": result,
                "stage_id": stage_id,
                "stage_name": stage_name,
                "agent": agent,
                "duration_seconds": round(duration, 2),
                "rejected": rejected,
                "reject_reason": reject_reason,
                "token_usage": token_usage,
            }

        except ImportError:
            duration = time.time() - start_time
            self.debug(f"[ERROR] ImportError: openai 包未安装")
            return self._make_error_result(stage_id, stage_name, agent, "错误: openai 包未安装，请运行 pip install openai", duration)
        except Exception as e:
            duration = time.time() - start_time
            err_msg = str(e)
            self.debug(f"[ERROR] exception={type(e).__name__} | msg={err_msg} | duration={duration:.1f}s")
            self.logger.error(f"[工作流] 阶段 [{stage_id}] 执行异常: {e}")
            # 标记上下文超限错误，让 retry 模块知道不应简单重试
            error_result = self._make_error_result(stage_id, stage_name, agent, f"API 调用失败: {err_msg}", duration)
            if self.is_context_overflow_error(err_msg):
                error_result["context_overflow"] = True
                self.debug(f"[CONTEXT OVERFLOW] 上下文超限错误，需要压缩后重试")
            return error_result


    # ==================== Function Calling 执行引擎 (v3.1) ====================

    def execute_stage_with_tools(
        self,
        stage: Dict,
        project_desc: str,
        stage_context: str = "",
        previous_outputs: Dict[str, str] = None,
        project_id: str = "",
        tools: List[Dict] = None,
        on_tool_call = None,
        max_tool_rounds: int = 30,
    ) -> Dict[str, Any]:
        """
        执行工作流阶段（Function Calling 版）— 支持工具调用的多轮交互

        与 execute_stage 相比，此方法：
        - 传入 tools 参数让模型可以主动调用工具
        - 多轮对话：模型调用工具 → 返回结果 → 模型继续输出
        - 通过 on_tool_call 回调让调用方处理工具执行
        - 兼容 MiniMax M2 的 reasoning_split=True 格式

        Args:
            stage: 阶段定义字典
            project_desc: 项目原始描述
            stage_context: 当前阶段特定输入
            previous_outputs: 前置阶段输出
            project_id: 项目 ID
            tools: OpenAI function calling 工具定义列表
            on_tool_call: 回调函数 (tool_name, tool_args) -> result_str
            max_tool_rounds: 最大工具调用轮数（防止死循环）

        Returns:
            与 execute_stage 相同的返回格式，额外包含 "files_written" 字段
        """
        import openai

        start_time = time.time()
        stage_id = stage["id"]
        stage_name = stage["name"]
        agent = stage["agent"]
        thinking_enabled = stage.get("thinking", True)

        api_key = self._get_api_key()
        base_url = self._get_base_url()
        model = self.config.get("api", {}).get("model", "gpt-4")
        api_config = self.config.get("api", {})
        api_timeout = self.get_api_timeout()

        if not api_key:
            return self._make_error_result(stage_id, stage_name, agent, "错误: API 密钥未配置", 0)

        # 构建 Prompt
        system_prompt, user_content = self._build_prompts(
            stage, project_desc, stage_context, previous_outputs
        )

        # === Debug 日志 ===
        self.debug(f"{'='*60}")
        self.debug(f"[STAGE+TOOLS START] {stage_id} | {stage_name} | Agent: {agent}")
        self.debug(f"[PROJECT] {project_id or 'N/A'}")
        self.debug(f"[THINKING] {'ON' if thinking_enabled else 'OFF'}")
        self.debug(f"[TOOLS] {len(tools) if tools else 0} tools available")
        self.debug(f"[MODEL] {model} | timeout={api_timeout}s")
        self.debug(f"[SYSTEM PROMPT] ({len(system_prompt)} chars):\n{system_prompt}")
        self.debug(f"[USER PROMPT] ({len(user_content)} chars):\n{user_content}")

        self.logger.info(f"[工作流+Tools] 开始执行阶段 [{stage_id}] {stage_name} (负责人: {agent})")
        self.logger.info(f"[工作流+Tools] HTTP Request: POST {base_url}/chat/completions")

        # 收集所有文件写入记录
        files_written = []

        try:
            client = openai.OpenAI(api_key=api_key, base_url=base_url)

            # 构建初始消息列表
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]

            extra_body = {
                "thinking": {
                    "type": "enabled" if thinking_enabled else "disabled"
                },
                "reasoning_split": True,  # MiniMax M2 推荐：思考内容独立字段
            }

            # 收集所有文本输出
            all_text_parts = []
            tool_round = 0

            while tool_round < max_tool_rounds:
                tool_round += 1

                self.debug(f"[TOOL ROUND {tool_round}] Sending request...")

                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    tools=tools if tools else None,
                    temperature=api_config.get("temperature", 0.7),
                    max_tokens=api_config.get("max_tokens", 128000),
                    timeout=api_timeout,
                    extra_body=extra_body,
                )

                response_message = response.choices[0].message

                # 收集文本输出
                if response_message.content:
                    all_text_parts.append(response_message.content)

                # Debug: 思考过程
                reasoning_details = getattr(response_message, 'reasoning_details', None)
                if reasoning_details:
                    for rd in reasoning_details:
                        if isinstance(rd, dict) and 'text' in rd:
                            self.debug(f"[THINKING] {rd['text'][:200]}...")

                # === 处理工具调用 ===
                if response_message.tool_calls:
                    # ⚠️ 关键：完整回传 assistant 消息（含 reasoning_details），保持思维链连续
                    messages.append(response_message)

                    for tool_call in response_message.tool_calls:
                        func_name = tool_call.function.name
                        try:
                            func_args = json.loads(tool_call.function.arguments)
                        except json.JSONDecodeError:
                            func_args = {}

                        self.debug(f"[TOOL CALL] {func_name}({json.dumps(func_args, ensure_ascii=False)[:200]})")
                        self.logger.info(f"[工作流+Tools] 工具调用: {func_name}")

                        # 执行工具
                        tool_result_str = ""
                        if func_name == "write_file" and on_tool_call:
                            file_path = func_args.get("path", "")
                            file_content = func_args.get("content", "")
                            tool_result_str = on_tool_call(func_name, func_args)
                            files_written.append({
                                "path": file_path,
                                "size": len(file_content),
                            })
                            self.debug(f"[FILE WRITTEN] {file_path} ({len(file_content)} chars)")
                            self.logger.info(f"[工作流+Tools] 文件写入: {file_path} ({len(file_content)} chars)")
                        elif on_tool_call:
                            tool_result_str = on_tool_call(func_name, func_args)
                        else:
                            tool_result_str = "OK"

                        # 回传工具结果
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result_str,
                        })

                    # 继续循环，让模型决定下一步
                    continue

                # 没有工具调用，且 finish_reason 不是 tool_calls → 结束
                break

            duration = time.time() - start_time
            full_result = "\n".join(all_text_parts)

            # Debug: 响应摘要
            usage = getattr(response, 'usage', None)
            usage_info = ""
            token_usage = {}
            if usage:
                usage_info = f" | prompt={usage.prompt_tokens} completion={usage.completion_tokens} total={usage.total_tokens}"
                token_usage = {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                }
                # 记录 token 用量到监控
                try:
                    from usage_monitor import get_monitor
                    monitor = get_monitor()
                    if not monitor.data["summary"].get("token_usage"):
                        monitor.data["summary"]["token_usage"] = {
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "total_tokens": 0,
                        }
                    tu = monitor.data["summary"]["token_usage"]
                    tu["prompt_tokens"] += usage.prompt_tokens
                    tu["completion_tokens"] += usage.completion_tokens
                    tu["total_tokens"] += usage.total_tokens
                except Exception:
                    pass

            self.debug(f"[RESPONSE] status=OK | duration={duration:.1f}s | output={len(full_result)} chars | tools_rounds={tool_round} | files={len(files_written)}{usage_info}")

            # 检查打回
            rejected, reject_reason = self._check_rejection(stage_id, full_result)

            if rejected:
                self.debug(f"[REJECTED] reason={reject_reason}")

            self.logger.info(
                f"[工作流+Tools] 阶段 [{stage_id}] {stage_name} 完成 "
                f"(耗时 {duration:.1f}s, 输出 {len(full_result)} 字符, "
                f"写入 {len(files_written)} 个文件, {tool_round} 轮工具调用)"
                + (f", ⚠️ 已打回" if rejected else ", ✅ 通过")
            )

            return {
                "success": True,
                "result": full_result,
                "stage_id": stage_id,
                "stage_name": stage_name,
                "agent": agent,
                "duration_seconds": round(duration, 2),
                "rejected": rejected,
                "reject_reason": reject_reason,
                "files_written": files_written,
                "tool_rounds": tool_round,
                "token_usage": token_usage,
            }

        except ImportError:
            duration = time.time() - start_time
            return self._make_error_result(stage_id, stage_name, agent, "错误: openai 包未安装，请运行 pip install openai", duration)
        except Exception as e:
            duration = time.time() - start_time
            err_msg = str(e)
            self.debug(f"[ERROR] exception={type(e).__name__} | msg={err_msg} | duration={duration:.1f}s")
            self.logger.error(f"[工作流+Tools] 阶段 [{stage_id}] 执行异常: {e}")
            error_result = self._make_error_result(stage_id, stage_name, agent, f"API 调用失败: {err_msg}", duration, files_written)
            if self.is_context_overflow_error(err_msg):
                error_result["context_overflow"] = True
                self.debug(f"[CONTEXT OVERFLOW] 上下文超限错误，需要压缩后重试")
            return error_result


# ==================== 全局单例 ====================

_scheduler: Optional[CrewAIScheduler] = None
_scheduler_lock = threading.Lock()


def get_scheduler() -> CrewAIScheduler:
    """获取全局调度器实例（懒初始化单例，线程安全）"""
    global _scheduler
    if _scheduler is None:
        with _scheduler_lock:
            if _scheduler is None:
                _scheduler = CrewAIScheduler()
    return _scheduler


def reset_scheduler():
    """重置调度器实例（用于配置变更后重新加载）"""
    global _scheduler
    with _scheduler_lock:
        _scheduler = None
