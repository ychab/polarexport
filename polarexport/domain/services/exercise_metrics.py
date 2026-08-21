from collections.abc import Sequence

from polarexport.domain.value_objects.heart_rate_stats import HeartRateStats


def parse_sample_series(data: str) -> tuple[float | None, ...]:
    """Split Polar's comma-separated sample string.

    Polar's swagger states the list "can contain null-values which indicate a situation where sensor
    was offline" — those become `None`, as do empty segments. A value that is present but not numeric
    is also `None`; one bad reading must not discard the series.
    """
    samples: list[float | None] = []
    for segment in data.split(","):
        stripped = segment.strip()
        if not stripped or stripped.lower() == "null":
            samples.append(None)
            continue
        try:
            samples.append(float(stripped))
        except ValueError:
            samples.append(None)
    return tuple(samples)


def heart_rate_stats(
    samples: Sequence[float | None], *, api_average: int | None, api_maximum: int | None
) -> HeartRateStats:
    """Combine Polar's own average/maximum with a minimum derived from the samples.

    Polar's figures win where they exist — they are what Polar Flow shows and what the account export
    agrees with. Only the minimum is genuinely ours.

    Non-positive samples are discarded before taking the minimum: a 0 bpm reading is a sensor
    dropout, not a heart rate, and a "minimum: 0" in the archive would be actively misleading.
    """
    positive_samples = [sample for sample in samples if sample is not None and sample > 0]
    minimum = round(min(positive_samples)) if positive_samples else None
    return HeartRateStats(average=api_average, maximum=api_maximum, minimum=minimum)


def downsample_per_minute(
    samples: Sequence[float | None], *, recording_rate_seconds: int | None
) -> tuple[int | None, ...]:
    """Average the sample series into one rounded value per minute.

    The full 1 Hz series is ~5 000 values per session and is deliberately kept out of the archive; a
    per-minute curve is ~87 values for the same session and is what lets an agent see the *shape* of
    an effort — warm-up, intervals, fade — instead of only its totals.

    A bucket whose samples are all missing yields `None`, not 0. Returns an empty tuple when
    `recording_rate_seconds` is `None` (Polar documents this for RR data), zero, or greater than 60.
    """
    if not recording_rate_seconds or recording_rate_seconds > 60:
        return ()
    bucket_size = 60 // recording_rate_seconds

    per_minute: list[int | None] = []
    for start in range(0, len(samples), bucket_size):
        bucket = [value for value in samples[start : start + bucket_size] if value is not None]
        per_minute.append(round(sum(bucket) / len(bucket)) if bucket else None)
    return tuple(per_minute)
