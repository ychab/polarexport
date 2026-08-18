class PolarApiError(Exception): ...


class PolarNotFoundError(PolarApiError): ...  # 404 — no data for that date


class PolarForbiddenError(PolarApiError): ...  # 403 — consent missing for this source


class PolarRateLimitError(PolarApiError): ...  # 429 after retries exhausted
