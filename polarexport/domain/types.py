from datetime import datetime

type Hypnogram = dict[str, int]  # "HH:MM" -> SleepStage value, as Polar returns it
type HeartRateSample = tuple[datetime, int]
type SkinTemperatureSample = tuple[datetime, float]
type AlertnessHour = tuple[int, str]
type IsoDateStr = str
