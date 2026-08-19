import logging
from collections.abc import Iterable

import pytest

from polarexport.infrastructure.config.loggers import LOGGER_POLAREXPORT
from polarexport.infrastructure.config.loggers import configure_loggers


class TestConfigureLoggersOutputSplit:
    @pytest.fixture(autouse=True)
    def restore_default_logging(self) -> Iterable[None]:
        yield
        configure_loggers(level="DEBUG", handlers=["null"], propagate=True)

    def test__cli_and_cli_alert__warning_printed_once_on_stderr_only(self, capsys: pytest.CaptureFixture[str]) -> None:
        configure_loggers(level="DEBUG", handlers=["cli", "cli_alert"], propagate=False)

        logger = logging.getLogger(LOGGER_POLAREXPORT)
        logger.warning("a lone warning")

        captured = capsys.readouterr()
        assert (captured.out + captured.err).count("a lone warning") == 1
        assert "a lone warning" in captured.err
        assert "a lone warning" not in captured.out

    def test__cli_alone__warning_still_emitted(self, capsys: pytest.CaptureFixture[str]) -> None:
        # The way to get item 1 wrong: baking the filter statically into "cli" would silently
        # swallow warnings whenever "cli_alert" is not also requested.
        configure_loggers(level="DEBUG", handlers=["cli"], propagate=False)

        logger = logging.getLogger(LOGGER_POLAREXPORT)
        logger.warning("a lone warning")

        captured = capsys.readouterr()
        assert "a lone warning" in captured.out
