from datetime import date

from polarexport.application.ports.providers.night import SourceFetchResult
from polarexport.domain.enums import SourceAvailability


class TestSourceFetchResult:
    def test__fields(self) -> None:
        result = SourceFetchResult(
            payloads={date(2026, 7, 20): {"foo": "bar"}},
            availability=SourceAvailability.AVAILABLE,
            request_count=1,
        )

        assert result.payloads == {date(2026, 7, 20): {"foo": "bar"}}
        assert result.availability is SourceAvailability.AVAILABLE
        assert result.request_count == 1
