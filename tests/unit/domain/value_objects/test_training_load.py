from polarexport.domain.enums import LoadInterpretation
from polarexport.domain.value_objects.training_load import TrainingLoad


class TestTrainingLoad:
    def test__fields(self) -> None:
        load = TrainingLoad(
            cardio_load=81.1622,
            cardio_load_interpretation=LoadInterpretation.HIGH,
            muscle_load=None,
            muscle_load_interpretation=None,
            perceived_load=None,
            perceived_load_interpretation=None,
            user_rpe="UNKNOWN",
        )
        assert load.cardio_load == 81.1622
        assert load.cardio_load_interpretation == LoadInterpretation.HIGH
        assert load.user_rpe == "UNKNOWN"

    def test__defaults(self) -> None:
        load = TrainingLoad()
        assert load.cardio_load is None
        assert load.muscle_load is None
        assert load.perceived_load is None
        assert load.user_rpe is None
