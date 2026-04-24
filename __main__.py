#!/usr/bin/env python3
"""
CrewAI Scheduler - OpenClaw Skill Entry Point (v3.0 工作流版)

v3.0 功能:
- 工作流模式: execute-workflow / workflow-status / workflow-reset / workflow-stages
- 技术部 8 阶段标准工作流（需求分析->架构设计->详细设计->开发->审查->测试->部署->交付）
- 项目串行执行：一个项目走完全部阶段再开始下一个
- 上下文传递：前一阶段输出自动注入下一阶段 Prompt
- 角色切换：每个阶段使用不同的 AI 角色身份
- 思考模式按阶段开关（thinking parameter）
- 回退机制：代码审查/测试不通过 -> 自动回退到开发阶段（最大回退次数限制）
- Debug 模式：详细日志输出到 Debug/ 目录
"""

import sys as _sys
import os
import json
import argparse
import signal
import time as _time
from datetime import datetime
from typing import Optional, List, Dict, Any

_sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# === 代码提取和项目写入模块 ===
try:
    from code_extractor import CodeExtractor, CodeFile
    from code_extractor import parse_modules_from_design, extract_exports_summary, extract_module_design_section
    from code_extractor import CODE_REVIEW_EXTENSIONS, CODE_EXTENSIONS
    from project_writer import ProjectWriter, create_project_writer
    CODE_EXTRACTOR_AVAILABLE = True
except ImportError:
    CODE_EXTRACTOR_AVAILABLE = False

# === 数据目录 ===
def _get_data_dir():
    env_dir = os.getenv("CREWAI_DATA_DIR")
    if env_dir:
        return env_dir
    src_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(src_dir, "data")
    if not os.path.exists(data_dir):
        os.makedirs(data_dir, exist_ok=True)
    return data_dir

DATA_DIR = _get_data_dir()

from utf8_fix import ensure_utf8
ensure_utf8()

from scheduler_log import init_logging, get_logger, close_logging

# === 从拆分模块导入 ===
from db import load_db, save_db, atomic_update, PROJECTS_DB, WORKFLOW_DB, set_data_dir, compact_workflow_db
from retry import _call_with_retry, _call_with_context_compress, STAGE_DELAY_SECONDS, MODULE_DELAY_SECONDS, MAX_API_RETRIES
from constants import (
    STAGE_NAMES, STAGE_NAMES_NUMBERED, STALE_IN_PROGRESS_SECONDS,
    STAGE_OUTPUT_FILE_THRESHOLD, PREVIEW_CHARS, RESULT_PREVIEW_CHARS,
    CONTEXT_TRUNCATE_CHARS, MAX_PARALLEL_WORKERS, _walk_project_files,
)
from workflow_db import (
    ensure_db as ensure_sqlite_db,
    load_workflow as sqlite_load_workflow,
    load_all_workflows as sqlite_load_all_workflows,
    save_workflow as sqlite_save_workflow,
    compact_workflow as sqlite_compact_workflow,
    query_workflows_by_status,
    record_token_usage,
    get_token_usage_summary,
    load_all_projects as sqlite_load_all_projects,
    save_project as sqlite_save_project,
)

# 同步 DATA_DIR 到 db 模块
set_data_dir(DATA_DIR)

_logger = None

def log():
    global _logger
    if _logger is None:
        _logger = init_logging()
    return _logger

def out(*args, **kwargs):
    print(*args, **kwargs)
    try:
        msg = " ".join(str(a) for a in args)
        if _logger:
            _logger.info(msg)
    except Exception as e:
        # 日志写入失败不应阻塞主流程，但仍需知道
        pass


def _save_stage_output(p_name: str, stage_id: str, result_text: str) -> str:
    """
    保存阶段输出。超过阈值时写入独立文件，返回值：
    - 短文本：原样返回
    - 长文本：写入文件，返回 "file:stages/stage_id_full.md" 引用
    """
    if not result_text or len(result_text) <= STAGE_OUTPUT_FILE_THRESHOLD:
        return result_text

    try:
        writer = create_project_writer()
        project_path = writer._get_project_path(p_name)
        stages_dir = os.path.join(project_path, "docs", "stages")
        os.makedirs(stages_dir, exist_ok=True)
        full_path = os.path.join(stages_dir, f"{stage_id}_full.md")
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(result_text)
        # 返回摘要 + 文件引用
        preview = result_text[:PREVIEW_CHARS].strip()
        return f"{preview}\n\n...(完整输出已保存至 file:docs/stages/{stage_id}_full.md, 共 {len(result_text)} 字符)"
    except Exception as e:
        log().warning("_save_stage_output 写入失败: %s" % e)
        return result_text


def _load_stage_output(p_name: str, stored_text: str) -> str:
    """
    加载阶段输出。如果是文件引用则读取完整内容，否则原样返回。
    """
    if not stored_text or not stored_text.startswith("file:"):
        return stored_text

    try:
        ref_path = stored_text.split("file:")[1].split(",")[0].strip()
        writer = create_project_writer()
        project_path = writer._get_project_path(p_name)
        full_path = os.path.join(project_path, ref_path)
        if os.path.exists(full_path):
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        log().warning("_load_stage_output 读取失败: %s" % e)
    return stored_text


def _compact_completed_stages(p_name: str, wf: Dict, current_stage_id: str):
    """
    阶段完成后自动压缩：清理已完成阶段的 history 和 sub_tasks 大字段，
    减少工作流数据的总体积，防止 JSON 膨胀。

    注意：不压缩 result，因为后续阶段需要通过 _load_stage_output 引用完整输出。
    只有 workflow 全部完成后才压缩 result（通过 workflow-health --compact）。
    """
    stages = wf.get("stages", {})
    for sid, sd in stages.items():
        if sd.get("status") != "completed":
            continue
        # 压缩 history：只保留元数据（result 可能很大）
        hist = sd.get("history", [])
        if hist and len(hist) > 0:
            sd["history"] = [{"attempt": h.get("attempt", i+1), "duration_seconds": h.get("duration_seconds")}
                             for i, h in enumerate(hist)]
        # 清理 sub_tasks 中的 _files 等大字段
        st = sd.get("sub_tasks", [])
        if st:
            sd["sub_tasks"] = [{"id": t.get("id"), "name": t.get("name"),
                                "status": t.get("status"),
                                "files_written": t.get("files_written", 0),
                                "duration_seconds": t.get("duration_seconds", 0)}
                               for t in st]

def _detect_crashed_workflows() -> List[Dict[str, Any]]:
    """
    扫描所有工作流，检测状态为 in_progress 但超时未更新的（疑似崩溃）。
    返回 [{name, wf, stale_seconds}] 列表。
    """
    workflows = _load_workflows()
    wf_all = workflows.get("workflows", {})
    crashed = []
    now = time.time()

    for name, wf in wf_all.items():
        if wf.get("status") != "in_progress":
            continue
        # 检查最后更新时间
        last_update = wf.get("last_heartbeat") or wf.get("started_at")
        if not last_update:
            continue
        try:
            last_ts = datetime.fromisoformat(last_update).timestamp()
            stale_secs = now - last_ts
            if stale_secs > STALE_IN_PROGRESS_SECONDS:
                crashed.append({"name": name, "wf": wf, "stale_seconds": stale_secs})
        except (ValueError, OSError):
            pass
    return crashed


def _mark_workflow_interrupted(project_name: str):
    """
    将工作流标记为 interrupted（崩溃/中断），保存当前进度。
    与 failed 不同，interrupted 可以从断点恢复。
    """
    workflows = _load_workflows()
    wf = workflows.get("workflows", {}).get(project_name)
    if not wf:
        return
    wf["status"] = "interrupted"
    wf["interrupted_at"] = datetime.now().isoformat()
    # 标记当前阶段为 interrupted（而非 failed）
    current_sid = wf.get("current_stage_id")
    if current_sid and current_sid in wf.get("stages", {}):
        sd = wf["stages"][current_sid]
        if sd.get("status") not in ("completed", "failed"):
            sd["status"] = "interrupted"
    _save_workflow(project_name, wf)

# === 优雅中断 ===
_interrupted = False

def _signal_handler(signum, frame):
    """SIGINT/SIGTERM 处理器：标记中断，不立即退出"""
    global _interrupted
    _interrupted = True
    out("\n[WARN] 收到中断信号，等待当前操作完成后退出（再次 Ctrl+C 强制退出）...")
    signal.signal(signal.SIGINT, lambda s, f: (_sys.exit(1)))  # 二次则强制

def install_signal_handlers():
    """注册信号处理器"""
    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _signal_handler)

def is_interrupted() -> bool:
    """检查是否收到中断信号"""
    return _interrupted


# === 数据库初始化 ===
def _db_path(filename):
    return os.path.join(DATA_DIR, filename)

def init_databases():
    """初始化数据库（SQLite + JSON 向后兼容）"""
    # 确保 SQLite 数据库就绪（含自动迁移）
    ensure_sqlite_db()
    # 同时保留 JSON 文件用于向后兼容
    if not os.path.exists(_db_path(PROJECTS_DB)):
        save_db(PROJECTS_DB, {"projects": {}})
    if not os.path.exists(_db_path(WORKFLOW_DB)):
        save_db(WORKFLOW_DB, {"workflows": {}})


# === 工作流数据读写（SQLite 优先，JSON 同步） ===

def _load_workflows() -> Dict:
    """加载所有工作流（SQLite 优先，兼容 JSON）"""
    try:
        return sqlite_load_all_workflows()
    except Exception:
        return load_db(WORKFLOW_DB)


def _save_workflow(project_name: str, wf: Dict):
    """保存单个工作流到 SQLite + JSON（SQLite 为主存储，JSON 按需更新）"""
    try:
        sqlite_save_workflow(project_name, wf)
    except Exception as e:
        log().debug("SQLite 保存工作流失败，回退到 JSON: %s" % e)
    # 只更新 JSON 中对应项目的条目（避免全量重写大文件）
    try:
        json_wfs = load_db(WORKFLOW_DB)
        if "workflows" not in json_wfs:
            json_wfs["workflows"] = {}
        json_wfs["workflows"][project_name] = wf
        save_db(WORKFLOW_DB, json_wfs)
    except Exception:
        pass


def _load_projects() -> Dict:
    """加载所有项目（SQLite 优先，兼容 JSON）"""
    try:
        return sqlite_load_all_projects()
    except Exception:
        return load_db(PROJECTS_DB)


def _save_project(name: str, project: Dict):
    """保存单个项目到 SQLite + JSON"""
    try:
        sqlite_save_project(name, project)
    except Exception as e:
        log().debug("SQLite 保存项目失败: %s" % e)
    try:
        projects = _load_projects()
        projects["projects"][name] = project
        save_db(PROJECTS_DB, projects)
    except Exception:
        pass


# ==================== 主入口 ====================

def main():
    parser = argparse.ArgumentParser(
        description='CrewAI Scheduler v3.0 - AI工作流调度系统',
        prog='crewai-scheduler'
    )
    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # 基础命令
    subparsers.add_parser('init', help='初始化调度系统')

    pp = subparsers.add_parser('create-project', help='创建项目')
    pp.add_argument('--name', '-n', required=True, help='项目名称')
    pp.add_argument('--description', '-d', default='', help='项目描述')
    pp.add_argument('--department', '-dept', default='技术部',
                    choices=['技术部', '运营部', '交付部'], help='负责部门')

    subparsers.add_parser('list-projects', help='列出所有项目')
    subparsers.add_parser('status', help='查看系统状态')

    rp = subparsers.add_parser('report', help='生成报告')
    rp.add_argument('--project', '-p', help='项目名称(可选)')

    subparsers.add_parser('monitor', help='查看使用监控报告')

    cp = subparsers.add_parser('clear', help='清空所有数据')
    cp.add_argument('--confirm', '-y', action='store_true', help='确认清空')

    dp = subparsers.add_parser('delete-project', help='删除项目（含工作流和生成文件）')
    dp.add_argument('--name', '-n', required=True, help='项目名称')
    dp.add_argument('--confirm', '-y', action='store_true', help='确认删除')

    # 工作流命令 (v3.0)
    wep = subparsers.add_parser('execute-workflow', help='[工作流] 执行项目工作流')
    wep.add_argument('--project', '-p', help='项目名称')
    wep.add_argument('--stage', '-s', type=int, default=None, help='从指定阶段开始(1-8)')
    wep.add_argument('--all', '-a', action='store_true', help='执行所有待处理项目')
    wep.add_argument('--dry-run', action='store_true', help='干跑模式：预览将执行的阶段/模块，不实际调API')
    wep.add_argument('--resume', action='store_true', help='断点续传：自动检测并恢复中断的工作流')

    wsp = subparsers.add_parser('workflow-status', help='[工作流] 查看项目工作流进度')
    wsp.add_argument('--project', '-p', help='项目名称')

    wrp = subparsers.add_parser('workflow-reset', help='[工作流] 重置项目工作流')
    wrp.add_argument('--project', '-p', required=True, help='项目名称')

    wlp = subparsers.add_parser('workflow-stages', help='[工作流] 查看部门工作流定义')
    wlp.add_argument('--department', '-dept', default='技术部',
                     choices=['技术部', '运营部', '交付部'], help='部门名称')

    whp = subparsers.add_parser('workflow-health', help='[工作流] 健康检查：扫描崩溃/中断的工作流')
    whp.add_argument('--fix', action='store_true', help='自动将崩溃的工作流标记为 interrupted')
    whp.add_argument('--resume', action='store_true', help='自动恢复中断的工作流')
    whp.add_argument('--compact', action='store_true', help='压缩已完成的工作流数据（截断result/清理history）')

    wpp = subparsers.add_parser('workflow-pause', help='[工作流] 暂停正在执行的工作流')
    wpp.add_argument('--project', '-p', required=True, help='项目名称')

    wrp2 = subparsers.add_parser('workflow-resume', help='[工作流] 恢复暂停的工作流')
    wrp2.add_argument('--project', '-p', required=True, help='项目名称')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # 安装信号处理器（优雅中断）
    install_signal_handlers()

    try:
        from usage_monitor import MonitorTimer

        if args.command == 'init':
            with MonitorTimer("init") as t:
                return cmd_init()
        elif args.command == 'create-project':
            with MonitorTimer("create-project") as t:
                return cmd_create_project(args.name, args.description, getattr(args, 'department', '技术部'))
        elif args.command == 'list-projects':
            with MonitorTimer("list-projects") as t:
                return cmd_list_projects()
        elif args.command == 'status':
            with MonitorTimer("status") as t:
                return cmd_status()
        elif args.command == 'report':
            with MonitorTimer("report") as t:
                return cmd_report(args.project)
        elif args.command == 'monitor':
            return cmd_monitor()
        elif args.command == 'clear':
            with MonitorTimer("clear") as t:
                return cmd_clear(args.confirm)
        elif args.command == 'delete-project':
            with MonitorTimer("delete-project") as t:
                return cmd_delete_project(args.name, getattr(args, 'confirm', False))
        elif args.command == 'execute-workflow':
            with MonitorTimer("execute-workflow") as t:
                return cmd_execute_workflow(project_name=args.project, start_stage=args.stage,
                                           execute_all=getattr(args, 'all', False),
                                           dry_run=getattr(args, 'dry_run', False),
                                           resume=getattr(args, 'resume', False))
        elif args.command == 'workflow-status':
            with MonitorTimer("workflow-status") as t:
                return cmd_workflow_status(args.project)
        elif args.command == 'workflow-reset':
            with MonitorTimer("workflow-reset") as t:
                return cmd_workflow_reset(args.project)
        elif args.command == 'workflow-stages':
            return cmd_workflow_stages(getattr(args, 'department', '技术部'))
        elif args.command == 'workflow-health':
            return cmd_workflow_health(fix=getattr(args, 'fix', False),
                                      resume=getattr(args, 'resume', False),
                                      compact=getattr(args, 'compact', False))
        elif args.command == 'workflow-pause':
            return cmd_workflow_pause(args.project)
        elif args.command == 'workflow-resume':
            return cmd_workflow_resume(args.project)

    except Exception as e:
        out("[ERROR] 错误: %s" % e)
        import traceback
        traceback.print_exc()
        return 1


# ==================== 命令实现 ====================

def cmd_init():
    """初始化调度系统"""
    out("[INFO] 初始化 CrewAI 调度系统 v3.0 (工作流版)...")
    init_databases()

    try:
        from crewai_scheduler import get_scheduler
        scheduler = get_scheduler()
        workflows = scheduler.config.get("workflow", {})

        out("[OK] 调度系统初始化完成")
        out("[INFO] 已配置的工作流:")
        for dept_name, dept_wf in workflows.items():
            if not isinstance(dept_wf, dict):
                continue  # 跳过 _comment 等非部门字段
            wf_enabled = dept_wf.get("enabled", False)
            stages_count = len(dept_wf.get("stages", []))
            if wf_enabled:
                out("   - %s [工作流] (%d 个阶段)" % (dept_name, stages_count))
            else:
                out("   - %s" % dept_name)

        if scheduler.is_debug():
            dp = scheduler.get_debug_log_path()
            out("[DEBUG] Debug 日志: %s" % (dp or "N/A"))

        out("\n[INFO] 使用 execute-workflow 启动项目开发流程")
    except ImportError as e:
        out("[WARN] 核心模块未安装: %s" % e)
        out("[OK] 基础调度系统初始化完成")

    return 0


def cmd_create_project(name, description="", department="技术部"):
    """创建项目(v3.0: 自动初始化工作流状态)"""
    out("[INFO] 创建项目: %s (部门: %s)" % (name, department))
    init_databases()
    projects = _load_projects()

    if name in projects.get("projects", {}):
        out("[WARN] 项目 '%s' 已存在" % name)
        return 1

    now = datetime.now().isoformat()
    project = {
        "name": name,
        "description": description,
        "department": department,
        "created_at": now,
        "status": "active",
    }
    _save_project(name, project)

    try:
        from crewai_scheduler import get_scheduler
        scheduler = get_scheduler()
    except Exception as e:
        out("[WARN] 调度器初始化失败: %s" % e)
        out("[OK] 项目 '%s' 创建成功 (标准模式，工作流未初始化)" % name)
        return 0

    if scheduler.is_workflow_enabled(department):
        stages = scheduler.get_workflow_stages(department)
        stage_outputs = {}
        for stage in stages:
            stage_outputs[stage["id"]] = {
                "status": "pending",
                "agent": stage["agent"],
                "result": None,
                "completed_at": None,
                "duration_seconds": None,
                "retry_count": 0,
            }

        wf_record = {
            "project": name,
            "department": department,
            "status": "ready",
            "current_stage_index": 0,
            "current_stage_id": stages[0]["id"] if stages else None,
            "total_stages": len(stages),
            "stages": stage_outputs,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
            "summary": None,
        }
        _save_workflow(name, wf_record)
        out("[OK] 项目 '%s' 创建成功 (工作流模式, %d 个阶段)" % (name, len(stages)))
    else:
        out("[OK] 项目 '%s' 创建成功 (标准模式)" % name)

    if description:
        out("       描述: %s" % description)

    return 0


def cmd_list_projects():
    """列出所有项目"""
    projects = _load_projects()
    workflows = _load_workflows()

    if not projects.get("projects"):
        out("[EMPTY] 暂无项目")
        return 0

    out("[FOLDERS] 项目列表 (%d 个):" % len(projects['projects']))
    out("-" * 70)

    for name, project in projects["projects"].items():
        status_icon = "[ACTIVE]" if project.get("status") == "active" else "[INACTIVE]"
        dept = project.get("department", "未指定")
        desc = project.get("description", "")
        created = project.get("created_at", "?")

        wf_info = ""
        wf = workflows.get("workflows", {}).get(name)
        if wf:
            wf_status_map = {
                "ready": "[待启动]", "in_progress": "[进行中]",
                "completed": "[已完成]", "failed": "[异常]"
            }
            wf_s = wf.get("status", "unknown")
            ci = wf.get("current_stage_index", 0) + 1
            ts = wf.get("total_stages", "?")
            wf_info = " | Workflow: %s [%d/%d]" % (wf_status_map.get(wf_s, wf_s), ci, ts)

        out("  %s %s (%s)%s" % (status_icon, name, dept, wf_info))
        if desc:
            out("       描述: %s" % desc[:60])
        out("       创建: %s" % created[:19])
        out()

    return 0


def cmd_status():
    """查看系统状态"""
    out("[STATS] 系统状态:")
    out("-" * 60)

    projects = _load_projects()
    workflows = _load_workflows()

    project_count = len(projects.get("projects", {}))
    out("[FOLDER] 项目总数: %d" % project_count)

    wf_all = workflows.get("workflows", {})
    if wf_all:
        wf_statuses = {}
        for wfname, wf in wf_all.items():
            s = wf.get("status", "unknown")
            wf_statuses[s] = wf_statuses.get(s, 0) + 1
        out("\n[WORKFLOW] 工作流项目:")
        for s, c in wf_statuses.items():
            out("       %s: %d 个项目" % (s, c))

    try:
        from crewai_scheduler import get_scheduler
        scheduler = get_scheduler()
        if scheduler.is_debug():
            out("\n[DEBUG] Debug 模式: ON")
            out("       日志文件: %s" % (scheduler.get_debug_log_path() or "N/A"))
    except Exception as e:
        log().debug("获取调试状态失败: %s" % e)

    return 0


def cmd_report(project_name=None):
    """生成报告"""
    out("[REPORT] 生成报告中...")
    projects = _load_projects()
    workflows = _load_workflows()

    wf_all = workflows.get("workflows", {})

    lines = []
    lines.append("=" * 80)
    lines.append("CrewAI Scheduler v3.0 执行报告 (工作流版)")
    lines.append("生成时间: %s" % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    lines.append("=" * 80)

    if project_name:
        if project_name not in projects.get("projects", {}):
            out("[ERROR] 项目 '%s' 不存在" % project_name)
            return 1
        project = projects["projects"][project_name]
        lines.append("\n[PROJECT] %s" % project_name)
        lines.append("部门: %s" % project.get("department", "N/A"))
        lines.append("状态: %s" % project.get("status", "unknown"))

        wf = workflows.get("workflows", {}).get(project_name)
        if wf:
            lines.append("\n%s" % ("=" * 80))
            lines.append("[WORKFLOW DETAILS]")
            lines.append("%s" % ("=" * 80))
            lines.append("工作流状态: %s" % wf.get("status"))
            lines.append("当前阶段: %d/%d" % (wf.get("current_stage_index", 0) + 1, wf.get("total_stages", "?")))
            lines.append("\n各阶段输出:")
            for sid, sd in wf.get("stages", {}).items():
                ss = sd.get("status", "pending")
                agent = sd.get("agent", "")
                dur = sd.get("duration_seconds")
                ds = "%.1fs" % dur if dur else "N/A"
                lines.append("\n  [%s] %s (%s) %s" % (ss.upper(), sid, agent, ds))
                result = sd.get("result")
                if result:
                    preview = result[:1500] if len(result) > 1500 else result
                    lines.append(preview)
                    if len(result) > 1500:
                        lines.append("...(截断, 完整共%d字符)" % len(result))
    else:
        lines.append("\n[STATS] 系统概览:")
        lines.append("  项目总数: %d" % len(projects.get("projects", {})))
        if wf_all:
            lines.append("  工作流项目: %d" % len(wf_all))
            for wfname, wf in wf_all.items():
                lines.append("    - %s: %s" % (wfname, wf.get("status", "?")))

    report_text = "\n".join(lines)
    out("\n" + report_text)

    reports_dir = os.path.join(DATA_DIR, "reports")
    if not os.path.exists(reports_dir):
        os.makedirs(reports_dir, exist_ok=True)
    report_filename = "report_%s.txt" % datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(reports_dir, report_filename)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    out("\n[SAVE] 报告已保存: %s" % report_filename)
    return 0


def cmd_monitor():
    """查看使用监控报告"""
    from usage_monitor import get_monitor
    monitor = get_monitor()
    monitor.print_report()
    return 0


def cmd_delete_project(name: str, confirm: bool = False):
    """删除项目（含工作流记录和生成的项目文件）"""
    if not confirm:
        out("[WARN] 这将删除项目 '%s' 的所有数据（工作流记录+生成文件）！" % name)
        out("       请使用 --confirm (-y) 确认操作。")
        return 1

    init_databases()
    projects = _load_projects()
    if name not in projects.get("projects", {}):
        out("[ERROR] 项目 '%s' 不存在" % name)
        return 1

    deleted_items = []

    # 1. 删除工作流记录（SQLite + JSON）
    try:
        sqlite_delete_result = False
        try:
            from workflow_db import delete_workflow as sqlite_delete_workflow
            sqlite_delete_workflow(name)
            sqlite_delete_result = True
        except Exception:
            pass
        # 从 JSON 中删除
        json_wfs = load_db(WORKFLOW_DB)
        if name in json_wfs.get("workflows", {}):
            del json_wfs["workflows"][name]
            save_db(WORKFLOW_DB, json_wfs)
            sqlite_delete_result = True
        if sqlite_delete_result:
            deleted_items.append("工作流记录")
    except Exception as e:
        out("[WARN] 删除工作流记录失败: %s" % e)

    # 2. 删除项目记录（SQLite + JSON）
    try:
        try:
            from workflow_db import save_project as sqlite_save_project
            # SQLite 中没有 delete_project，直接用 SQL
            import sqlite3
            from workflow_db import _get_db_path
            db_path = _get_db_path()
            conn = sqlite3.connect(db_path)
            conn.execute("DELETE FROM projects WHERE name = ?", (name,))
            conn.commit()
            conn.close()
        except Exception:
            pass
        json_projs = load_db(PROJECTS_DB)
        if name in json_projs.get("projects", {}):
            del json_projs["projects"][name]
            save_db(PROJECTS_DB, json_projs)
        deleted_items.append("项目记录")
    except Exception as e:
        out("[WARN] 删除项目记录失败: %s" % e)

    # 3. 删除生成的项目文件目录
    try:
        if CODE_EXTRACTOR_AVAILABLE:
            writer = create_project_writer()
            project_path = writer._get_project_path(name)
            if os.path.exists(project_path):
                import shutil
                shutil.rmtree(project_path)
                deleted_items.append("项目文件 (%s)" % project_path)
    except Exception as e:
        out("[WARN] 删除项目文件失败: %s" % e)

    out("[OK] 项目 '%s' 已删除: %s" % (name, ", ".join(deleted_items)))
    return 0


def cmd_clear(confirm=False):
    """清空所有数据"""
    if not confirm:
        out("[WARN] 这将删除所有项目和工作流数据！")
        out("       请使用 --confirm (-y) 确认操作。")
        return 1

    out("[CLEAR] 清空所有数据...")

    for db_file in [PROJECTS_DB, WORKFLOW_DB]:
        path = _db_path(db_file)
        if os.path.exists(path):
            save_db(db_file, {} if db_file != WORKFLOW_DB else {"workflows": {}})
            out("  [DEL] %s" % db_file)

    out("[OK] 所有数据已清空,系统已重新初始化")
    init_databases()
    return 0


# ==================== 工作流命令实现 (v3.0) ====================

def cmd_workflow_stages(department="技术部"):
    """查看部门工作流阶段定义"""
    from crewai_scheduler import get_scheduler
    scheduler = get_scheduler()
    stages = scheduler.get_workflow_stages(department)
    enabled = scheduler.is_workflow_enabled(department)

    out("=" * 70)
    out("[WORKFLOW STAGES] 部门: %s" % department)
    out("  状态: %s" % ("启用" if enabled else "未启用"))
    out("  阶段数: %d" % len(stages))
    out("=" * 70)

    for i, stage in enumerate(stages, 1):
        thinking_mark = " [思考]" if stage.get("thinking", True) else ""
        out("  %d. %s | Agent: %s%s" % (i, stage["name"], stage["agent"], thinking_mark))
        out("     ID: %s" % stage["id"])
        role = stage.get("agent_role", "")
        if role:
            out("     角色: %s" % role[:60])

    retry_rules = scheduler.config.get("workflow", {}).get(department, {}).get("retry_on_reject", {})
    if retry_rules:
        out("\n  回退规则:")
        for stage_id, target in retry_rules.items():
            out("    %s -> %s" % (stage_id, target))

    max_ret = scheduler.get_max_retries(department)
    out("\n  最大回退次数: %d" % max_ret)
    out("  API timeout: %ds" % scheduler.get_api_timeout())
    out("  Debug: %s" % ("ON" if scheduler.is_debug() else "OFF"))

    return 0


def cmd_workflow_status(project_name=None):
    """查看项目工作流详细进度"""
    workflows = _load_workflows()
    wf_all = workflows.get("workflows", {})

    if project_name:
        if project_name not in wf_all:
            out("[ERROR] 项目 '%s' 无工作流记录" % project_name)
            return 1
        _print_one_workflow(project_name, wf_all[project_name])
    else:
        if not wf_all:
            out("[EMPTY] 暂无工作流项目")
            return 0
        for name in sorted(wf_all.keys()):
            _print_one_workflow(name, wf_all[name])
            out()

    return 0


def _print_one_workflow(name, wf):
    """打印单个项目工作流详情"""
    status = wf.get("status", "unknown")
    status_icons = {
        "ready": "[READY]", "in_progress": "[RUNNING]",
        "completed": "[DONE!]", "failed": "[FAIL!]", "interrupted": "[PAUSED]",
        "paused": "[PAUSED]"
    }
    icon = status_icons.get(status, "[?]")
    current_idx = wf.get("current_stage_index", 0)
    total = wf.get("total_stages", "?")
    started = wf.get("started_at", "?")
    completed = wf.get("completed_at", "")

    out("=" * 70)
    out("[WORKFLOW] %s %s" % (icon, name))
    out("  状态: %s | 进度: 阶段 %d/%s" % (status, current_idx + 1, total))
    if started and started != "?":
        out("  开始: %s" % started[:19])
    if completed:
        out("  完成: %s" % completed[:19])
    summary = wf.get("summary")
    if summary:
        out("  摘要: %s" % summary)
    out("-" * 70)

    stages_data = wf.get("stages", {})
    for i, sid in enumerate(stages_data.keys()):
        sd = stages_data[sid]
        s_status = sd.get("status", "pending")
        agent = sd.get("agent", "")
        duration = sd.get("duration_seconds")
        dur_str = "%.1fs" % duration if duration else "N/A"

        if s_status == "completed":
            if sd.get("force_passed"):
                icon2 = "[PASS!]"
            else:
                icon2 = "[DONE]"
        elif s_status == "rejected":
            icon2 = "[REJECTED]"
        elif s_status == "failed":
            icon2 = "[FAILED!]"
        elif s_status == "interrupted":
            icon2 = "[PAUSED]"
        elif s_status == "paused":
            icon2 = "[PAUSED]"
        else:
            icon2 = "[TODO]"

        marker = " >>>" if i == current_idx and status == "in_progress" else ""

        out("  %s #%d %-18s %-10s %s%s" % (icon2, i+1, sid, agent, dur_str, marker))

        result = sd.get("result")
        if result and s_status == "completed":
            preview = result[:80].replace('\n', ' ')
            out("       Output: %s..." % preview)

        hist = sd.get("history", [])
        for h in hist:
            h_preview = (h.get("result") or "")[:60].replace('\n', ' ')
            h_dur = h.get("duration_seconds")
            ds = "(%.1fs)" % h_dur if h_dur else ""
            out("       [历史#%d]%s %s..." % (h['attempt'], ds, h_preview))


def cmd_workflow_reset(project_name):
    """重置项目工作流"""
    workflows = _load_workflows()
    wf_all = workflows.get("workflows", {})

    if project_name not in wf_all:
        out("[ERROR] 项目 '%s' 无工作流记录" % project_name)
        return 1

    wf = wf_all[project_name]
    old_status = wf.get("status", "?")

    for sid, sd in wf.get("stages", {}).items():
        sd["status"] = "pending"
        sd["result"] = None
        sd["completed_at"] = None
        sd["duration_seconds"] = None
        sd["retry_count"] = 0
        sd["history"] = []

    wf["status"] = "ready"
    wf["current_stage_index"] = 0
    stages_def = None
    try:
        from crewai_scheduler import get_scheduler
        scheduler = get_scheduler()
        stages_def = scheduler.get_workflow_stages(wf.get("department", "技术部"))
    except Exception:
        pass
    wf["current_stage_id"] = stages_def[0]["id"] if stages_def else None
    wf["started_at"] = None
    wf["completed_at"] = None
    wf["summary"] = None

    _save_workflow(project_name, wf)
    out("[OK] 项目 '%s' 工作流已重置 (%s -> ready)" % (project_name, old_status))
    return 0


def cmd_workflow_health(fix: bool = False, resume: bool = False, compact: bool = False) -> int:
    """健康检查：扫描崩溃/中断的工作流，可选修复、恢复或压缩"""
    out("=" * 70)
    out("[健康检查] 工作流状态扫描")
    out("=" * 70)

    workflows = _load_workflows()
    wf_all = workflows.get("workflows", {})

    if not wf_all:
        out("[INFO] 暂无工作流记录")
        return 0

    issues = []
    for name, wf in wf_all.items():
        status = wf.get("status", "unknown")
        # 检测1: paused/interrupted 状态
        if status in ("interrupted", "paused"):
            ci = wf.get("current_stage_index", 0) + 1
            ts = wf.get("total_stages", "?")
            interrupted_at = wf.get("interrupted_at") or wf.get("paused_at", "?")
            issues.append({
                "name": name, "type": status,
                "detail": "阶段 %d/%s, %s于 %s" % (ci, ts, "暂停" if status == "paused" else "中断", interrupted_at[:19] if interrupted_at != "?" else "?"),
            })
        # 检测2: in_progress 超时（疑似崩溃）
        elif status == "in_progress":
            last_hb = wf.get("last_heartbeat") or wf.get("started_at")
            if last_hb:
                try:
                    stale_secs = _time.time() - datetime.fromisoformat(last_hb).timestamp()
                    if stale_secs > STALE_IN_PROGRESS_SECONDS:
                        issues.append({
                            "name": name, "type": "crashed",
                            "detail": "已 %d 分钟无心跳更新" % (stale_secs / 60),
                        })
                except (ValueError, OSError):
                    pass
        # 检测3: failed 状态
        elif status == "failed":
            issues.append({
                "name": name, "type": "failed",
                "detail": "工作流执行失败",
            })

    if not issues:
        out("[OK] 所有工作流状态正常")
        return 0

    out("\n[问题] 发现 %d 个异常:" % len(issues))
    type_icons = {"interrupted": "[PAUSED]", "crashed": "[CRASH!]", "failed": "[FAIL!]", "paused": "[PAUSED]"}
    for issue in issues:
        icon = type_icons.get(issue["type"], "[?]")
        out("  %s %s — %s" % (icon, issue["name"], issue["detail"]))

    # 修复模式
    if fix:
        fixed = 0
        for issue in issues:
            if issue["type"] in ("crashed", "interrupted", "paused"):
                _mark_workflow_interrupted(issue["name"])
                fixed += 1
                out("  [FIX] %s → interrupted" % issue["name"])
        if fixed:
            out("\n[OK] 已修复 %d 个工作流" % fixed)

    # 恢复模式
    if resume:
        resumable = [i for i in issues if i["type"] in ("interrupted", "crashed", "paused")]
        if resumable:
            out("\n[续传] 恢复 %d 个工作流..." % len(resumable))
            for issue in resumable:
                cmd_execute_workflow(project_name=issue["name"], resume=True)

    # 压缩模式
    if compact:
        # SQLite 压缩
        try:
            result = sqlite_compact_workflow(keep_result_chars=200)
        except Exception:
            result = compact_workflow_db(keep_result_chars=200)
        if result["compacted"] > 0:
            out("\n[压缩] 已压缩 %d 个已完成工作流，释放约 %dKB 数据" % (
                result["compacted"], result["freed_chars"] // 1024))
            out("[压缩] 数据库当前约 %dKB" % (result["remaining_size"] // 1024))
        else:
            out("\n[压缩] 无已完成的工作流需要压缩")

    if not fix and not resume and not compact:
        out("\n[提示] 使用 --fix 将崩溃的工作流标记为 interrupted")
        out("[提示] 使用 --resume 自动恢复中断的工作流")
        out("[提示] 使用 --compact 压缩已完成的工作流数据（减小 workflow.json 体积）")

    return 0


def cmd_workflow_pause(project_name: str) -> int:
    """暂停正在执行的工作流（区别于 interrupted 崩溃中断）"""
    workflows = _load_workflows()
    wf_all = workflows.get("workflows", {})

    if project_name not in wf_all:
        out("[ERROR] 项目 '%s' 无工作流记录" % project_name)
        return 1

    wf = wf_all[project_name]
    if wf.get("status") != "in_progress":
        out("[WARN] 项目 '%s' 当前状态为 %s，无法暂停（仅 in_progress 可暂停）" % (project_name, wf.get("status")))
        return 1

    _mark_workflow_interrupted(project_name)
    # 覆盖 interrupted 为 paused
    workflows = _load_workflows()
    wf = workflows["workflows"][project_name]
    wf["status"] = "paused"
    wf["paused_at"] = datetime.now().isoformat()
    _save_workflow(project_name, wf)
    out("[OK] 项目 '%s' 工作流已暂停" % project_name)
    return 0


def cmd_workflow_resume(project_name: str) -> int:
    """恢复暂停的工作流"""
    workflows = _load_workflows()
    wf_all = workflows.get("workflows", {})

    if project_name not in wf_all:
        out("[ERROR] 项目 '%s' 无工作流记录" % project_name)
        return 1

    wf = wf_all[project_name]
    if wf.get("status") not in ("paused", "interrupted"):
        out("[WARN] 项目 '%s' 当前状态为 %s，无需恢复" % (project_name, wf.get("status")))
        return 1

    return cmd_execute_workflow(project_name=project_name, resume=True)


def _merge_modules(modules: List[Dict], max_modules: int, max_files_per_module: int) -> List[Dict]:
    """当模块数超过上限时，按顺序合并相邻模块"""
    if len(modules) <= max_modules:
        return modules
    
    # 计算需要合并多少次
    merge_count = len(modules) - max_modules
    merged = list(modules)
    
    for _ in range(merge_count):
        # 找文件数最少的相邻模块对进行合并
        best_idx = 0
        best_total = float('inf')
        for i in range(len(merged) - 1):
            total = len(merged[i].get("files", [])) + len(merged[i + 1].get("files", []))
            if total < best_total and total <= max_files_per_module * 2:
                best_total = total
                best_idx = i
        
        # 如果没有满足大小限制的合并对，取最小的相邻对强制合并
        if best_total == float('inf'):
            for i in range(len(merged) - 1):
                total = len(merged[i].get("files", [])) + len(merged[i + 1].get("files", []))
                if total < best_total:
                    best_total = total
                    best_idx = i
        
        # 合并 best_idx 和 best_idx+1
        a = merged[best_idx]
        b = merged[best_idx + 1]
        merged_module = {
            "id": a["id"] + "_" + b["id"],
            "name": a["name"] + " + " + b["name"],
            "description": (a.get("description", "") + "\n" + b.get("description", "")).strip(),
            "files": a.get("files", []) + b.get("files", []),
        }
        merged = merged[:best_idx] + [merged_module] + merged[best_idx + 2:]
    
    return merged


def cmd_execute_workflow(project_name: str = None, start_stage: int = None,
                        execute_all: bool = False, dry_run: bool = False,
                        resume: bool = False) -> int:
    """核心方法：执行项目工作流（支持干跑模式、断点续传和进度估算）"""
    from crewai_scheduler import get_scheduler
    scheduler = get_scheduler()

    init_databases()

    # === 断点续传：检测并恢复中断的工作流 ===
    if resume:
        workflows = _load_workflows()
        wf_all = workflows.get("workflows", {})
        resumable = []
        for name, wf in wf_all.items():
            if wf.get("status") in ("interrupted", "in_progress", "paused"):
                resumable.append((name, wf))
        if not resumable:
            out("[INFO] 未发现可恢复的工作流")
            return 0
        out("[续传] 发现 %d 个可恢复的工作流:" % len(resumable))
        for name, wf in resumable:
            ci = wf.get("current_stage_index", 0) + 1
            ts = wf.get("total_stages", "?")
            st = wf.get("status", "?")
            out("   - %s (状态=%s, 阶段 %d/%s)" % (name, st, ci, ts))
        # 恢复第一个（或指定的）
        if project_name:
            resumable = [(n, w) for n, w in resumable if n == project_name]
            if not resumable:
                out("[ERROR] 项目 '%s' 不在可恢复列表中" % project_name)
                return 1
        # 将 interrupted → in_progress（允许继续执行）
        for name, wf in resumable:
            if wf.get("status") in ("interrupted", "paused"):
                wf["status"] = "in_progress"
                current_sid = wf.get("current_stage_id")
                if current_sid and current_sid in wf.get("stages", {}):
                    wf["stages"][current_sid]["status"] = "pending"
                out("[续传] 恢复项目: %s (从阶段 %d 继续)" % (
                    name, wf.get("current_stage_index", 0) + 1))
                _save_workflow(name, wf)
        if not project_name:
            project_name = resumable[0][0]
        out("")

    projects = _load_projects()
    workflows = _load_workflows()
    wf_all = workflows.get("workflows", {})

    if execute_all:
        target_projects = []
        for pname, proj in projects.get("projects", {}).items():
            wf = wf_all.get(pname)
            if wf and wf.get("status") in ("ready", "in_progress"):
                target_projects.append((pname, proj, wf))
        if not target_projects:
            out("[INFO] 暂无待处理的工作流项目")
            return 0
        target_projects.sort(key=lambda x: x[1].get("created_at", ""))
        out("[工作流] 发现 %d 个项目:" % len(target_projects))
        for pname, proj, wf in target_projects:
            idx = wf.get("current_stage_index", 0) + 1
            total = wf.get("total_stages", "?")
            out("   - %s (阶段 %d/%s)" % (pname, idx, total))
        out("")
    elif project_name:
        if project_name not in wf_all:
            out("[ERROR] 项目 '%s' 无工作流记录" % project_name)
            return 1
        proj = projects["projects"].get(project_name)
        if not proj:
            out("[ERROR] 项目 '%s' 不存在" % project_name)
            return 1
        wf = wf_all[project_name]
        target_projects = [(project_name, proj, wf)]
    else:
        target_projects = []
        for pname, proj in projects.get("projects", {}).items():
            wf = wf_all.get(pname)
            if wf and wf.get("status") in ("ready", "in_progress"):
                target_projects.append((pname, proj, wf))
        if not target_projects:
            out("[INFO] 暂无待处理的工作流项目")
            return 0
        target_projects.sort(key=lambda x: x[1].get("created_at", ""))
        target_projects = [target_projects[0]]
        out("[工作流] 自动选择: %s" % target_projects[0][0])

    total_success = 0
    total_fail = 0

    for p_name, p_proj, p_wf in target_projects:
        out("\n" + "#" * 70)
        out("# Project: %s" % p_name)
        out("#" * 70)

        department = p_proj.get("department", "技术部")
        stages_def = scheduler.get_workflow_stages(department)

        if not stages_def:
            out("[WARN] 部门 '%s' 无工作流定义，跳过" % department)
            continue

        workflows = _load_workflows()
        wf = workflows["workflows"][p_name]

        if start_stage is not None:
            start_idx = start_stage - 1
            if start_idx < 0 or start_idx >= len(stages_def):
                out("[ERROR] 阶段编号无效: %d，有效范围 1-%d" % (start_stage, len(stages_def)))
                total_fail += 1
                continue
            wf["current_stage_index"] = start_idx
            wf["current_stage_id"] = stages_def[start_idx]["id"]
            out("[INFO] 从阶段 %d (%s) 开始" % (start_stage, stages_def[start_idx]["name"]))
            start_stage = None  # 仅对第一个项目生效

        if wf.get("status") == "ready":
            wf["status"] = "in_progress"
            wf["started_at"] = datetime.now().isoformat()
            wf["last_heartbeat"] = datetime.now().isoformat()

        _save_workflow(p_name, wf)

        current_idx = wf["current_stage_index"]

        while current_idx < len(stages_def):
            # 检查中断信号
            if is_interrupted():
                out("\n[WARN] 收到中断信号，保存当前进度后退出...")
                _mark_workflow_interrupted(p_name)
                total_fail += 1
                break

            stage = stages_def[current_idx]
            stage_id = stage["id"]
            stage_name = stage["name"]

            # === 进度估算 ===
            elapsed_stages = [wf["stages"][s["id"]] for s in stages_def[:current_idx]
                              if wf["stages"].get(s["id"], {}).get("duration_seconds")]
            if elapsed_stages:
                avg_dur = sum(s["duration_seconds"] for s in elapsed_stages) / len(elapsed_stages)
                remaining = len(stages_def) - current_idx
                eta_secs = avg_dur * remaining
                eta_mins = eta_secs / 60
                out("  [进度] 阶段 %d/%d | 已完成平均耗时 %.1fs | 预计剩余 %.0f 分钟" % (
                    current_idx + 1, len(stages_def), avg_dur, eta_mins))

            # === 干跑模式 ===
            if dry_run:
                out("  [DRY-RUN] 将执行阶段: %s (%s) — 跳过API调用" % (stage_name, stage_id))
                current_idx += 1
                wf["current_stage_index"] = current_idx
                if current_idx < len(stages_def):
                    wf["current_stage_id"] = stages_def[current_idx]["id"]
                continue

            # Stage delay to avoid rate limiting (skip for first stage)
            if current_idx > 0:
                delay = STAGE_DELAY_SECONDS
                out("  [延迟] 等待 %ds 后继续下个 API 调用..." % delay)
                _time.sleep(delay)

            workflows = _load_workflows()
            wf = workflows["workflows"][p_name]

            out("\n" + "-" * 60)
            out("[Stage %d/%d] %s" % (current_idx + 1, len(stages_def), stage_name))
            out("  Agent: %s" % stage["agent"])
            out("-" * 60)

            previous_outputs = {}
            for prev_i in range(current_idx):
                psid = stages_def[prev_i]["id"]
                pd = wf.get("stages", {}).get(psid, {})
                pr = pd.get("result")
                if pr:
                    previous_outputs[psid] = _load_stage_output(p_name, pr)

            project_desc = p_proj.get("description", p_name) or p_name

            # 代码审查/测试阶段：注入项目目录中的实际代码（而非依赖开发阶段的文本输出）
            if stage_id in ("code_review", "testing") and CODE_EXTRACTOR_AVAILABLE:
                # 读取代码审查的上下文限制配置
                dept_wf_tmp = scheduler.config.get("workflow", {}).get(department, {})
                modular_cfg_tmp = dept_wf_tmp.get("modular_development", {})
                ctx_limits_tmp = modular_cfg_tmp.get("context_limits", {})
                review_chars_limit = ctx_limits_tmp.get("code_review_code_chars", 30000)

                try:
                    writer_tmp = create_project_writer()
                    proj_path = writer_tmp._get_project_path(p_name)
                    if os.path.isdir(proj_path):
                        code_parts = []
                        file_records = _walk_project_files(proj_path, CODE_REVIEW_EXTENSIONS, skip_stages_dir=True)
                        for rel, content, ext in file_records:
                            code_parts.append("\n### 文件: %s\n```%s\n%s\n```" % (rel, ext, content))
                            if sum(len(p) for p in code_parts) > review_chars_limit:
                                break
                        file_count = len(code_parts)
                        if code_parts:
                            # 限制总大小，避免超出上下文
                            code_text = "\n".join(code_parts)
                            if len(code_text) > review_chars_limit:
                                code_text = code_text[:review_chars_limit] + "\n...(代码过长已截断，共 %d 个文件)" % file_count
                            previous_outputs["development"] = "## 项目代码（%d 个文件）\n%s" % (file_count, code_text)
                            out("  [CONTEXT] 注入项目代码 %d 个文件到上下文" % file_count)
                except Exception as e:
                    out("  [WARN] 代码注入失败: %s" % str(e)[:60])

            # 判断是否为开发阶段（使用 Function Calling）
            use_function_calling = (stage_id == "development" and CODE_EXTRACTOR_AVAILABLE)
            sub_tasks = []  # 模块化开发的子任务记录

            if use_function_calling:
                # === Function Calling 模式（支持模块化开发）===
                from crewai_scheduler import WRITE_FILE_TOOL

                # 创建项目目录
                writer = create_project_writer()
                project_path = writer.create_project_directory(p_name)

                # === 阶段内检查点 ===
                # 读取本阶段之前的检查点（失败重试时恢复）
                sr_checkpoint = wf.get("stages", {}).get(stage_id, {})
                checkpoint_files = sr_checkpoint.get("checkpoint_files", [])

                # 构建检查点上下文：告知 LLM 哪些文件已完成
                checkpoint_context = ""
                if checkpoint_files:
                    completed_list = "\n".join("- %s" % f for f in checkpoint_files)
                    checkpoint_context = (
                        "\n## 已完成的文件（请勿重复编写，继续编写剩余文件）\n%s\n\n"
                        "注意：以上文件已在上一轮尝试中成功写入，请只编写尚未完成的文件。" % completed_list
                    )
                    out("  [CHECKPOINT] 发现 %d 个已完成文件的检查点，将从中断处继续" % len(checkpoint_files))

                # 当前轮次新写入的文件（用于更新检查点）
                current_round_files = []

                def _on_tool_call(func_name, func_args):
                    """处理 write_file 工具调用 — 实时写入文件 + 检查点记录"""
                    nonlocal current_round_files
                    if func_name == "write_file":
                        file_path = func_args.get("path", "")
                        file_content = func_args.get("content", "")
                        if file_path and file_content:
                            # 检查点：跳过已完成的文件
                            if file_path in checkpoint_files:
                                return "文件 %s 已在上一轮写入，已跳过" % file_path
                            target_path = os.path.join(project_path, file_path)
                            # 路径遍历检查：先检查 .. 组件和绝对路径
                            norm_fp = os.path.normpath(file_path)
                            if norm_fp.startswith('..') or os.path.isabs(norm_fp):
                                return "错误: 路径 '%s' 包含非法组件，不允许写入" % file_path
                            # 路径遍历检查：确保实际路径在项目目录内（Windows 大小写不敏感）
                            real_target = os.path.realpath(target_path)
                            real_project = os.path.realpath(project_path)
                            if not (os.path.normcase(real_target).startswith(os.path.normcase(real_project + os.sep))
                                    or os.path.normcase(real_target) == os.path.normcase(real_project)):
                                return "错误: 路径 '%s' 超出项目目录，不允许写入" % file_path
                            parent_dir = os.path.dirname(target_path)
                            if parent_dir:
                                os.makedirs(parent_dir, exist_ok=True)
                            with open(target_path, 'w', encoding='utf-8') as f:
                                f.write(file_content)
                            out("  [WRITE] %s (%d chars)" % (file_path, len(file_content)))
                            # === 检查点：记录已写入文件 ===
                            current_round_files.append(file_path)
                            try:
                                wf_cp = _load_workflows()["workflows"][p_name]
                                sr_cp = wf_cp["stages"][stage_id]
                                cp = sr_cp.get("checkpoint_files", [])
                                if file_path not in cp:
                                    cp.append(file_path)
                                sr_cp["checkpoint_files"] = cp
                                sr_cp["last_heartbeat"] = datetime.now().isoformat()
                                _save_workflow(p_name, wf_cp)
                            except Exception:
                                pass
                            return "文件 %s 已成功写入 (%d 字符)" % (file_path, len(file_content))
                        return "错误: 缺少 path 或 content 参数"
                    return "OK"

                # === 解析模块化开发配置 ===
                dept_workflow = scheduler.config.get("workflow", {}).get(department, {})
                modular_cfg = dept_workflow.get("modular_development", {})
                module_mode = modular_cfg.get("mode", "auto")       # auto / always / never
                max_files_per_module = modular_cfg.get("max_files_per_module", 8)
                max_modules_limit = modular_cfg.get("max_modules", 10)
                min_files_to_split = modular_cfg.get("min_files_to_split", 10)
                parallel_modules = modular_cfg.get("parallel", False)
                ctx_limits = modular_cfg.get("context_limits", {})
                arch_chars = ctx_limits.get("architecture_overview_chars", 2000)
                design_chars = ctx_limits.get("module_design_chars", 3000)
                review_chars = ctx_limits.get("code_review_code_chars", 30000)

                # === 解析模块列表 ===
                design_output = previous_outputs.get("detailed_design", "")
                modules = []
                enable_modular = (module_mode != "never")  # never 模式下跳过模块化

                if enable_modular and CODE_EXTRACTOR_AVAILABLE and design_output:
                    try:
                        modules = parse_modules_from_design(design_output)
                        # 应用配置限制
                        if modules and len(modules) > max_modules_limit:
                            out("  [MODULE] 模块数 %d 超过上限 %d，自动合并" % (len(modules), max_modules_limit))
                            modules = _merge_modules(modules, max_modules_limit, max_files_per_module)
                        if modules:
                            out("  [MODULE] 检测到 %d 个开发模块:" % len(modules))
                            for mi, m in enumerate(modules):
                                out("    %d. %s (%s) - %d files" % (mi + 1, m["name"], m["id"], len(m.get("files", []))))
                    except Exception as e:
                        out("  [WARN] 模块解析失败，使用单次开发: %s" % str(e)[:60])
                        modules = []

                # auto 模式：小项目不拆模块
                if module_mode == "auto" and modules:
                    total_files = sum(len(m.get("files", [])) for m in modules)
                    if total_files <= min_files_to_split:
                        out("  [MODULE] 项目文件数 %d <= %d，跳过模块化开发" % (total_files, min_files_to_split))
                        modules = []

                # === 按模块执行开发 ===
                all_files_written = []
                dev_success = True

                if modules and len(modules) > 0:
                    # --- 模块化开发 ---
                    arch_output = previous_outputs.get("architecture", "")

                    def _execute_one_module(mi: int, module: Dict) -> Dict:
                        """执行单个模块开发（供串行/并行调用）"""
                        mid = module.get("id", "module_%d" % mi)
                        mname = module.get("name", mid)
                        mfiles = module.get("files", [])

                        out("\n  [MODULE %d/%d] %s (%d target files)" % (mi + 1, len(modules), mname, len(mfiles)))

                        # 构建模块专用上下文
                        module_context_parts = []
                        if arch_output:
                            module_context_parts.append("## 项目架构概览\n%s" % arch_output[:arch_chars])
                        if CODE_EXTRACTOR_AVAILABLE:
                            module_design = extract_module_design_section(design_output, module)
                        else:
                            module_design = module.get("description", "")
                        module_context_parts.append("## 当前模块设计: %s\n%s" % (mname, module_design[:design_chars]))
                        if mfiles:
                            module_context_parts.append("## 需要编写的文件\n%s" % "\n".join("- " + f for f in mfiles))
                        # 并行模式下跳过跨模块依赖传递（文件可能尚未写入完成）
                        if not parallel_modules:
                            exports_summary = extract_exports_summary(project_path)
                            if exports_summary:
                                module_context_parts.append(exports_summary)
                        # 注入检查点上下文
                        if checkpoint_context:
                            module_context_parts.append(checkpoint_context)

                        module_context = "\n\n".join(module_context_parts)

                        # 执行该模块的开发
                        module_result = _call_with_retry(
                            fn=lambda ctx=module_context, _mid=mid: scheduler.execute_stage_with_tools(
                                stage=stage,
                                project_desc=project_desc,
                                stage_context=ctx,
                                previous_outputs={},
                                project_id="%s/%s" % (p_name, _mid),
                                tools=[WRITE_FILE_TOOL],
                                on_tool_call=_on_tool_call,
                            ),
                        )

                        module_files = module_result.get("files_written", []) if module_result else []
                        success = module_result and module_result.get("success", False)
                        duration = module_result.get("duration_seconds", 0) if module_result else 0

                        if success:
                            out("  [MODULE] %s done (%d files, %.1fs)" % (mname, len(module_files), duration))
                        else:
                            out("  [MODULE] %s FAILED" % mname)

                        return {
                            "id": mid,
                            "name": mname,
                            "status": "completed" if success else "failed",
                            "files_written": len(module_files),
                            "duration_seconds": duration,
                            "_files": module_files,
                            "_success": success,
                        }

                    # === 串行 or 并行执行 ===
                    if parallel_modules and len(modules) > 1:
                        from concurrent.futures import ThreadPoolExecutor, as_completed
                        out("  [MODULE] 并行模式: %d 个模块同时执行" % len(modules))
                        with ThreadPoolExecutor(max_workers=min(len(modules), 3)) as executor:
                            futures = {executor.submit(_execute_one_module, mi, m): mi
                                       for mi, m in enumerate(modules)}
                            for future in as_completed(futures):
                                task = future.result()
                                all_files_written.extend(task.pop("_files", []))
                                if not task.pop("_success", True):
                                    dev_success = False
                                sub_tasks.append(task)
                    else:
                        # 串行执行（默认）
                        for mi, module in enumerate(modules):
                            task = _execute_one_module(mi, module)
                            all_files_written.extend(task.pop("_files", []))
                            if not task.pop("_success", True):
                                dev_success = False
                            sub_tasks.append(task)
                            # === 模块级检查点：每完成一个模块立即保存进度 ===
                            workflows = _load_workflows()
                            wf = workflows["workflows"][p_name]
                            sr = wf["stages"][stage_id]
                            sr["sub_tasks"] = sub_tasks
                            wf["last_heartbeat"] = datetime.now().isoformat()
                            _save_workflow(p_name, wf)
                            # 模块间短暂延迟，避免速率限制
                            if mi < len(modules) - 1:
                                _time.sleep(MODULE_DELAY_SECONDS)

                    # 汇总结果
                    total_module_files = sum(st["files_written"] for st in sub_tasks)
                    result = {
                        "success": dev_success,
                        "result": "模块化开发完成: %d 个模块, %d 个文件" % (len(modules), total_module_files),
                        "stage_id": stage_id,
                        "stage_name": stage_name,
                        "agent": stage["agent"],
                        "duration_seconds": sum(st["duration_seconds"] for st in sub_tasks),
                        "rejected": False,
                        "reject_reason": "",
                        "files_written": all_files_written,
                    }
                    out("  [FILES] 模块化开发共写入 %d 个文件" % len(all_files_written))
                    for fw in all_files_written:
                        out("    - %s (%d chars)" % (fw["path"], fw["size"]))
                else:
                    # --- 单次开发（向后兼容 / 小项目）---
                    _dev_prev_outputs = previous_outputs  # 可变引用

                    def _do_dev_compress():
                        """单次开发模式下上下文超限时的压缩（使用结构化摘要）"""
                        nonlocal _dev_prev_outputs
                        from crewai_scheduler import get_scheduler as _get_sched
                        sched = _get_sched()
                        # 逐轮压缩：使用结构化摘要提取
                        for sid, text in list(_dev_prev_outputs.items()):
                            if len(text) > 500:
                                _dev_prev_outputs[sid] = sched._extract_structured_summary(text, sid)
                        # 清除压缩缓存，因为输入变了
                        sched._compress_cache.clear()
                        out("  [CONTEXT] 上下文超限，使用结构化摘要压缩历史输出后重试")

                    result = _call_with_context_compress(
                        fn=lambda: scheduler.execute_stage_with_tools(
                            stage=stage,
                            project_desc=project_desc,
                            stage_context=checkpoint_context,
                            previous_outputs=_dev_prev_outputs,
                            project_id=p_name,
                            tools=[WRITE_FILE_TOOL],
                            on_tool_call=_on_tool_call,
                        ),
                        compress_fn=_do_dev_compress,
                    )

                    # 汇总文件写入情况
                    files_written = result.get("files_written", [])
                    if files_written:
                        out("  [FILES] 通过 Function Calling 写入 %d 个文件" % len(files_written))
                        for fw in files_written:
                            out("    - %s (%d chars)" % (fw["path"], fw["size"]))
            else:
                # === 普通模式（原有逻辑）===
                # 使用带上下文压缩的重试：超限时自动压缩 previous_outputs 后重试
                _compress_prev_outputs = previous_outputs  # 可变引用，压缩函数会修改它

                # === 非开发阶段检查点：注入之前失败的结果 ===
                sr_checkpoint = wf.get("stages", {}).get(stage_id, {})
                checkpoint_prev_result = sr_checkpoint.get("checkpoint_prev_result")
                _stage_context = ""
                if checkpoint_prev_result:
                    # 之前有失败的结果，告知 LLM 之前完成了什么
                    prev_preview = checkpoint_prev_result[:2000]
                    _stage_context = (
                        "\n## 之前的尝试结果（你可能已经完成了部分工作，请基于此继续）\n%s\n\n"
                        "注意：以上是之前失败的尝试产生的结果。请检查并完善，不要从头开始。" % prev_preview
                    )
                    out("  [CHECKPOINT] 发现之前失败的尝试结果，将从中断处继续")

                def _do_compress():
                    """上下文超限时压缩 previous_outputs（使用结构化摘要）"""
                    nonlocal _compress_prev_outputs
                    from crewai_scheduler import get_scheduler as _get_sched
                    sched = _get_sched()
                    # 使用结构化摘要提取，保留关键信息
                    for sid, text in list(_compress_prev_outputs.items()):
                        if len(text) > 500:
                            _compress_prev_outputs[sid] = sched._extract_structured_summary(text, sid)
                    # 清除压缩缓存
                    sched._compress_cache.clear()
                    out("  [CONTEXT] 上下文超限，使用结构化摘要压缩历史输出后重试")

                result = _call_with_context_compress(
                    fn=lambda: scheduler.execute_stage(
                        stage=stage,
                        project_desc=project_desc,
                        stage_context=_stage_context,
                        previous_outputs=_compress_prev_outputs,
                        project_id=p_name,
                    ),
                    compress_fn=_do_compress,
                )

            # 防护：result 为 None 时提供默认值
            if result is None:
                result = {"success": False, "result": "未知错误: 执行无返回结果",
                          "duration_seconds": 0, "rejected": False, "reject_reason": ""}

            # 重新加载 wf，确保 _on_tool_call 中的检查点更新不会丢失
            workflows = _load_workflows()
            wf = workflows["workflows"][p_name]

            sr = wf["stages"][stage_id]
            ok = result["success"]
            sr["status"] = "completed" if ok else "failed"
            sr["result"] = _save_stage_output(p_name, stage_id, result["result"])
            sr["completed_at"] = datetime.now().isoformat()
            sr["duration_seconds"] = result["duration_seconds"]

            # 更新心跳时间（用于崩溃检测）
            wf["last_heartbeat"] = datetime.now().isoformat()

            # 保存模块化开发的子任务信息
            if use_function_calling and sub_tasks:
                sr["sub_tasks"] = sub_tasks

            # 阶段成功完成：清除检查点（不再需要）
            # 阶段失败：保留检查点（下次重试时恢复）
            if ok:
                sr.pop("checkpoint_files", None)
                sr.pop("checkpoint_prev_result", None)
                out("  [CHECKPOINT] 清除检查点（阶段已完成）")
                # 自动压缩已完成阶段的 result（防止 JSON 膨胀）
                _compact_completed_stages(p_name, wf, stage_id)

            if ok:
                out("  Done (%.1fs)" % result["duration_seconds"])
                rt = result["result"]
                if rt:
                    pv = rt[:300].replace("\n", " ")
                    out("  Output: %s..." % pv)
                    if len(rt) > 300:
                        out("  (Full: %d chars)" % len(rt))

                    # === 代码写入 ===
                    # Function Calling 模式：文件已在生成时实时写入，无需再提取
                    # 非 development 阶段（如 architecture/detailed_design 可能含代码）：尝试提取
                    if not use_function_calling and stage_id in ("development", "architecture", "detailed_design") and CODE_EXTRACTOR_AVAILABLE:
                        try:
                            extractor = CodeExtractor()
                            code_files = extractor.extract(rt)
                            if code_files:
                                out("  [EXTRACT] 检测到 %d 个代码文件" % len(code_files))
                                writer = create_project_writer()
                                written = writer.write_files(p_name, code_files)
                                out("  [WRITE] 已写入 project/%s/ (%d files)" % (p_name, len(written)))
                        except Exception as e:
                            out("  [WARN] 代码提取失败: %s" % str(e)[:80])

                if result["rejected"]:
                    out("  REJECTED!")
                    rr = result.get("reject_reason", "")
                    if rr:
                        out("  Reason: %s" % rr)

                    cfg_max_retries = scheduler.get_max_retries(department)
                    current_retry_count = sr.get("retry_count", 0)

                    if current_retry_count >= cfg_max_retries:
                        out("  [FORCE PASS] Max retries (%d) reached, forcing pass" % cfg_max_retries)
                        sr["status"] = "completed"
                        sr["force_passed"] = True
                        current_idx += 1
                        wf["current_stage_index"] = current_idx
                        if current_idx < len(stages_def):
                            wf["current_stage_id"] = stages_def[current_idx]["id"]
                    else:
                        rtarget = scheduler.get_retry_target(department, stage_id)
                        if rtarget:
                            ridx = None
                            for ri2, rs2 in enumerate(stages_def):
                                if rs2["id"] == rtarget:
                                    ridx = ri2
                                    break
                            if ridx is not None:
                                out("  Rollback to stage %d: %s (retry %d/%d)" % (ridx + 1, rtarget, current_retry_count + 1, cfg_max_retries))
                                sr["status"] = "rejected"
                                sr["retry_count"] = current_retry_count + 1
                                for ri3 in range(ridx, current_idx + 1):
                                    rid = stages_def[ri3]["id"]
                                    rsd = wf["stages"][rid]
                                    if rsd.get("result"):
                                        hist = rsd.get("history", [])
                                        hist.append({
                                            "attempt": len(hist) + 1,
                                            "result": rsd["result"],
                                            "completed_at": rsd.get("completed_at"),
                                            "duration_seconds": rsd.get("duration_seconds"),
                                        })
                                        rsd["history"] = hist
                                    rsd["status"] = "pending"
                                    rsd["result"] = None
                                    rsd["completed_at"] = None
                                    rsd["duration_seconds"] = None
                                    # 清除检查点（回退后从头开始）
                                    rsd.pop("checkpoint_files", None)
                                    rsd.pop("checkpoint_prev_result", None)
                                current_idx = ridx
                                wf["current_stage_index"] = current_idx
                                wf["current_stage_id"] = stages_def[current_idx]["id"]
                                _save_workflow(p_name, wf)
                                continue

                        out("  Cannot rollback, next stage")
                        current_idx += 1
                        wf["current_stage_index"] = current_idx
                        if current_idx < len(stages_def):
                            wf["current_stage_id"] = stages_def[current_idx]["id"]
                else:
                    current_idx += 1
                    wf["current_stage_index"] = current_idx
                    if current_idx < len(stages_def):
                        wf["current_stage_id"] = stages_def[current_idx]["id"]
            else:
                out("  FAILED: %s" % str(result["result"])[:100])
                sr["status"] = "failed"
                wf["status"] = "failed"
                # 保存检查点：开发阶段保存文件列表，其他阶段保存之前的尝试结果
                cp_files = sr.get("checkpoint_files", [])
                if cp_files:
                    out("  [CHECKPOINT] 已保存 %d 个已写入文件的检查点，重试时将从中断处继续" % len(cp_files))
                # 非开发阶段：保存失败的 result 作为检查点
                if not use_function_calling and result.get("result"):
                    prev_result_text = result["result"]
                    # 限制大小，避免检查点本身也太大
                    if len(prev_result_text) > 5000:
                        prev_result_text = prev_result_text[:5000] + "\n...(检查点截断)"
                    sr["checkpoint_prev_result"] = prev_result_text
                    out("  [CHECKPOINT] 已保存之前的尝试结果，重试时将基于此继续")
                _save_workflow(p_name, wf)
                total_fail += 1
                break

            _save_workflow(p_name, wf)

        if current_idx >= len(stages_def):
            wf["status"] = "completed"
            wf["completed_at"] = datetime.now().isoformat()
            stage_results = {}
            for sid2, sd2 in wf.get("stages", {}).items():
                if sd2.get("result"):
                    stage_results[sid2] = sd2["result"]
            wf["summary"] = "Done: %s, %d stages" % (p_name, len(stages_def))
            # === 工作流完成后压缩所有 result（不再需要引用） ===
            for sid2, sd2 in wf.get("stages", {}).items():
                result = sd2.get("result", "")
                # 只压缩非文件引用且很长的 result
                if result and len(result) > 2000 and not result.startswith("file:"):
                    sd2["result"] = result[:2000] + "\n...(已压缩，原长度 %d 字符)" % len(result)
            _save_workflow(p_name, wf)
            out("\n" + "#" * 60)
            out("# DONE: %s" % p_name)
            out("#" * 60)
            total_success += 1

            # === 生成完整项目文档 ===
            if CODE_EXTRACTOR_AVAILABLE:
                try:
                    out("\n  [PROJECT] 生成项目文档...")
                    writer = create_project_writer()

                    # 收集代码文件：从已写入的项目目录扫描 + 从非 development 阶段提取
                    all_code_files = []

                    # 1. 扫描项目目录中已有的文件（Function Calling 实时写入的）
                    project_path = writer._get_project_path(p_name)
                    if os.path.exists(project_path):
                        for rel_path, content, ext in _walk_project_files(project_path, skip_stages_dir=True):
                            all_code_files.append(CodeFile(
                                path=rel_path,
                                content=content,
                                language=ext
                            ))

                    # 2. 从非 development 阶段提取代码（architecture/detailed_design 可能含代码）
                    for sid2, sd2 in wf.get("stages", {}).items():
                        result_text = sd2.get("result", "")
                        if result_text and sid2 in ["architecture", "detailed_design"]:
                            try:
                                extractor = CodeExtractor()
                                files = extractor.extract(result_text)
                                all_code_files.extend(files)
                            except Exception as e:
                                log().warning("阶段 %s 代码提取失败: %s" % (sid2, e))

                    # 去重：相同路径保留内容最长的
                    seen = {}
                    for f in all_code_files:
                        if f.path in seen:
                            if len(f.content) > len(seen[f.path].content):
                                seen[f.path] = f
                        else:
                            seen[f.path] = f
                    unique_files = list(seen.values())

                    # 生成完整项目（代码文件已存在，主要生成 README 和阶段文档）
                    proj_result = writer.write_complete_project(
                        project_name=p_name,
                        description=p_proj.get("description", ""),
                        stages_output=stage_results,
                        code_files=unique_files
                    )

                    out("  [PROJECT] 项目路径: %s" % proj_result['project_path'])
                    out("  [PROJECT] 文件数量: %d" % proj_result['file_count'])
                    if proj_result.get('readme_path'):
                        out("  [PROJECT] README: %s" % os.path.basename(proj_result['readme_path']))
                except Exception as e:
                    out("  [WARN] 项目文档生成失败: %s" % str(e)[:80])

    out("\n" + "=" * 60)
    out("[SUMMARY] OK=%d FAIL=%d" % (total_success, total_fail))
    out("=" * 60)

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    try:
        _sys.exit(main())
    finally:
        close_logging()
