"""
性能计时工具 - 提供可复用的计时上下文管理器和装饰器
输出到控制台 + data/performance.log
"""
import sys
import time
import functools
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

# 延迟导入config避免循环依赖
def _get_log_path():
    from config import LOG_PATH
    return LOG_PATH


class _PerfFormatter(logging.Formatter):
    """自定义formatter，处理可选的duration字段"""
    def format(self, record):
        if not hasattr(record, 'duration'):
            record.duration = 0
        return super().format(record)


_logger_instance = None

def get_perf_logger() -> logging.Logger:
    """获取性能日志单例logger"""
    global _logger_instance
    if _logger_instance is not None:
        return _logger_instance

    logger = logging.getLogger("perf")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # 避免重复添加handler
    if logger.handlers:
        _logger_instance = logger
        return logger

    fmt = _PerfFormatter(
        "[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s | duration=%(duration)sms",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    # 文件输出 (RotatingFileHandler, 5MB, 3备份)
    try:
        log_path = _get_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            str(log_path), maxBytes=5*1024*1024, backupCount=3,
            encoding="utf-8", delay=True
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except Exception:
        pass  # 文件handler创建失败不影响控制台输出

    _logger_instance = logger
    return logger


class TimerContext:
    """
    计时上下文管理器。

    用法:
        with TimerContext("my_operation", logger) as t:
            do_work()
        # t.duration_ms 可用

    自动记录:
        - INFO: 正常完成
        - WARN: 超过阈值 (默认5秒)
        - ERROR: 异常
    """
    def __init__(self, label: str, logger: logging.Logger = None,
                 warn_threshold_ms: float = 5000.0):
        self.label = label
        self.logger = logger or get_perf_logger()
        self.warn_threshold_ms = warn_threshold_ms
        self.duration_ms = 0.0
        self._start = 0.0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (time.perf_counter() - self._start) * 1000
        self.duration_ms = elapsed

        extra = {"duration": f"{elapsed:.1f}"}

        if exc_type is not None:
            self.logger.error(
                "%s FAILED: %s | %.1fms",
                self.label, exc_val, elapsed, extra=extra
            )
        elif elapsed > self.warn_threshold_ms:
            self.logger.warning(
                "%s SLOW | %.1fms", self.label, elapsed, extra=extra
            )
        else:
            self.logger.info(
                "%s | %.1fms", self.label, elapsed, extra=extra
            )
        return False  # 不吞异常


def timed(func=None, *, label=None, warn_threshold_ms=5000.0):
    """
    计时装饰器。

    用法:
        @timed
        def my_func(): ...

        @timed(label="custom_name", warn_threshold_ms=1000)
        def my_func(): ...
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            lbl = label or f"{fn.__module__}.{fn.__qualname__}"
            with TimerContext(lbl, warn_threshold_ms=warn_threshold_ms):
                return fn(*args, **kwargs)
        return wrapper

    if func is not None:
        # @timed 无括号调用
        return decorator(func)
    # @timed(...) 有括号调用
    return decorator


def log_user_action(action: str, detail: str = "", logger: logging.Logger = None):
    """记录用户操作行为

    Args:
        action: 操作类型 (如 "click", "input", "select", "download")
        detail: 操作详情 (如按钮名称、输入内容等)
        logger: 可选的logger实例
    """
    lg = logger or get_perf_logger()
    msg = f"[USER] {action}: {detail}" if detail else f"[USER] {action}"
    lg.info(msg, extra={"duration": "0"})


def read_recent_logs(n: int = 50) -> list:
    """读取最近n条性能日志"""
    try:
        log_path = _get_log_path()
        if not log_path.exists():
            return []
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return [line.rstrip() for line in lines[-n:]]
    except Exception:
        return []
