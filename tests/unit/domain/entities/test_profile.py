from datetime import date

from polarexport.domain.entities.profile import UserProfile


class TestUserProfileAge:
    def test__birthday_already_passed_this_year(self) -> None:
        profile = UserProfile(user_id="60233839", birthdate=date(1987, 6, 22))
        assert profile.age(on=date(2026, 8, 20)) == 39

    def test__day_before_birthday(self) -> None:
        profile = UserProfile(user_id="60233839", birthdate=date(1987, 6, 22))
        assert profile.age(on=date(2026, 6, 21)) == 38

    def test__no_birthdate__returns_none(self) -> None:
        profile = UserProfile(user_id="60233839")
        assert profile.age(on=date(2026, 8, 20)) is None


class TestUserProfileEstimatedMaxHeartRate:
    def test__derived_from_age(self) -> None:
        profile = UserProfile(user_id="60233839", birthdate=date(1987, 6, 22))
        assert profile.estimated_max_heart_rate(on=date(2026, 8, 20)) == 181

    def test__no_birthdate__returns_none(self) -> None:
        profile = UserProfile(user_id="60233839")
        assert profile.estimated_max_heart_rate(on=date(2026, 8, 20)) is None
