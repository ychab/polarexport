from dataclasses import dataclass

from polarexport.domain.enums import LoadInterpretation


@dataclass(frozen=True, kw_only=True)
class TrainingLoad:
    cardio_load: float | None = None
    cardio_load_interpretation: LoadInterpretation | None = None
    muscle_load: float | None = None
    muscle_load_interpretation: LoadInterpretation | None = None
    perceived_load: float | None = None
    perceived_load_interpretation: LoadInterpretation | None = None
    user_rpe: str | None = None
