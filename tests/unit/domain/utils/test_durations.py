import pytest

from polarexport.domain.utils.durations import parse_iso_duration


class TestParseIsoDuration:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("PT5221.533S", 5221.533),
            ("PT16M18S", 978.0),
            ("PT2H44M", 9840.0),
            ("PT0S", 0.0),
        ],
    )
    def test__valid_durations(self, value: str, expected: float) -> None:
        assert parse_iso_duration(value) == expected

    @pytest.mark.parametrize("value", ["P1D", "nonsense", "", "PT"])
    def test__unparseable__returns_none(self, value: str) -> None:
        assert parse_iso_duration(value) is None
