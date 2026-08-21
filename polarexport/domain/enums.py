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


class SampleType(IntEnum):
    """Polar exercise sample-series type ids.

    `HEART_RATE` is confirmed: phase 21's live capture showed type "0" carrying 70-175 bpm values
    whose mean reproduces Polar's own `heart_rate.average`. The rest come from Polar's documentation —
    the audited sessions were all indoor, so types "1" and "10" were present but all-zero and their
    identity is inferred, not verified. Confirm SPEED and DISTANCE against a real outdoor session
    before trusting them (see phase 23).
    """

    HEART_RATE = 0
    SPEED = 1
    CADENCE = 2
    ALTITUDE = 3
    POWER = 4
    POWER_PEDALING_INDEX = 5
    POWER_LEFT_RIGHT_BALANCE = 6
    AIR_PRESSURE = 7
    RUNNING_CADENCE = 8
    TEMPERATURE = 9
    DISTANCE = 10
    RR_INTERVAL = 11


class LoadInterpretation(StrEnum):
    """Polar's verbal reading of a training-load figure.

    `MEDIUM`, `HIGH` and `NOT_AVAILABLE` were observed live; the others are documented by Polar.
    Unknown values must map to `None` with a warning, never raise — see the mapper rule in phase 23.
    """

    NOT_AVAILABLE = "NOT_AVAILABLE"
    VERY_LOW = "VERY_LOW"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"
