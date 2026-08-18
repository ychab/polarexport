from pathlib import Path

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from polarexport.application.inputs.night import NightExportInput
from polarexport.application.inputs.night import NightSyncInput
from polarexport.domain.enums import NightSource

from tests.unit.factories.value_objects.date_range import DateRangeFactory


class NightSyncInputFactory(ModelFactory[NightSyncInput]):
    __model__ = NightSyncInput

    date_range = Use(DateRangeFactory.build)
    sources = Use(lambda: frozenset(NightSource))
    force_refresh = False
    limit = None


class NightExportInputFactory(ModelFactory[NightExportInput]):
    __model__ = NightExportInput

    date_range = Use(DateRangeFactory.build)
    sources = Use(lambda: frozenset(NightSource))
    output_dir = Use(lambda: Path("export"))
    include_raw = True
    force = False
    limit = None
