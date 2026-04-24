#!/usr/bin/env python3
"""
测试 v3.2 改进项：retry、路径遍历、锁原子化、模块合并、配置校验、文件扩展名常量
"""

import os
import sys
import json
import time
import tempfile
import shutil
import unittest

# 确保可以导入项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCallWithRetry(unittest.TestCase):
    """测试 _call_with_retry（指数退避 + 重试）"""

    def test_success_first_try(self):
        from __main__ import _call_with_retry
        result = _call_with_retry(fn=lambda: {"success": True, "result": "ok"})
        self.assertTrue(result["success"])
        self.assertEqual(result["result"], "ok")

    def test_retry_on_rate_limit(self):
        from __main__ import _call_with_retry, RATE_LIMIT_BACKOFF_BASE, MAX_JITTER_SECONDS
        call_count = [0]

        def failing_fn():
            call_count[0] += 1
            if call_count[0] < 3:
                return {"success": False, "result": "429 rate limit exceeded"}
            return {"success": True, "result": "ok after retry"}

        # 使用极短退避以加快测试
        result = _call_with_retry(fn=failing_fn, backoff_base=0.01)
        self.assertTrue(result["success"])
        self.assertEqual(call_count[0], 3)

    def test_non_rate_limit_failure_no_retry(self):
        from __main__ import _call_with_retry
        call_count = [0]

        def failing_fn():
            call_count[0] += 1
            return {"success": False, "result": "connection refused"}

        result = _call_with_retry(fn=failing_fn, max_retries=3)
        self.assertFalse(result["success"])
        self.assertEqual(call_count[0], 1)  # 非速率限制不重试

    def test_max_retries_exhausted(self):
        from __main__ import _call_with_retry
        call_count = [0]

        def always_rate_limited():
            call_count[0] += 1
            return {"success": False, "result": "429 too many requests"}

        result = _call_with_retry(fn=always_rate_limited, max_retries=3, backoff_base=0.01)
        self.assertFalse(result["success"])
        self.assertEqual(call_count[0], 3)


class TestPathTraversal(unittest.TestCase):
    """测试路径遍历防护"""

    def test_project_writer_blocks_traversal(self):
        from project_writer import ProjectWriter
        from code_extractor import CodeFile

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ProjectWriter(tmpdir)
            # 正常路径应成功
            ok_file = CodeFile(path="src/main.py", content="print('hi')", language="python")
            result = writer.write_file("test_proj", ok_file)
            self.assertTrue(os.path.exists(result))

            # 路径遍历应被拒绝
            bad_file = CodeFile(path="../../etc/passwd", content="hacked", language="text")
            with self.assertRaises(ValueError):
                writer.write_file("test_proj", bad_file)

    def test_project_writer_blocks_absolute_path(self):
        from project_writer import ProjectWriter
        from code_extractor import CodeFile

        with tempfile.TemporaryDirectory() as tmpdir:
            writer = ProjectWriter(tmpdir)
            bad_file = CodeFile(path="/etc/passwd", content="hacked", language="text")
            with self.assertRaises(ValueError):
                writer.write_file("test_proj", bad_file)


class TestFileLockAtomic(unittest.TestCase):
    """测试文件锁原子化（O_CREAT|O_EXCL）"""

    def test_basic_lock_acquire_release(self):
        from file_lock import FileLock

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = os.path.join(tmpdir, "test.lock")
            lock = FileLock(lock_file, timeout=1.0)
            self.assertTrue(lock.acquire())
            self.assertTrue(os.path.exists(lock_file))
            lock.release()
            self.assertFalse(os.path.exists(lock_file))

    def test_lock_contention(self):
        from file_lock import FileLock

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = os.path.join(tmpdir, "contended.lock")
            lock1 = FileLock(lock_file, timeout=1.0)
            lock2 = FileLock(lock_file, timeout=0.5)

            self.assertTrue(lock1.acquire())
            # 第二个锁应获取失败（超时）
            self.assertFalse(lock2.acquire())
            lock1.release()

    def test_stale_lock_cleanup(self):
        from file_lock import FileLock, _is_stale_lock, STALE_LOCK_MAX_AGE

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = os.path.join(tmpdir, "stale.lock")
            # 创建一个旧锁文件
            with open(lock_file, 'w') as f:
                f.write("12345:67890")

            # 新创建的不应被判定为僵尸
            self.assertFalse(_is_stale_lock(lock_file))

            # 修改 mtime 为很久以前
            old_time = time.time() - STALE_LOCK_MAX_AGE - 60
            os.utime(lock_file, (old_time, old_time))

            # 现在应被判定为僵尸
            self.assertTrue(_is_stale_lock(lock_file))

            # acquire 应能自动清除僵尸锁
            lock = FileLock(lock_file, timeout=1.0)
            self.assertTrue(lock.acquire())
            lock.release()


class TestMergeModules(unittest.TestCase):
    """测试 _merge_modules"""

    def test_no_merge_needed(self):
        from __main__ import _merge_modules
        modules = [{"id": "a", "name": "A", "files": ["f1"]},
                   {"id": "b", "name": "B", "files": ["f2"]}]
        result = _merge_modules(modules, max_modules=5, max_files_per_module=8)
        self.assertEqual(len(result), 2)

    def test_merge_exceeds_max(self):
        from __main__ import _merge_modules
        modules = [{"id": str(i), "name": f"M{i}", "files": [f"f{i}"]}
                   for i in range(6)]
        result = _merge_modules(modules, max_modules=3, max_files_per_module=8)
        self.assertLessEqual(len(result), 3)

    def test_force_merge_when_all_exceed_limit(self):
        from __main__ import _merge_modules
        # 每个模块 10 个文件，max_files*2=16，能合并
        modules = [{"id": str(i), "name": f"M{i}", "files": [f"f{i}_{j}" for j in range(10)]}
                   for i in range(5)]
        result = _merge_modules(modules, max_modules=2, max_files_per_module=8)
        self.assertLessEqual(len(result), 2)


class TestCodeExtensions(unittest.TestCase):
    """测试文件扩展名集中管理"""

    def test_code_extensions_not_empty(self):
        from code_extractor import CODE_EXTENSIONS, SOURCE_CODE_EXTENSIONS, CONFIG_EXTENSIONS
        self.assertTrue(len(CODE_EXTENSIONS) > 10)
        self.assertTrue(len(SOURCE_CODE_EXTENSIONS) > 5)
        self.assertTrue(len(CONFIG_EXTENSIONS) > 3)

    def test_common_exts_in_set(self):
        from code_extractor import CODE_EXTENSIONS
        for ext in ['py', 'js', 'ts', 'tsx', 'java', 'go', 'rs', 'html', 'css', 'json']:
            self.assertIn(ext, CODE_EXTENSIONS, f"{ext} not in CODE_EXTENSIONS")


class TestConfigValidation(unittest.TestCase):
    """测试配置校验"""

    def test_valid_config_no_warnings(self):
        from crewai_scheduler import CrewAIScheduler
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            config = {
                "api": {
                    "openai_api_key": "test",
                    "base_url": "https://api.test.com/v1",
                    "model": "test-model",
                    "temperature": 0.7,
                    "max_tokens": 128000,
                    "timeout": 300,
                },
                "system": {"debug": False},
                "workflow": {},
            }
            with open(config_path, 'w') as f:
                json.dump(config, f)
            # 不应抛出异常
            scheduler = CrewAIScheduler(config_path=config_path)
            self.assertIsNotNone(scheduler)


class TestSaveStageOutput(unittest.TestCase):
    """测试大段输出存独立文件"""

    def test_short_output_unchanged(self):
        from __main__ import _save_stage_output
        short = "这是一个短的输出"
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["CREWAI_PROJECTS_DIR"] = tmpdir
            try:
                result = _save_stage_output("test_proj", "requirements", short)
                self.assertEqual(result, short)
            finally:
                del os.environ["CREWAI_PROJECTS_DIR"]

    def test_long_output_saved_to_file(self):
        from __main__ import _save_stage_output, STAGE_OUTPUT_FILE_THRESHOLD
        long_text = "x" * (STAGE_OUTPUT_FILE_THRESHOLD + 1000)
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["CREWAI_PROJECTS_DIR"] = tmpdir
            try:
                result = _save_stage_output("test_proj", "architecture", long_text)
                # 应返回摘要 + 文件引用
                self.assertIn("file:", result)
                self.assertIn("architecture_full.md", result)
            finally:
                del os.environ["CREWAI_PROJECTS_DIR"]


class TestJSTypeExportDetection(unittest.TestCase):
    """测试 JS/TS 导出检测增强"""

    def test_export_const(self):
        from code_extractor import _extract_export_lines
        content = "export const API_URL = 'http://localhost';\nexport function fetch() {}"
        exports = _extract_export_lines(content, 'ts')
        self.assertTrue(any('API_URL' in e for e in exports))

    def test_export_braces(self):
        from code_extractor import _extract_export_lines
        content = "export { foo, bar, baz };\n"
        exports = _extract_export_lines(content, 'js')
        self.assertTrue(any('foo' in e for e in exports))

    def test_export_type(self):
        from code_extractor import _extract_export_lines
        content = "export interface User { name: string }\nexport type Status = 'active' | 'inactive'"
        exports = _extract_export_lines(content, 'ts')
        self.assertTrue(any('User' in e for e in exports))
        self.assertTrue(any('Status' in e for e in exports))


if __name__ == '__main__':
    unittest.main()
