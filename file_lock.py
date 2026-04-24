"""
文件锁工具 - 用于JSON数据库的并发访问控制
"""

import os
import time
import threading
from contextlib import contextmanager
from typing import Optional

# 僵尸锁最大存活时间（秒）：超过此时间的残留锁文件将被自动清除
STALE_LOCK_MAX_AGE = 300  # 5 分钟


def _is_stale_lock(lock_file: str) -> bool:
    """检查锁文件是否为僵尸锁（创建时间超过阈值）"""
    try:
        mtime = os.path.getmtime(lock_file)
        return (time.time() - mtime) > STALE_LOCK_MAX_AGE
    except OSError:
        return False

class FileLock:
    """基于文件锁的并发控制"""
    
    def __init__(self, lock_file: str, timeout: float = 10.0, retry_interval: float = 0.1):
        self.lock_file = lock_file
        self.timeout = timeout
        self.retry_interval = retry_interval
        self._local_lock = threading.Lock()
        self._acquired = False
    
    def acquire(self) -> bool:
        """获取锁（使用 O_CREAT|O_EXCL 原子创建，避免 TOCTOU 竞态）"""
        start_time = time.time()
        
        while time.time() - start_time < self.timeout:
            try:
                with self._local_lock:
                    try:
                        # 原子创建：O_CREAT|O_EXCL 确保文件不存在时才创建成功
                        fd = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                        try:
                            os.write(fd, f"{os.getpid()}:{threading.current_thread().ident}".encode())
                        finally:
                            os.close(fd)
                        self._acquired = True
                        return True
                    except FileExistsError:
                        # 锁文件已存在，检查是否为僵尸锁
                        if _is_stale_lock(self.lock_file):
                            try:
                                os.remove(self.lock_file)
                                continue  # 清除后立即重试
                            except OSError:
                                pass  # 被其他进程抢先删除，正常重试
            except Exception as e:
                pass  # 锁获取的异常不阻塞主流程，仅重试
            
            # 等待重试
            time.sleep(self.retry_interval)
        
        return False
    
    def release(self):
        """释放锁"""
        with self._local_lock:
            if self._acquired and os.path.exists(self.lock_file):
                try:
                    os.remove(self.lock_file)
                except Exception as e:
                    pass  # 锁释放失败不阻塞，僵尸锁由超时机制清理
                self._acquired = False
    
    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"无法获取文件锁: {self.lock_file}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


class DatabaseLock:
    """数据库级别的锁管理"""
    
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.lock_file = db_file + ".lock"
        self.lock = FileLock(self.lock_file)
    
    @contextmanager
    def acquire(self):
        """获取数据库锁的上下文管理器"""
        try:
            with self.lock:
                yield self
        except TimeoutError as e:
            raise TimeoutError(f"数据库 {self.db_file} 被锁定，请稍后再试") from e


# 全局锁管理器
_lock_managers = {}
_lock_managers_lock = threading.Lock()


def get_db_lock(db_file: str) -> DatabaseLock:
    """获取数据库锁实例"""
    with _lock_managers_lock:
        if db_file not in _lock_managers:
            _lock_managers[db_file] = DatabaseLock(db_file)
        return _lock_managers[db_file]
