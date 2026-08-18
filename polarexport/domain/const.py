from typing import Final

POLAR_HISTORY_WINDOW_DAYS: Final[int] = 28  # AccessLink v3 retention for sleep / recharge / sleepwise
EXPORT_DIR_NAME: Final[str] = "export"
ARCHIVE_NAME_TEMPLATE: Final[str] = "polarexport-nights-{date_min}_{date_max}.zip"
