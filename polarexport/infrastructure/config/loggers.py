import logging
import logging.config
from copy import deepcopy
from typing import Any
from typing import Final

from polarexport.infrastructure.types import LogHandler
from polarexport.infrastructure.types import LogLevel

LOGGER_POLAREXPORT: Final[str] = "polarexport"


class MaxLevelFilter(logging.Filter):
    """Passes only records strictly below `level`, so a paired handler can own the rest."""

    def __init__(self, level: int) -> None:
        super().__init__()
        self._level = level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno < self._level


default_conf: Final[dict[str, Any]] = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "max_level_warning": {
            "()": MaxLevelFilter,
            "level": logging.WARNING,
        },
    },
    "formatters": {
        "default": {
            "format": "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "message": {
            "format": "%(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "rich": {
            # RichHandler ignores the 'format' string usually, but 'datefmt' works
            "format": "%(message)s",
            "datefmt": "[%X]",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "default",
            "stream": "ext://sys.stdout",
        },
        "cli": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "message",
            "stream": "ext://sys.stdout",
        },
        "cli_alert": {
            "class": "logging.StreamHandler",
            "level": "WARNING",
            "formatter": "default",
            "stream": "ext://sys.stderr",
        },
        "rich": {
            "class": "rich.logging.RichHandler",
            "formatter": "rich",
            "level": "NOTSET",
            # Optional Rich settings
            "markup": True,
            "rich_tracebacks": True,
            "show_level": True,
            "show_path": True,
            "show_time": True,
        },
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "loggers": {
        LOGGER_POLAREXPORT: {
            "level": "INFO",
            "handlers": ["console"],
            "propagate": False,
        },
        "httpx": {
            "level": "WARNING",
            "handlers": ["console"],
            "propagate": False,
        },
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
}


def configure_loggers(level: LogLevel, handlers: list[LogHandler], propagate: bool = False) -> None:
    """Configures the application's loggers based on the provided level and handlers.

    This function takes a default logging configuration, modifies the log level and
    handlers for the application's main logger, and applies the same handlers
    to other defined loggers and the root logger.

    Args:
        level: The minimum logging level to set (e.g., "INFO", "DEBUG").
        handlers: A list of handler names (e.g., ["console"], ["rich"]) to use.
        propagate: Whether messages should be propagated to ancestor loggers.
    """
    conf = deepcopy(default_conf)

    if "cli" in handlers and "cli_alert" in handlers:
        # cli_alert owns WARNING and above; cap cli below it so the two don't overlap.
        conf["handlers"]["cli"]["filters"] = ["max_level_warning"]

    # Change level and propagate only for our main logger.
    conf["loggers"][LOGGER_POLAREXPORT]["level"] = level
    conf["loggers"][LOGGER_POLAREXPORT]["propagate"] = propagate

    # However, change handlers for all loggers defined to use the same.
    for logger in conf["loggers"].keys():
        conf["loggers"][logger]["handlers"] = handlers

    # Without forgetting the root handlers.
    conf["root"]["handlers"] = handlers

    logging.config.dictConfig(conf)
