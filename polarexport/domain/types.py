from datetime import datetime

type Hypnogram = dict[str, int]  # "HH:MM" -> SleepStage value, as Polar returns it
type HeartRateSample = tuple[datetime, int]
type HeartRateByTime = dict[str, int]  # "HH:MM" -> bpm, Polar's own sleep-window series
type IsoDateStr = str
