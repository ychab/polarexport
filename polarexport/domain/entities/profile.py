from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, kw_only=True)
class UserProfile:
    user_id: str
    birthdate: date | None = None
    gender: str | None = None
    height_cm: float | None = None
    weight_kg: float | None = None

    def age(self, *, on: date) -> int | None:
        if self.birthdate is None:
            return None
        years = on.year - self.birthdate.year
        if (on.month, on.day) < (self.birthdate.month, self.birthdate.day):
            years -= 1
        return years

    def estimated_max_heart_rate(self, *, on: date) -> int | None:
        """The classic `220 - age` estimate.

        It is a population formula with a standard deviation of roughly 10 bpm, not this user's
        measured maximum — the archive README must say so, and nothing should present a derived
        "% of max" as precise.
        """
        age = self.age(on=on)
        if age is None:
            return None
        return 220 - age
