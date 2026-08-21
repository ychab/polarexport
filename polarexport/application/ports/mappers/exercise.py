from abc import ABC
from abc import abstractmethod
from collections.abc import Mapping
from typing import Any

from polarexport.domain.entities.exercise import Exercise
from polarexport.domain.entities.profile import UserProfile


class ExerciseMapperPort(ABC):
    """A port for mapping raw Polar payloads to exercise domain entities.

    Mirrors `NightMapperPort`: the export use case reads raw payloads from the store and must turn
    them into entities without the application layer importing the Polar adapter directly, so a
    mapper fix applies retroactively to sessions already on disk.
    """

    @abstractmethod
    def to_exercises(self, payloads: Mapping[str, Mapping[str, Any]]) -> tuple[Exercise, ...]:
        """Map raw Polar exercise payloads to `Exercise` entities.

        Args:
            payloads: The raw payloads, keyed by exercise id.

        Returns:
            The mapped exercises. A payload that fails to map is skipped, not raised — one malformed
            session must not fail the whole export.
        """
        ...

    @abstractmethod
    def to_profile(self, payload: Mapping[str, Any]) -> UserProfile | None:
        """Map a raw Polar user-info payload to a `UserProfile` entity.

        Args:
            payload: The raw payload.

        Returns:
            The mapped profile, or `None` if the payload cannot be interpreted.
        """
        ...
