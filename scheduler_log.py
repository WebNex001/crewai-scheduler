"""
统一日志工具 - 所有输出使用标准格式，支持文件和控制台双输出
"""

import sys
import os
from datetime import datetime
from typing import Optional, TextIO

# 日志级别
LOG_LEVELS = {
    "DEBUG": 0,
    "INFO": 1,
    "WARN": 2,
    "ERROR": 3,
    "SUCCESS": 3,  # 与 ERROR 同级，但用绿色标记
}

# ANSI 颜色码（Windows 终端支持）
COLORS = {
    "DEBUG": "\033[36m",     # 青色
    "INFO": "\033[37m",      # 白色
    "WARN": "\033[33m",      # 黄色
    "ERROR": "\033[31m",     # 红色
    "SUCCESS": "\033[32m",   # 绿色
    "RESET": "\033[0m",      # 重置
}


class SchedulerLogger:
    """CrewAI Scheduler 统一日志"""

    def __init__(
        self,
        name: str = "crewai-scheduler",
        log_file: Optional[str] = None,
        console: bool = True,
        min_level: str = "INFO"
    ):
        self.name = name
        self.console = console
        self.min_level = LOG_LEVELS.get(min_level, 1)
        self.log_file_path = log_file
        self._file_handle: Optional[TextIO] = None

        # 打开日志文件
        if log_file:
            try:
                log_dir = os.path.dirname(log_file)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                self._file_handle = open(log_file, 'a', encoding='utf-8')
            except Exception as e:
                print(f"[ERROR] 无法打开日志文件 {log_file}: {e}")

    def _format(self, level: str, message: str) -> str:
        """格式化日志消息"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return f"[{timestamp}] [{level:>7}] [{self.name}] {message}"

    def _colorize(self, level: str, text: str) -> str:
        """添加颜色（仅控制台）"""
        color = COLORS.get(level, "")
        if color and self.console and sys.stdout.isatty():
            return f"{color}{text}{COLORS['RESET']}"
        return text

    def _log(self, level: str, message: str):
        """核心日志方法"""
        # 检查级别
        if LOG_LEVELS.get(level, 0) < self.min_level:
            return

        formatted = self._format(level, message)

        # 控制台输出（带颜色）
        if self.console:
            colored = self._colorize(level, formatted)
            print(colored)

        # 文件输出（纯文本）
        if self._file_handle:
            try:
                self._file_handle.write(formatted + "\n")
                self._file_handle.flush()
            except Exception as e:
                print(f"[WARN] 日志文件写入失败: {e}")

    def debug(self, msg: str): self._log("DEBUG", msg)
    def info(self, msg: str): self._log("INFO", msg)
    def warn(self, msg: str): self._log("WARN", msg)
    def warning(self, msg: str): self._log("WARN", msg)  # alias for warn()
    def error(self, msg: str): self._log("ERROR", msg)
    def success(self, msg: str): self._log("SUCCESS", msg)

    def close(self):
        """关闭日志文件"""
        if self._file_handle:
            try:
                self._file_handle.close()
            except Exception as e:
                print(f"[WARN] 日志文件关闭失败: {e}")


# 全局日志实例
_logger: Optional[SchedulerLogger] = None


def get_logger(
    name: str = "crewai-scheduler",
    log_file: Optional[str] = None,
    **kwargs
) -> SchedulerLogger:
    """获取或创建全局日志实例"""
    global _logger
    if _logger is None or (log_file and _logger.log_file_path != log_file):
        _logger = SchedulerLogger(name=name, log_file=log_file, **kwargs)
    return _logger


def init_logging(log_file: Optional[str] = None) -> SchedulerLogger:
    """
    初始化日志系统
    
    Args:
        log_file: 日志文件路径（默认: data/logs/scheduler_YYYYMMDD.log）
    
    Returns:
        Logger 实例
    """
    if log_file is None:
        # 使用 data/ 目录下的 logs/（与源码分离）
        # 兼容直接运行和模块导入两种场景
        try:
            from __main__ import DATA_DIR
            base_dir = DATA_DIR
        except ImportError:
            base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
        logs_dir = os.path.join(base_dir, "logs")
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, exist_ok=True)
        date_str = datetime.now().strftime("%Y%m%d")
        log_file = os.path.join(logs_dir, f"scheduler_{date_str}.log")

    return get_logger(log_file=log_file)


def close_logging():
    """关闭日志系统"""
    global _logger
    if _logger:
        _logger.close()
        _logger = None
