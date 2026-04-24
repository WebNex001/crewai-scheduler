"""
共享常量与工具函数

集中管理项目中的：
- 阶段名称映射 (STAGE_NAMES / STAGE_NAMES_NUMBERED)
- 文件遍历工具 (_walk_project_files)
- 其他跨模块常量
"""

import os
from typing import List, Tuple, Set

from code_extractor import CODE_REVIEW_EXTENSIONS

# ==================== 阶段名称映射 ====================

STAGE_NAMES = {
    'requirements': '需求分析',
    'architecture': '架构设计',
    'detailed_design': '详细设计',
    'development': '编码开发',
    'code_review': '代码审查',
    'testing': '测试',
    'deployment': '部署上线',
    'delivery': '项目交付'
}

STAGE_NAMES_NUMBERED = {
    'requirements': '01_需求分析',
    'architecture': '02_架构设计',
    'detailed_design': '03_详细设计',
    'development': '04_编码开发',
    'code_review': '05_代码审查',
    'testing': '06_测试',
    'deployment': '07_部署上线',
    'delivery': '08_项目交付'
}

# ==================== 断点续传 ====================

STALE_IN_PROGRESS_SECONDS = 3600  # in_progress 超过此时间视为崩溃残留（秒）

# ==================== 阶段输出阈值 ====================

STAGE_OUTPUT_FILE_THRESHOLD = 5000  # 阶段输出超过此字符数时存入独立文件

# ==================== 输出截断常量 ====================

PREVIEW_CHARS = 500         # _save_stage_output 摘要预览长度
RESULT_PREVIEW_CHARS = 300  # 结果预览长度（out输出）
CONTEXT_TRUNCATE_CHARS = 3000  # 前置阶段上下文截断长度
REPORT_TRUNCATE_CHARS = 1500   # 报告截断长度
MAX_CALL_RECORDS = 1000        # 监控调用记录上限
MAX_PARALLEL_WORKERS = 3       # 并行模块开发最大线程数


# ==================== 文件遍历工具 ====================

# 遍历时默认跳过的目录名
SKIP_DIR_NAMES: Set[str] = {'.', 'node_modules', '__pycache__'}


def _walk_project_files(
    project_path: str,
    extensions: Set[str] = None,
    skip_stages_dir: bool = True,
    max_chars: int = 0,
) -> List[Tuple[str, str, str]]:
    """
    遍历项目目录中的代码文件。
    
    Args:
        project_path: 项目根目录
        extensions: 文件扩展名白名单（如 CODE_REVIEW_EXTENSIONS），None 则不过滤
        skip_stages_dir: 是否跳过 docs/stages 目录
        max_chars: 总字符数上限（0 = 不限制）
    
    Returns:
        [(相对路径, 文件内容, 扩展名), ...]
    """
    if not project_path or not os.path.isdir(project_path):
        return []

    results = []
    total_chars = 0

    for root, dirs, fnames in os.walk(project_path):
        # 跳过隐藏目录和常见排除目录
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in SKIP_DIR_NAMES]
        if skip_stages_dir and os.path.basename(root) == 'stages':
            continue

        for fname in sorted(fnames):
            ext = fname.rsplit('.', 1)[-1].lower() if '.' in fname else ''
            if extensions and ext not in extensions:
                continue

            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, project_path).replace('\\', '/')

            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                continue

            if not content.strip():
                continue

            results.append((rel_path, content, ext))
            total_chars += len(content)

            if max_chars > 0 and total_chars > max_chars:
                return results

    return results
