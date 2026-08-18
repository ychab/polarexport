from enum import IntEnum
from enum import StrEnum


class NightSource(StrEnum):
    """A Polar AccessLink data source. Values double as `--source` CLI values and `raw/<source>/`
    directory names — keep them identical so there is one vocabulary."""

    SLEEP = "sleep"
    RECHARGE = "recharge"
    SKIN_TEMPERATURE = "skin-temperature"
    SLEEPWISE = "sleepwise"
    HEART_RATE = "heart-rate"


class SleepStage(IntEnum):
    """Hypnogram codes returned by Polar's sleep endpoint.

    Verified against the official swagger.yaml (polar.com/accesslink-api/swagger.yaml) and a live
    hypnogram capture in phase 5. Polar's own description distinguishes "LIGHTER" from "LIGHT"
    non-REM as two separate codes — kept verbatim even though it reads like a documentation slip.
    """

    WAKE = 0
    REM = 1
    LIGHTER_NON_REM = 2
    LIGHT_NON_REM = 3
    DEEP_NON_REM = 4
    UNKNOWN = 5  # e.g. due to bad skin contact


class ContinuityClass(IntEnum):
    """Polar's sleep continuity classification (`continuity_class` on the sleep payload).

    Verified against the official swagger.yaml in phase 5.
    """

    FRAGMENTED = 1
    FAIRLY_FRAGMENTED = 2
    FAIRLY_CONTINUOUS = 3
    CONTINUOUS = 4
    VERY_CONTINUOUS = 5

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


class NightlyRechargeStatus(IntEnum):
    """Polar's Nightly Recharge status classification (`nightly_recharge_status`).

    Verified against the official swagger.yaml in phase 5.
    """

    VERY_POOR = 1
    POOR = 2
    COMPROMISED = 3
    OK = 4
    GOOD = 5
    VERY_GOOD = 6

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()


class SourceAvailability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"  # 403 / consent missing
    NOT_REQUESTED = "not_requested"
    NO_DATA = "no_data"  # requested, consent fine, but the local store held nothing for the range
