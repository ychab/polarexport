import re

_ISO_TIME_DURATION_PATTERN = re.compile(
    r"^PT(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+(?:\.\d+)?)S)?$"
)


def parse_iso_duration(value: str) -> float | None:
    """Parse an ISO-8601 duration into seconds.

    Polar emits only the time portion — `PT5221.533S`, `PT16M18S`, `PT2H44M`, `PT0S`. Anything with a
    date component (`P1D`) or that does not parse returns `None`; it has never been observed and
    guessing is worse than reporting nothing.
    """
    match = _ISO_TIME_DURATION_PATTERN.match(value)
    if match is None:
        return None
    hours, minutes, seconds = match.group("hours"), match.group("minutes"), match.group("seconds")
    if hours is None and minutes is None and seconds is None:
        return None
    total_seconds = 0.0
    if hours is not None:
        total_seconds += int(hours) * 3600
    if minutes is not None:
        total_seconds += int(minutes) * 60
    if seconds is not None:
        total_seconds += float(seconds)
    return total_seconds
