"""计时工具单元测试"""
import time
import logging
import pytest
from utils.timing import TimerContext, timed, read_recent_logs, get_perf_logger, log_user_action


class TestTimerContext:
    def test_measures_duration(self):
        logger = logging.getLogger("test_timer")
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        with TimerContext("test_op", logger) as t:
            time.sleep(0.01)
        assert t.duration_ms >= 10

    def test_logs_info_for_fast_op(self):
        records = []
        logger = logging.getLogger("test_info")
        logger.setLevel(logging.DEBUG)
        handler = logging.Handler()
        handler.emit = lambda r: records.append(r)
        logger.addHandler(handler)

        with TimerContext("fast_op", logger, warn_threshold_ms=99999):
            pass

        assert len(records) == 1
        assert records[0].levelname == "INFO"

    def test_logs_warn_for_slow_op(self):
        records = []
        logger = logging.getLogger("test_warn")
        logger.setLevel(logging.DEBUG)
        handler = logging.Handler()
        handler.emit = lambda r: records.append(r)
        logger.addHandler(handler)

        with TimerContext("slow_op", logger, warn_threshold_ms=1):
            time.sleep(0.01)

        assert len(records) == 1
        assert records[0].levelname == "WARNING"

    def test_logs_error_on_exception(self):
        records = []
        logger = logging.getLogger("test_error")
        logger.setLevel(logging.DEBUG)
        handler = logging.Handler()
        handler.emit = lambda r: records.append(r)
        logger.addHandler(handler)

        with pytest.raises(ValueError):
            with TimerContext("fail_op", logger):
                raise ValueError("boom")

        assert len(records) == 1
        assert records[0].levelname == "ERROR"

    def test_context_manager_returns_self(self):
        logger = logging.getLogger("test_self")
        logger.setLevel(logging.CRITICAL)
        with TimerContext("op", logger) as t:
            pass
        assert t.duration_ms >= 0


class TestTimedDecorator:
    def test_preserves_return_value(self):
        logger = logging.getLogger("test_dec")
        logger.setLevel(logging.CRITICAL)

        @timed(label="test_func")
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_reraises_exception(self):
        @timed(label="fail_func")
        def fail():
            raise RuntimeError("oops")

        with pytest.raises(RuntimeError):
            fail()

    def test_no_parenthesis_usage(self):
        @timed
        def hello():
            return "hi"

        assert hello() == "hi"


class TestReadRecentLogs:
    def test_empty_when_no_file(self):
        result = read_recent_logs(n=10)
        # 可能有文件也可能没有，但不应报错
        assert isinstance(result, list)


class TestLogUserAction:
    def test_logs_action_with_detail(self):
        records = []
        logger = logging.getLogger("test_user_action")
        logger.setLevel(logging.DEBUG)
        handler = logging.Handler()
        handler.emit = lambda r: records.append(r)
        logger.addHandler(handler)

        log_user_action("click", "按钮名称", logger=logger)

        assert len(records) == 1
        assert "[USER] click: 按钮名称" in records[0].getMessage()
        assert records[0].levelname == "INFO"

    def test_logs_action_without_detail(self):
        records = []
        logger = logging.getLogger("test_user_action_no_detail")
        logger.setLevel(logging.DEBUG)
        handler = logging.Handler()
        handler.emit = lambda r: records.append(r)
        logger.addHandler(handler)

        log_user_action("page_load", logger=logger)

        assert len(records) == 1
        assert "[USER] page_load" in records[0].getMessage()


class TestGetPerfLogger:
    def test_singleton(self):
        a = get_perf_logger()
        b = get_perf_logger()
        assert a is b

    def test_has_handlers(self):
        logger = get_perf_logger()
        assert len(logger.handlers) >= 1
