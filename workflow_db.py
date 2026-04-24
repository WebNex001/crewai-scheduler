"""
SQLite 工作流数据库 — 替代 workflow.json 单文件存储

优势：
- 原子事务（无 .tmp/.backup 之舞）
- 按需查询（只加载需要的数据）
- 索引加速（按状态/项目名查询）
- 并发安全（SQLite 内置锁）
- 自动迁移（首次运行从 workflow.json 导入）
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any

from scheduler_log import init_logging

_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        _logger = init_logging()
    return _logger


# 数据库版本号，用于未来 schema 迁移
DB_VERSION = 1


def _get_db_path() -> str:
    """获取数据库文件路径"""
    try:
        from __main__ import DATA_DIR
        return os.path.join(DATA_DIR, "scheduler.db")
    except ImportError:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "scheduler.db")


def _connect() -> sqlite3.Connection:
    """获取数据库连接（启用 WAL 模式提升并发）"""
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")       # WAL 模式：读写不互斥
    conn.execute("PRAGMA synchronous=NORMAL")      # 平衡安全与性能
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _init_schema(conn: sqlite3.Connection):
    """初始化数据库表结构"""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS db_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS workflows (
            project_name TEXT PRIMARY KEY,
            department TEXT NOT NULL DEFAULT '技术部',
            status TEXT NOT NULL DEFAULT 'ready',
            current_stage_index INTEGER NOT NULL DEFAULT 0,
            current_stage_id TEXT,
            total_stages INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            interrupted_at TEXT,
            paused_at TEXT,
            last_heartbeat TEXT,
            summary TEXT,
            -- 压缩后的完整数据 JSON（用于向后兼容读取）
            raw_json TEXT
        );

        CREATE TABLE IF NOT EXISTS workflow_stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            stage_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            agent TEXT,
            result TEXT,
            completed_at TEXT,
            duration_seconds REAL,
            retry_count INTEGER NOT NULL DEFAULT 0,
            force_passed INTEGER NOT NULL DEFAULT 0,
            sub_tasks_json TEXT,
            extra_json TEXT,
            UNIQUE(project_name, stage_id),
            FOREIGN KEY (project_name) REFERENCES workflows(project_name) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS workflow_stage_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            stage_id TEXT NOT NULL,
            attempt INTEGER NOT NULL,
            result TEXT,
            completed_at TEXT,
            duration_seconds REAL,
            FOREIGN KEY (project_name) REFERENCES workflows(project_name) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS projects (
            name TEXT PRIMARY KEY,
            description TEXT DEFAULT '',
            department TEXT DEFAULT '技术部',
            created_at TEXT,
            status TEXT DEFAULT 'active'
        );

        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            stage_id TEXT,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            recorded_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);
        CREATE INDEX IF NOT EXISTS idx_stages_project ON workflow_stages(project_name);
        CREATE INDEX IF NOT EXISTS idx_history_project_stage ON workflow_stage_history(project_name, stage_id);
        CREATE INDEX IF NOT EXISTS idx_token_usage_project ON token_usage(project_name);
    """)
    conn.execute("INSERT OR IGNORE INTO db_meta (key, value) VALUES ('version', ?)", (str(DB_VERSION),))
    conn.commit()

    # === 增量迁移：添加 extra_json 列 ===
    try:
        conn.execute("ALTER TABLE workflow_stages ADD COLUMN extra_json TEXT")
        conn.commit()
    except Exception:
        pass  # 列已存在，忽略


# ==================== 初始化 & 迁移 ====================

_initialized = False


def ensure_db():
    """确保数据库已初始化（幂等）"""
    global _initialized
    conn = _connect()
    try:
        _init_schema(conn)
        if not _initialized:
            _migrate_from_json(conn)
            _initialized = True
    finally:
        conn.close()


def _migrate_from_json(conn: sqlite3.Connection):
    """从 workflow.json / projects.json 迁移数据到 SQLite（仅首次运行）"""
    # 检查是否已有数据
    count = conn.execute("SELECT COUNT(*) FROM workflows").fetchone()[0]
    if count > 0:
        return  # 已有数据，不重复迁移

    # 迁移 projects.json
    try:
        from db import PROJECTS_DB
        from db import _get_data_dir
        proj_path = os.path.join(_get_data_dir(), PROJECTS_DB)
        if os.path.exists(proj_path):
            with open(proj_path, 'r', encoding='utf-8') as f:
                proj_data = json.load(f)
            for name, proj in proj_data.get("projects", {}).items():
                conn.execute(
                    "INSERT OR IGNORE INTO projects (name, description, department, created_at, status) VALUES (?,?,?,?,?)",
                    (name, proj.get("description", ""), proj.get("department", "技术部"),
                     proj.get("created_at"), proj.get("status", "active"))
                )
    except Exception as e:
        _get_logger().debug("迁移 projects.json 跳过: %s" % e)

    # 迁移 workflow.json
    try:
        from db import WORKFLOW_DB
        from db import _get_data_dir
        wf_path = os.path.join(_get_data_dir(), WORKFLOW_DB)
        if os.path.exists(wf_path):
            with open(wf_path, 'r', encoding='utf-8') as f:
                wf_data = json.load(f)
            for name, wf in wf_data.get("workflows", {}).items():
                # 插入工作流主记录
                conn.execute("""
                    INSERT OR IGNORE INTO workflows
                    (project_name, department, status, current_stage_index, current_stage_id,
                     total_stages, created_at, started_at, completed_at, interrupted_at,
                     paused_at, last_heartbeat, summary)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    name, wf.get("department", "技术部"), wf.get("status", "ready"),
                    wf.get("current_stage_index", 0), wf.get("current_stage_id"),
                    wf.get("total_stages", 0), wf.get("created_at"), wf.get("started_at"),
                    wf.get("completed_at"), wf.get("interrupted_at"), wf.get("paused_at"),
                    wf.get("last_heartbeat"), wf.get("summary"),
                ))
                # 插入阶段记录
                for sid, sd in wf.get("stages", {}).items():
                    sub_tasks = sd.get("sub_tasks")
                    conn.execute("""
                        INSERT OR IGNORE INTO workflow_stages
                        (project_name, stage_id, status, agent, result, completed_at,
                         duration_seconds, retry_count, force_passed, sub_tasks_json)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (
                        name, sid, sd.get("status", "pending"), sd.get("agent"),
                        sd.get("result"), sd.get("completed_at"),
                        sd.get("duration_seconds"), sd.get("retry_count", 0),
                        1 if sd.get("force_passed") else 0,
                        json.dumps(sub_tasks, ensure_ascii=False) if sub_tasks else None,
                    ))
                    # 插入历史记录
                    for h in sd.get("history", []):
                        conn.execute("""
                            INSERT INTO workflow_stage_history
                            (project_name, stage_id, attempt, result, completed_at, duration_seconds)
                            VALUES (?,?,?,?,?,?)
                        """, (
                            name, sid, h.get("attempt", 0), h.get("result"),
                            h.get("completed_at"), h.get("duration_seconds"),
                        ))
            conn.commit()
            _get_logger().info("从 workflow.json 迁移了 %d 个工作流到 SQLite" % len(wf_data.get("workflows", {})))
    except Exception as e:
        _get_logger().debug("迁移 workflow.json 跳过: %s" % e)


# ==================== 工作流 CRUD ====================

def load_workflow(project_name: str) -> Optional[Dict]:
    """加载单个工作流（含阶段、历史），返回与原 workflow.json 兼容的 dict"""
    ensure_db()
    conn = _connect()
    try:
        row = conn.execute("SELECT * FROM workflows WHERE project_name = ?", (project_name,)).fetchone()
        if not row:
            return None

        wf = {
            "project": row["project_name"],
            "department": row["department"],
            "status": row["status"],
            "current_stage_index": row["current_stage_index"],
            "current_stage_id": row["current_stage_id"],
            "total_stages": row["total_stages"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "interrupted_at": row["interrupted_at"],
            "paused_at": row["paused_at"],
            "last_heartbeat": row["last_heartbeat"],
            "summary": row["summary"],
            "stages": {},
        }

        # 加载阶段
        for sr in conn.execute("SELECT * FROM workflow_stages WHERE project_name = ?", (project_name,)):
            sd = {
                "status": sr["status"],
                "agent": sr["agent"],
                "result": sr["result"],
                "completed_at": sr["completed_at"],
                "duration_seconds": sr["duration_seconds"],
                "retry_count": sr["retry_count"],
                "force_passed": bool(sr["force_passed"]),
                "history": [],
            }
            # 解析 sub_tasks
            if sr["sub_tasks_json"]:
                try:
                    sd["sub_tasks"] = json.loads(sr["sub_tasks_json"])
                except json.JSONDecodeError:
                    pass

            # 解析 extra_json（checkpoint_files, checkpoint_prev_result 等）
            try:
                extra_val = sr["extra_json"] if "extra_json" in sr.keys() else None
            except (IndexError, KeyError):
                extra_val = None
            if extra_val:
                try:
                    extra_data = json.loads(extra_val)
                    sd.update(extra_data)
                except json.JSONDecodeError:
                    pass

            # 加载历史
            for hr in conn.execute(
                "SELECT * FROM workflow_stage_history WHERE project_name = ? AND stage_id = ? ORDER BY attempt",
                (project_name, sr["stage_id"])
            ):
                sd["history"].append({
                    "attempt": hr["attempt"],
                    "result": hr["result"],
                    "completed_at": hr["completed_at"],
                    "duration_seconds": hr["duration_seconds"],
                })

            wf["stages"][sr["stage_id"]] = sd

        return wf
    finally:
        conn.close()


def load_all_workflows() -> Dict:
    """加载所有工作流（兼容原 load_db(WORKFLOW_DB) 的返回格式）"""
    ensure_db()
    conn = _connect()
    try:
        result = {"workflows": {}}
        for row in conn.execute("SELECT project_name FROM workflows ORDER BY created_at"):
            wf = load_workflow(row["project_name"])
            if wf:
                result["workflows"][row["project_name"]] = wf
        return result
    finally:
        conn.close()


def save_workflow(project_name: str, wf: Dict):
    """保存单个工作流（增量更新，只写变化的字段）"""
    ensure_db()
    conn = _connect()
    try:
        # UPSERT 工作流主记录
        conn.execute("""
            INSERT INTO workflows
            (project_name, department, status, current_stage_index, current_stage_id,
             total_stages, created_at, started_at, completed_at, interrupted_at,
             paused_at, last_heartbeat, summary)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(project_name) DO UPDATE SET
                status=excluded.status,
                current_stage_index=excluded.current_stage_index,
                current_stage_id=excluded.current_stage_id,
                started_at=excluded.started_at,
                completed_at=excluded.completed_at,
                interrupted_at=excluded.interrupted_at,
                paused_at=excluded.paused_at,
                last_heartbeat=excluded.last_heartbeat,
                summary=excluded.summary
        """, (
            project_name, wf.get("department", "技术部"), wf.get("status", "ready"),
            wf.get("current_stage_index", 0), wf.get("current_stage_id"),
            wf.get("total_stages", 0), wf.get("created_at"), wf.get("started_at"),
            wf.get("completed_at"), wf.get("interrupted_at"), wf.get("paused_at"),
            wf.get("last_heartbeat"), wf.get("summary"),
        ))

        # UPSERT 各阶段
        for sid, sd in wf.get("stages", {}).items():
            sub_tasks_json = None
            if sd.get("sub_tasks"):
                sub_tasks_json = json.dumps(sd["sub_tasks"], ensure_ascii=False)
            # 收集额外字段（checkpoint_files, checkpoint_prev_result 等）
            extra_data = {}
            for key in ("checkpoint_files", "checkpoint_prev_result"):
                if key in sd:
                    extra_data[key] = sd[key]
            extra_json = json.dumps(extra_data, ensure_ascii=False) if extra_data else None
            conn.execute("""
                INSERT INTO workflow_stages
                (project_name, stage_id, status, agent, result, completed_at,
                 duration_seconds, retry_count, force_passed, sub_tasks_json, extra_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(project_name, stage_id) DO UPDATE SET
                    status=excluded.status,
                    result=excluded.result,
                    completed_at=excluded.completed_at,
                    duration_seconds=excluded.duration_seconds,
                    retry_count=excluded.retry_count,
                    force_passed=excluded.force_passed,
                    sub_tasks_json=excluded.sub_tasks_json,
                    extra_json=excluded.extra_json
            """, (
                project_name, sid, sd.get("status", "pending"), sd.get("agent"),
                sd.get("result"), sd.get("completed_at"),
                sd.get("duration_seconds"), sd.get("retry_count", 0),
                1 if sd.get("force_passed") else 0, sub_tasks_json, extra_json,
            ))

            # 替换历史记录（删除旧的再插入，避免重复追加）
            hist = sd.get("history", [])
            if hist:
                conn.execute(
                    "DELETE FROM workflow_stage_history WHERE project_name = ? AND stage_id = ?",
                    (project_name, sid)
                )
                for h in hist:
                    conn.execute("""
                        INSERT INTO workflow_stage_history
                        (project_name, stage_id, attempt, result, completed_at, duration_seconds)
                        VALUES (?,?,?,?,?,?)
                    """, (
                        project_name, sid, h.get("attempt", 0), h.get("result"),
                        h.get("completed_at"), h.get("duration_seconds"),
                    ))

        conn.commit()
    finally:
        conn.close()


def delete_workflow(project_name: str):
    """删除工作流及关联的阶段/历史"""
    ensure_db()
    conn = _connect()
    try:
        conn.execute("DELETE FROM workflows WHERE project_name = ?", (project_name,))
        conn.commit()
    finally:
        conn.close()


def compact_workflow(keep_result_chars: int = 200) -> Dict:
    """压缩已完成/失败的工作流数据：截断 result，清理 history"""
    ensure_db()
    conn = _connect()
    try:
        compacted = 0
        freed_chars = 0

        for row in conn.execute(
            "SELECT project_name FROM workflows WHERE status IN ('completed', 'failed')"
        ):
            project_name = row["project_name"]
            for sr in conn.execute(
                "SELECT stage_id, result, sub_tasks_json FROM workflow_stages WHERE project_name = ?",
                (project_name,)
            ):
                # 截断 result
                result = sr["result"] or ""
                if len(result) > keep_result_chars:
                    freed_chars += len(result) - keep_result_chars
                    new_result = result[:keep_result_chars] + "\n...(已压缩，原长度 %d 字符)" % len(result) if keep_result_chars > 0 else "(已压缩，原长度 %d 字符)" % len(result)
                    conn.execute(
                        "UPDATE workflow_stages SET result = ? WHERE project_name = ? AND stage_id = ?",
                        (new_result, project_name, sr["stage_id"])
                    )

            # 清理 history（只保留元数据）
            conn.execute(
                "DELETE FROM workflow_stage_history WHERE project_name = ?", (project_name,)
            )
            compacted += 1

        conn.commit()
        # 计算数据库大小
        db_size = os.path.getsize(_get_db_path())
        return {"compacted": compacted, "freed_chars": freed_chars, "remaining_size": db_size}
    finally:
        conn.close()


def query_workflows_by_status(status: str) -> List[Dict]:
    """按状态查询工作流（利用索引，无需加载全部数据）"""
    ensure_db()
    conn = _connect()
    try:
        results = []
        for row in conn.execute(
            "SELECT * FROM workflows WHERE status = ? ORDER BY created_at", (status,)
        ):
            results.append(dict(row))
        return results
    finally:
        conn.close()


def record_token_usage(project_name: str, stage_id: str, token_usage: Dict):
    """记录 token 用量"""
    ensure_db()
    conn = _connect()
    try:
        conn.execute("""
            INSERT INTO token_usage (project_name, stage_id, prompt_tokens, completion_tokens, total_tokens, recorded_at)
            VALUES (?,?,?,?,?,?)
        """, (
            project_name, stage_id,
            token_usage.get("prompt_tokens", 0),
            token_usage.get("completion_tokens", 0),
            token_usage.get("total_tokens", 0),
            datetime.now().isoformat(),
        ))
        conn.commit()
    finally:
        conn.close()


def get_token_usage_summary() -> Dict:
    """获取 token 用量汇总"""
    ensure_db()
    conn = _connect()
    try:
        row = conn.execute("""
            SELECT
                COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) as completion_tokens,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COUNT(*) as record_count
            FROM token_usage
        """).fetchone()
        return dict(row) if row else {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "record_count": 0}
    finally:
        conn.close()


# ==================== 项目 CRUD ====================

def load_all_projects() -> Dict:
    """加载所有项目（兼容原 load_db(PROJECTS_DB) 格式）"""
    ensure_db()
    conn = _connect()
    try:
        result = {"projects": {}}
        for row in conn.execute("SELECT * FROM projects ORDER BY created_at"):
            result["projects"][row["name"]] = {
                "name": row["name"],
                "description": row["description"],
                "department": row["department"],
                "created_at": row["created_at"],
                "status": row["status"],
            }
        return result
    finally:
        conn.close()


def save_project(name: str, project: Dict):
    """保存单个项目"""
    ensure_db()
    conn = _connect()
    try:
        conn.execute("""
            INSERT INTO projects (name, description, department, created_at, status)
            VALUES (?,?,?,?,?)
            ON CONFLICT(name) DO UPDATE SET
                description=excluded.description,
                department=excluded.department,
                status=excluded.status
        """, (
            name, project.get("description", ""), project.get("department", "技术部"),
            project.get("created_at"), project.get("status", "active"),
        ))
        conn.commit()
    finally:
        conn.close()
