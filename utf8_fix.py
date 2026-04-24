"""
UTF-8 编码修复 - 确保 Windows 终端正确显示中文
"""

import sys


def ensure_utf8():
    """重新配置 stdout/stderr 为 UTF-8 编码"""
    try:
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        if hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
