from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class SleepStages:
    light_seconds: int
    deep_seconds: int
    rem_seconds: int
    unrecognized_seconds: int

    def __post_init__(self) -> None:
        if self.light_seconds < 0:
            raise ValueError(f"light_seconds must be >= 0, got {self.light_seconds}")
        if self.deep_seconds < 0:
            raise ValueError(f"deep_seconds must be >= 0, got {self.deep_seconds}")
        if self.rem_seconds < 0:
            raise ValueError(f"rem_seconds must be >= 0, got {self.rem_seconds}")
        if self.unrecognized_seconds < 0:
            raise ValueError(f"unrecognized_seconds must be >= 0, got {self.unrecognized_seconds}")

    @property
    def total_seconds(self) -> int:
        return self.light_seconds + self.deep_seconds + self.rem_seconds + self.unrecognized_seconds

    @property
    def total_hours(self) -> float:
        return self.total_seconds / 3600

    @property
    def light_ratio(self) -> float:
        return self.light_seconds / self.total_seconds if self.total_seconds else 0.0

    @property
    def deep_ratio(self) -> float:
        return self.deep_seconds / self.total_seconds if self.total_seconds else 0.0

    @property
    def rem_ratio(self) -> float:
        return self.rem_seconds / self.total_seconds if self.total_seconds else 0.0
