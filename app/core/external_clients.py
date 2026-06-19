"""
app/core/external_clients.py
Gateway-backed HTTP clients for upstream Auth and Info services.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from app.algorithm.engine import RoomType
from app.core.config import settings


@dataclass(frozen=True)
class OfferingSchedulePayload:
    """Stable upstream DTO consumed by the scheduler worker."""

    offering_id: str
    course_id: str
    course_code: str | None
    course_name: str | None
    teacher_ids: list[str]
    student_count: int
    room_requirements: list[dict[str, Any]]


class InfoServiceClient:
    """Access Info Service through Gateway using a Schedule service token."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.GATEWAY_BASE_URL.rstrip("/"),
            timeout=10.0,
        )
        self._service_token: str | None = None

    async def _get_service_token(self) -> str:
        if self._service_token:
            return self._service_token

        resp = await self._client.post(
            settings.AUTH_SYS_LOGIN_PATH,
            json={
                "client_id": settings.SCHEDULE_SERVICE_CLIENT_ID,
                "client_secret": settings.SCHEDULE_SERVICE_CLIENT_SECRET,
            },
        )
        resp.raise_for_status()
        data = self._unwrap(resp.json())
        token = data.get("access_token") or data.get("service_token") or data.get("token")
        if not token:
            raise ValueError("Auth service response did not include access_token")
        self._service_token = str(token)
        return self._service_token

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        token = await self._get_service_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        resp = await self._client.request(method, path, headers=headers, **kwargs)
        resp.raise_for_status()
        return self._unwrap(resp.json())

    @staticmethod
    def _unwrap(body: Any) -> Any:
        if isinstance(body, dict) and "data" in body:
            return body["data"]
        return body

    @staticmethod
    def _items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, dict) and "items" in payload:
            return list(payload["items"])
        if isinstance(payload, list):
            return payload
        raise ValueError(f"Expected list response payload, got {type(payload).__name__}")

    async def list_offerings(self, term_code: str) -> list[dict[str, Any]]:
        return await self._paginate(
            settings.INFO_OFFERINGS_PATH,
            {"term_code": term_code, "status": "ACTIVE"},
        )

    async def list_courses_by_ids(self, course_ids: set[str]) -> dict[str, dict[str, Any]]:
        courses: dict[str, dict[str, Any]] = {}
        for course_id in sorted(course_ids):
            data = await self._request("GET", f"{settings.INFO_COURSES_PATH}{course_id}")
            courses[str(data["id"])] = data
        return courses

    async def list_offering_teachers(self, offering_id: str) -> list[dict[str, Any]]:
        path = settings.INFO_OFFERING_TEACHERS_PATH_TEMPLATE.format(
            offering_id=offering_id,
        )
        return await self._paginate(path, {})

    async def get_scheduling_inputs(self, term_code: str) -> list[OfferingSchedulePayload]:
        offerings = await self.list_offerings(term_code)
        course_ids = {str(item["course_id"]) for item in offerings}
        course_map = await self.list_courses_by_ids(course_ids)

        payloads: list[OfferingSchedulePayload] = []
        for offering in offerings:
            offering_id = str(offering["id"])
            course_id = str(offering["course_id"])
            course = course_map.get(course_id)
            if not course:
                raise ValueError(f"Course {course_id} for offering {offering_id} not found")

            teachers = await self.list_offering_teachers(offering_id)
            credit = course.get("credit")
            room_requirements = [
                {
                    "room_type": RoomType.LECTURE.value,
                    "hours": credit,
                }
            ]
            payloads.append(
                OfferingSchedulePayload(
                    offering_id=offering_id,
                    course_id=course_id,
                    course_code=course.get("course_code"),
                    course_name=course.get("course_name"),
                    teacher_ids=[str(item["teacher_id"]) for item in teachers],
                    student_count=int(offering.get("capacity") or 0),
                    room_requirements=room_requirements,
                )
            )
        return payloads

    async def _paginate(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        page = 1
        page_size = 100
        items: list[dict[str, Any]] = []

        while True:
            payload = await self._request(
                "GET",
                path,
                params={**params, "page": page, "page_size": page_size},
            )
            batch = self._items(payload)
            items.extend(batch)

            pagination = payload.get("pagination") if isinstance(payload, dict) else None
            if not pagination:
                break

            total = int(pagination.get("total") or len(items))
            current_page = int(pagination.get("page") or page)
            current_page_size = int(pagination.get("page_size") or page_size)
            if len(items) >= total or len(batch) < current_page_size:
                break
            page = current_page + 1

        return items

    async def aclose(self) -> None:
        await self._client.aclose()
