"""
使用监控 - 记录每次调用的指标：耗时、成功率、错误统计
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

# 监控数据文件
MONITOR_FILE = "monitoring.json"
MAX_DAILY_STATS_DAYS = 90  # 每日统计最多保留天数
BATCH_SAVE_INTERVAL = 5    # 每 N 次 record_call 后才真正写盘（减少 I/O）


class UsageMonitor:
    """CrewAI Scheduler 使用监控"""

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            # 使用 data/ 目录（与源码分离）
            try:
                from __main__ import DATA_DIR
                data_dir = DATA_DIR
            except ImportError:
                data_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = data_dir
        self.file_path = os.path.join(data_dir, MONITOR_FILE)
        self.data = self._load()
        self._pending_writes = 0  # 批量写入计数器

    def _load(self) -> dict:
        """加载监控数据"""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return self._empty_data()

    def _empty_data(self) -> dict:
        """创建空数据结构"""
        return {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "summary": {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "success_rate": 0.0,
                "total_duration_ms": 0,
                "avg_duration_ms": 0,
                "commands_used": {},
                "departments_used": {},
                "errors_by_type": {},
            },
            "calls": [],
            "daily_stats": {},
        }

    def save(self):
        """保存监控数据（原子写入：先写临时文件再替换，防止写入中断导致数据损坏）"""
        self.data["last_updated"] = datetime.now().isoformat()
        # 转换 defaultdict 为普通 dict
        self.data["summary"]["errors_by_type"] = dict(
            self.data["summary"]["errors_by_type"]
        )
        temp_file = self.file_path + ".tmp"
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(temp_file, self.file_path)
        except Exception as e:
            print(f"[ERROR] 保存监控数据失败: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    def record_call(
        self,
        command: str,
        success: bool,
        duration_ms: float,
        department: str = None,
        error: str = None,
        extra: dict = None
    ):
        """
        记录一次调用
        
        Args:
            command: 命令名称（如 execute, assign-task）
            success: 是否成功
            duration_ms: 耗时（毫秒）
            department: 涉及部门
            error: 错误信息（如果失败）
            extra: 额外信息
        """
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        timestamp = now.isoformat()

        # 创建调用记录
        call_record = {
            "timestamp": timestamp,
            "command": command,
            "success": success,
            "duration_ms": round(duration_ms, 2),
            "department": department,
            "error": error,
            "extra": extra or {},
        }

        # 追加到调用列表（保留最近1000条）
        self.data["calls"].append(call_record)
        if len(self.data["calls"]) > 1000:
            self.data["calls"] = self.data["calls"][-1000:]

        # 更新汇总统计
        summary = self.data["summary"]
        summary["total_calls"] += 1
        summary["total_duration_ms"] += duration_ms

        if success:
            summary["successful_calls"] += 1
        else:
            summary["failed_calls"] += 1
            if error:
                error_type = error.split(":")[0][:50]
                if error_type not in summary["errors_by_type"]:
                    summary["errors_by_type"][error_type] = 0
                summary["errors_by_type"][error_type] += 1

        # 成功率
        summary["success_rate"] = (
            summary["successful_calls"] / summary["total_calls"] * 100
            if summary["total_calls"] > 0 else 0
        )

        # 平均耗时
        summary["avg_duration_ms"] = (
            summary["total_duration_ms"] / summary["total_calls"]
            if summary["total_calls"] > 0 else 0
        )

        # 命令使用统计
        if command not in summary["commands_used"]:
            summary["commands_used"][command] = 0
        summary["commands_used"][command] += 1

        # 部门使用统计
        if department:
            if department not in summary["departments_used"]:
                summary["departments_used"][department] = 0
            summary["departments_used"][department] += 1

        # 每日统计
        if date_str not in self.data["daily_stats"]:
            self.data["daily_stats"][date_str] = {
                "calls": 0,
                "success": 0,
                "failed": 0,
                "duration_ms": 0,
            }
        daily = self.data["daily_stats"][date_str]
        daily["calls"] += 1
        daily["duration_ms"] += duration_ms
        if success:
            daily["success"] += 1
        else:
            daily["failed"] += 1

        # 清理过期的每日统计
        self._prune_daily_stats()

        # 批量写入：每 BATCH_SAVE_INTERVAL 次调用才真正写盘
        self._pending_writes += 1
        if self._pending_writes >= BATCH_SAVE_INTERVAL:
            self.save()
            self._pending_writes = 0

    def _prune_daily_stats(self):
        """清理超过 MAX_DAILY_STATS_DAYS 天的每日统计"""
        if len(self.data.get("daily_stats", {})) <= MAX_DAILY_STATS_DAYS:
            return
        cutoff = (datetime.now() - timedelta(days=MAX_DAILY_STATS_DAYS)).strftime("%Y-%m-%d")
        to_remove = [d for d in self.data["daily_stats"] if d < cutoff]
        for d in to_remove:
            del self.data["daily_stats"][d]

    def get_summary(self) -> dict:
        """获取汇总报告"""
        s = self.data["summary"]
        return {
            "总调用次数": s["total_calls"],
            "成功次数": s["successful_calls"],
            "失败次数": s["failed_calls"],
            "成功率": f"{s['success_rate']:.1f}%",
            "平均耗时": f"{s['avg_duration_ms']:.0f}ms",
            "总耗时": f"{s['total_duration_ms']:.0f}ms",
            "命令使用分布": dict(s["commands_used"]),
            "部门使用分布": dict(s["departments_used"]),
            "错误类型分布": dict(s["errors_by_type"]),
            "最近7天": self._get_recent_days(7),
        }

    def _get_recent_days(self, days: int) -> List[dict]:
        """获取最近N天的统计"""
        result = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            if date in self.data["daily_stats"]:
                d = self.data["daily_stats"][date]
                result.append({
                    "日期": date,
                    "调用": d["calls"],
                    "成功": d["success"],
                    "失败": d["failed"],
                    "耗时(ms)": round(d["duration_ms"], 0),
                })
        return list(reversed(result))

    def print_report(self):
        """打印监控报告"""
        report = self.get_summary()

        print("\n" + "=" * 60)
        print("CREWAI SCHEDULER - USAGE MONITOR REPORT")
        print("=" * 60)

        print(f"\n[OVERVIEW] 总览:")
        print(f"  总调用: {report['总调用次数']} | "
              f"成功: {report['成功次数']} | "
              f"失败: {report['失败次数']} | "
              f"成功率: {report['成功率']}")
        print(f"  平均耗时: {report['平均耗时']} | 总耗时: {report['总耗时']}")

        if report["命令使用分布"]:
            print(f"\n[COMMANDS] 命令使用:")
            for cmd, count in sorted(report["命令使用分布"].items(), key=lambda x: -x[1]):
                print(f"  {cmd}: {count} 次")

        if report["部门使用分布"]:
            print(f"\n[DEPARTMENTS] 部门任务:")
            for dept, count in sorted(report["部门使用分布"].items(), key=lambda x: -x[1]):
                print(f"  {dept}: {count} 次")

        if report["错误类型分布"]:
            print(f"\n[ERRORS] 错误类型:")
            for err, count in sorted(report["错误类型分布"].items(), key=lambda x: -x[1]):
                print(f"  {err}: {count} 次")

        if report["最近7天"]:
            print(f"\n[DAILY] 最近7天:")
            for day in report["最近7天"]:
                print(f"  {day['日期']}: {day['调用']}次 "
                      f"(成功:{day['成功']} 失败:{day['失败']} "
                      f"耗时:{day['耗时(ms)']}ms)")

        print("\n" + "=" * 60)


# 全局监控实例
_monitor: Optional[UsageMonitor] = None


def get_monitor() -> UsageMonitor:
    """获取全局监控实例"""
    global _monitor
    if _monitor is None:
        _monitor = UsageMonitor()
    return _monitor


def record_command(command: str, success: bool, duration_ms: float, **kwargs):
    """便捷函数：记录命令调用"""
    get_monitor().record_call(command, success, duration_ms, **kwargs)


class MonitorTimer:
    """计时器上下文管理器，自动记录调用"""

    def __init__(self, command: str, department: str = None, **extra):
        self.command = command
        self.department = department
        self.extra = extra
        self.start_time = None
        self.success = True
        self.error = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.time() - self.start_time) * 1000
        self.success = (exc_type is None)
        self.error = str(exc_val) if exc_val else None

        get_monitor().record_call(
            command=self.command,
            success=self.success,
            duration_ms=duration_ms,
            department=self.department,
            error=self.error,
            extra=self.extra,
        )
        return False  # 不吞异常
