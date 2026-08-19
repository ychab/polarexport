import logging
import sys
from collections.abc import Iterable

import pytest

from polarexport.infrastructure.config.loggers import LOGGER_POLAREXPORT
from polarexport.infrastructure.config.loggers import MaxLevelFilter
from polarexport.infrastructure.config.loggers import configure_loggers

_HANDLER_CLASS_NAMES = {
    "console": "StreamHandler",
    "cli": "StreamHandler",
    "cli_alert": "StreamHandler",
    "null": "NullHandler",
}


class TestMaxLevelFilter:
    @pytest.fixture
    def max_level_filter(self) -> MaxLevelFilter:
        return MaxLevelFilter(level=logging.WARNING)

    @pytest.mark.parametrize(
        ("levelno", "expected"),
        [
            (logging.INFO, True),
            (logging.WARNING, False),
            (logging.ERROR, False),
        ],
    )
    def test__filter__passes_only_records_below_level(
        self, max_level_filter: MaxLevelFilter, levelno: int, expected: bool
    ) -> None:
        record = logging.LogRecord(
            name="polarexport", level=levelno, pathname=__file__, lineno=1, msg="msg", args=(), exc_info=None
        )

        assert max_level_filter.filter(record) is expected


class TestConfigureLoggers:
    @pytest.fixture(autouse=True)
    def restore_default_logging(self) -> Iterable[None]:
        yield
        configure_loggers(level="DEBUG", handlers=["null"], propagate=True)

    @pytest.mark.parametrize(
        ("level", "handlers", "propagate"),
        [
            ("DEBUG", ["null"], True),
            ("WARNING", ["console"], False),
            ("ERROR", ["cli", "cli_alert"], True),
        ],
    )
    def test__applies_level_handlers_and_propagate(
        self,
        level: str,
        handlers: list[str],
        propagate: bool,
    ) -> None:
        configure_loggers(level=level, handlers=handlers, propagate=propagate)  # type: ignore[arg-type]

        logger = logging.getLogger(LOGGER_POLAREXPORT)
        assert logger.level == getattr(logging, level)
        assert logger.propagate is propagate
        assert [type(h).__name__ for h in logger.handlers] == [_HANDLER_CLASS_NAMES[h] for h in handlers]

        httpx_logger = logging.getLogger("httpx")
        assert [type(h).__name__ for h in httpx_logger.handlers] == [_HANDLER_CLASS_NAMES[h] for h in handlers]

        assert [type(h).__name__ for h in logging.getLogger().handlers] == [_HANDLER_CLASS_NAMES[h] for h in handlers]

    def test__cli_and_cli_alert_both_requested__cli_filtered_cli_alert_on_stderr(self) -> None:
        configure_loggers(level="DEBUG", handlers=["cli", "cli_alert"], propagate=False)

        logger = logging.getLogger(LOGGER_POLAREXPORT)
        cli_handler, cli_alert_handler = logger.handlers
        assert isinstance(cli_alert_handler, logging.StreamHandler)
        assert any(isinstance(f, MaxLevelFilter) for f in cli_handler.filters)
        assert cli_alert_handler.stream is sys.stderr

    def test__emits_at_configured_level(self, capsys: pytest.CaptureFixture[str]) -> None:
        # dictConfig() replaces the root logger's handlers wholesale, which would tear down
        # pytest's own caplog handler — assert on the "console" handler's stdout instead.
        configure_loggers(level="INFO", handlers=["console"], propagate=False)

        logger = logging.getLogger(LOGGER_POLAREXPORT)
        logger.debug("should not appear")
        logger.info("should appear")

        captured = capsys.readouterr()
        assert "should not appear" not in captured.out
        assert "should appear" in captured.out
