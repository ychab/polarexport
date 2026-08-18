from typing import Final

# Verified against the live API and the official swagger.yaml (polar.com/accesslink-api/swagger.yaml)
# on 2026-08-17 — the plan's provisional skin-temperature/sleepwise paths returned a genuine
# (headers included polar-correlation-id / ratelimit-*) 404 from Polar's real infrastructure.
SLEEP: Final[str] = "/v3/users/sleep/{date}"
NIGHTLY_RECHARGE: Final[str] = "/v3/users/nightly-recharge/{date}"
CONTINUOUS_HEART_RATE: Final[str] = "/v3/users/continuous-heart-rate/{date}"
SKIN_TEMPERATURE: Final[str] = "/v3/users/biosensing/skintemperature"
SLEEPWISE_ALERTNESS: Final[str] = "/v3/users/sleepwise/alertness/date"
SLEEPWISE_CIRCADIAN_BEDTIME: Final[str] = "/v3/users/sleepwise/circadian-bedtime/date"

API_NAME: Final[str] = "polar-accesslink-v3"
