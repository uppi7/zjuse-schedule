"""Unit tests for Gateway-backed upstream clients."""

import asyncio
from urllib.parse import urljoin

import pytest

from app.core import external_clients
from app.core.external_clients import InfoServiceClient

pytestmark = pytest.mark.unit


def test_info_client_logs_in_and_builds_scheduling_inputs(monkeypatch):
    fake_client = FakeAsyncClient()

    monkeypatch.setattr(
        external_clients.httpx,
        "AsyncClient",
        lambda *args, **kwargs: fake_client,
    )

    payloads = asyncio.run(_run_client())

    assert len(payloads) == 1
    assert payloads[0].offering_id == "101"
    assert payloads[0].course_id == "201"
    assert payloads[0].course_code == "CS201"
    assert payloads[0].course_name == "Algorithms"
    assert payloads[0].teacher_ids == ["T001"]
    assert payloads[0].student_count == 45
    assert payloads[0].room_requirements == [{"room_type": "LECTURE", "hours": 3}]
    assert fake_client.closed is True
    assert [call["path"] for call in fake_client.calls] == [
        "/auth/sys/login",
        "/api/v1/info/offerings/",
        "/api/v1/info/courses/201",
        "/api/v1/info/offerings/101/teachers",
    ]
    assert fake_client.calls[1]["headers"]["Authorization"] == "Bearer svc-token"


class FakeResponse:
    def __init__(self, body: dict, status_code: int = 200) -> None:
        self._body = body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._body


class FakeAsyncClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.closed = False

    async def post(self, path: str, **kwargs) -> FakeResponse:
        return await self.request("POST", path, **kwargs)

    async def get(self, path: str, **kwargs) -> FakeResponse:
        return await self.request("GET", path, **kwargs)

    async def request(self, method: str, path: str, **kwargs) -> FakeResponse:
        full_url = urljoin("http://gateway", path)
        self.calls.append(
            {
                "method": method,
                "path": "/" + full_url.split("/", 3)[3],
                "headers": kwargs.get("headers", {}),
                "params": kwargs.get("params", {}),
            }
        )
        if path == "/auth/sys/login":
            return FakeResponse({"code": 0, "data": {"service_token": "svc-token"}})
        if path == "/api/v1/info/offerings/":
            return FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "items": [
                            {
                                "id": 101,
                                "course_id": 201,
                                "capacity": 45,
                            }
                        ],
                        "pagination": {"total": 1, "page": 1, "page_size": 100},
                    },
                }
            )
        if path == "/api/v1/info/courses/201":
            return FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "id": 201,
                        "course_code": "CS201",
                        "course_name": "Algorithms",
                        "credit": 3,
                    },
                }
            )
        if path == "/api/v1/info/offerings/101/teachers":
            return FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "items": [
                            {"teacher_id": "T001", "offering_id": 101, "role_type": "instructor"}
                        ],
                        "pagination": {"total": 1, "page": 1, "page_size": 100},
                    },
                }
            )
        return FakeResponse({"message": "not found"}, status_code=404)

    async def aclose(self) -> None:
        self.closed = True


async def _run_client():
    client = InfoServiceClient()
    try:
        return await client.get_scheduling_inputs("2026-FALL")
    finally:
        await client.aclose()
