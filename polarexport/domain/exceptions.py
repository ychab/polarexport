class PolarExportError(Exception): ...


class InvalidDateRangeError(PolarExportError): ...


class NoNightDataError(PolarExportError): ...  # every requested date came back empty


class ArchiveAlreadyExistsError(PolarExportError): ...  # target zip exists and --force not given
