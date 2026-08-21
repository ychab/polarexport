from typing import Final

POLAR_HISTORY_WINDOW_DAYS: Final[int] = 28  # AccessLink v3 retention for sleep / recharge / sleepwise
EXPORT_DIR_NAME: Final[str] = "export"
ARCHIVE_NAME_TEMPLATE: Final[str] = "polarexport-nights-{date_min}_{date_max}.zip"
API_NAME: Final[str] = "polar-accesslink-v3"
CREDENTIALS_FILENAME: Final[str] = "credentials.json"

POLAR_EXERCISE_WINDOW_DAYS: Final[int] = 30  # /v3/exercises retention — NOT the nights' 28
EXERCISE_ARCHIVE_NAME_TEMPLATE: Final[str] = "polarexport-exercises-{date_min}_{date_max}.zip"
EXERCISE_DIR_NAME: Final[str] = "exercise"
PROFILE_FILENAME: Final[str] = "profile.json"
