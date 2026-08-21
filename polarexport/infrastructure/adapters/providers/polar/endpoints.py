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

# Verified live on 2026-08-20. The transactional `/v3/users/{user-id}/exercise-transactions` path is
# deliberately not used — Polar's swagger marks it deprecated, GET returns 405, and committing a
# transaction consumes the data for the client, destroying the ability to re-fetch it.
EXERCISES: Final[str] = "/v3/exercises"
USER: Final[str] = "/v3/users/{user_id}"
