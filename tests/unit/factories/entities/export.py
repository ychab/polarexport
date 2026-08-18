from datetime import UTC
from datetime import datetime
from pathlib import Path

from polyfactory import Use
from polyfactory.factories.dataclass_factory import DataclassFactory

from polarexport.domain.entities.export import ExportManifest
from polarexport.domain.entities.export import ExportReport
from polarexport.domain.enums import NightSource
from polarexport.domain.enums import SourceAvailability

from tests.unit.factories.value_objects.date_range import DateRangeFactory


class ExportManifestFactory(DataclassFactory[ExportManifest]):
    __model__ = ExportManifest

    generated_at = Use(lambda: datetime(2026, 7, 20, tzinfo=UTC))
    date_range = Use(DateRangeFactory.build)
    sources_requested = Use(lambda: (NightSource.SLEEP,))
    source_availability = Use(lambda: {NightSource.SLEEP: SourceAvailability.AVAILABLE})
    request_counts = Use(lambda: {NightSource.SLEEP: 1})


class ExportReportFactory(DataclassFactory[ExportReport]):
    __model__ = ExportReport

    archive_path = Use(lambda: Path("export/polarexport-nights-2026-07-20_2026-07-27.zip"))
    archive_size_bytes = Use(DataclassFactory.__faker__.random_int, min=0, max=1_000_000)
    manifest = Use(ExportManifestFactory.build)
    # Randomly-generated Night/Sleep entities can violate cross-field invariants (e.g. sleep_start_time
    # after sleep_end_time) since nested union factories don't inherit those constructors' validation
    # awareness. Nothing here asserts on `nights`, so default to the same empty tuple as the entity.
    nights = Use(lambda: ())
