from typing import Any
from typing import Self

import httpx


class WireMockContext:
    def __init__(self, base_url: str) -> None:
        self.admin_url = f"{base_url.rstrip('/')}/__admin"
        self._mapping_ids: list[str] = []

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any | None,
    ) -> None:
        for mapping_id in self._mapping_ids:
            httpx.delete(f"{self.admin_url}/mappings/{mapping_id}")
        self._mapping_ids.clear()

    def create_mapping(
        self,
        method: str,
        url_path: str,
        status: int,
        query_params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | list[Any] | None = None,
        priority: int = 1,
    ) -> None:
        body: dict[str, Any] = {
            "priority": priority,
            "request": {
                "method": method,
                "urlPath": url_path,
            },
            "response": {
                "status": status,
                "headers": {"Content-Type": "application/json"},
            },
        }
        if query_params:
            body["request"]["queryParameters"] = {k: {"equalTo": str(v)} for k, v in query_params.items()}
        if json_body is not None:
            body["response"]["jsonBody"] = json_body

        response = httpx.post(f"{self.admin_url}/mappings", json=body)
        response.raise_for_status()
        self._mapping_ids.append(response.json()["id"])

    def count_requests(self) -> int:
        response = httpx.get(f"{self.admin_url}/requests")
        response.raise_for_status()
        return len(response.json()["requests"])
