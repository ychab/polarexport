from polarexport.application.ports.providers.exercise import ExerciseFetchResult
from polarexport.domain.enums import SourceAvailability


class TestExerciseFetchResult:
    def test__fields(self) -> None:
        result = ExerciseFetchResult(
            payloads={"54klrKbL": {"foo": "bar"}},
            availability=SourceAvailability.AVAILABLE,
            request_count=1,
        )

        assert result.payloads == {"54klrKbL": {"foo": "bar"}}
        assert result.availability is SourceAvailability.AVAILABLE
        assert result.request_count == 1
