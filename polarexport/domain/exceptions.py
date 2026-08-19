class PolarExportError(Exception): ...


class InvalidDateRangeError(PolarExportError): ...


class NoNightDataError(PolarExportError): ...  # every requested date came back empty


class ArchiveAlreadyExistsError(PolarExportError): ...  # target zip exists and --force not given


class ProviderRateLimitError(PolarExportError): ...  # a data source rate-limited us after retries were exhausted


class MissingCredentialsError(PolarExportError): ...  # neither the settings nor the credentials file yielded a token


class AuthorizationTimeoutError(PolarExportError): ...  # local callback listener timed out waiting for the browser


class AuthorizationStateMismatchError(PolarExportError): ...  # callback state didn't match the one we sent


class AuthorizationDeniedError(PolarExportError): ...  # user declined consent on Polar's authorization screen


class CredentialsAlreadyExistError(PolarExportError): ...  # credentials file already has a token; rerun with --force
