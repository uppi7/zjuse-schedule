"""
tests/unit/test_classrooms.py
教室接口单元测试（ASGITransport + SQLite in-memory，无外部依赖）
"""

import csv
import io
import uuid

import pytest
from httpx import AsyncClient
from openpyxl import Workbook

pytestmark = pytest.mark.unit


def _code(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _csv_bytes(rows: list[list[object]]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(rows)
    return output.getvalue().encode("utf-8")


def _xlsx_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    for row in rows:
        worksheet.append(row)
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


async def _find_classroom(client: AsyncClient, code: str) -> dict:
    resp = await client.get("/api/v1/classrooms", params={"limit": 1000})
    assert resp.status_code == 200
    for item in resp.json()["data"]:
        if item["code"] == code:
            return item
    raise AssertionError(f"Classroom {code} not found")


async def test_create_classroom(client: AsyncClient):
    resp = await client.post(
        "/api/v1/classrooms",
        json={
            "code": "101",
            "name": "琴房一",
            "campus": "紫金港",
            "building": "西教",
            "capacity": 120,
            "room_type": "LECTURE",
            "available_time": [{"day": 1, "slot": 1}, {"day": 1, "slot": 2}],
        },
    )
    assert resp.status_code == 201
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["code"] == "101"


async def test_create_classroom_duplicate_code(client: AsyncClient):
    payload = {
        "code": "202",
        "name": "202",
        "campus": "玉泉",
        "building": "教四",
        "capacity": 80,
        "room_type": "LECTURE",
        "available_time": [],
    }
    await client.post("/api/v1/classrooms", json=payload)
    resp = await client.post("/api/v1/classrooms", json=payload)
    assert resp.status_code == 200
    assert resp.json()["code"] == 2000


async def test_list_classrooms(client: AsyncClient):
    resp = await client.get("/api/v1/classrooms")
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


async def test_create_classroom_forbidden_for_student(student_client: AsyncClient):
    resp = await student_client.post(
        "/api/v1/classrooms",
        json={
            "code": "303",
            "name": "303",
            "campus": "玉泉",
            "building": "教七",
            "capacity": 60,
            "room_type": "LECTURE",
            "available_time": [],
        },
    )
    assert resp.status_code == 200
    assert resp.json()["code"] == 2012


async def test_batch_import_csv_success(client: AsyncClient):
    code = _code("B4CSV")
    content = _csv_bytes(
        [
            [
                "code",
                "name",
                "campus",
                "building",
                "capacity",
                "room_type",
                "available_time",
                "is_active",
            ],
            [code, "批量导入教室", "玉泉", "教三", 90, "LECTURE", "1-1,1-2,2-3", "true"],
        ]
    )

    resp = await client.post(
        "/api/v1/classrooms/batch-import",
        files={"file": ("classrooms.csv", content, "text/csv")},
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"] == {"success": 1, "failed": []}

    classroom = await _find_classroom(client, code)
    assert classroom["available_time"] == [
        {"day": 1, "slot": 1},
        {"day": 1, "slot": 2},
        {"day": 2, "slot": 3},
    ]


async def test_batch_import_xlsx_success(client: AsyncClient):
    code = _code("B4XLSX")
    content = _xlsx_bytes(
        [
            ["code", "name", "campus", "building", "capacity", "room_type", "available_time"],
            [code, "Excel 导入教室", "紫金港", "西教", 120, "COMPUTER_LAB", "3-4"],
        ]
    )

    resp = await client.post(
        "/api/v1/classrooms/batch-import",
        files={
            "file": (
                "classrooms.xlsx",
                content,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"] == {"success": 1, "failed": []}

    classroom = await _find_classroom(client, code)
    assert classroom["room_type"] == "COMPUTER_LAB"
    assert classroom["available_time"] == [{"day": 3, "slot": 4}]


async def test_batch_import_partial_failure(client: AsyncClient):
    valid_code = _code("B4OK")
    invalid_code = _code("B4BAD")
    content = _csv_bytes(
        [
            ["code", "name", "campus", "building", "capacity", "room_type", "available_time"],
            [valid_code, "有效教室", "玉泉", "教三", 60, "LECTURE", "1-1"],
            [invalid_code, "无效教室", "玉泉", "教三", "not-int", "LECTURE", "1-1"],
        ]
    )

    resp = await client.post(
        "/api/v1/classrooms/batch-import",
        files={"file": ("classrooms.csv", content, "text/csv")},
    )

    body = resp.json()
    assert resp.status_code == 200
    assert body["code"] == 0
    assert body["data"]["success"] == 1
    assert body["data"]["failed"][0]["row"] == 3
    assert body["data"]["failed"][0]["code"] == invalid_code
    assert "capacity" in body["data"]["failed"][0]["error"]
    await _find_classroom(client, valid_code)


async def test_batch_import_rejects_invalid_file_format(client: AsyncClient):
    resp = await client.post(
        "/api/v1/classrooms/batch-import",
        files={"file": ("classrooms.txt", b"not supported", "text/plain")},
    )

    assert resp.status_code == 200
    assert resp.json()["code"] == 2010


async def test_batch_import_rejects_oversized_file(client: AsyncClient):
    oversized = b"x" * (5 * 1024 * 1024 + 1)

    resp = await client.post(
        "/api/v1/classrooms/batch-import",
        files={"file": ("classrooms.csv", oversized, "text/csv")},
    )

    assert resp.status_code == 200
    assert resp.json()["code"] == 2010


async def test_batch_import_duplicate_code_skips_by_default(client: AsyncClient):
    code = _code("B4SKIP")
    payload = {
        "code": code,
        "name": "原教室",
        "campus": "玉泉",
        "building": "教三",
        "capacity": 80,
        "room_type": "LECTURE",
        "available_time": [],
    }
    create_resp = await client.post("/api/v1/classrooms", json=payload)
    assert create_resp.json()["code"] == 0

    content = _csv_bytes(
        [
            ["code", "name", "campus", "building", "capacity"],
            [code, "新教室", "紫金港", "西教", 120],
        ]
    )
    resp = await client.post(
        "/api/v1/classrooms/batch-import",
        files={"file": ("classrooms.csv", content, "text/csv")},
    )

    assert resp.json()["data"] == {"success": 0, "failed": []}
    classroom = await _find_classroom(client, code)
    assert classroom["name"] == "原教室"
    assert classroom["capacity"] == 80


async def test_batch_import_duplicate_code_overwrites_when_requested(client: AsyncClient):
    code = _code("B4OVER")
    payload = {
        "code": code,
        "name": "原教室",
        "campus": "玉泉",
        "building": "教三",
        "capacity": 80,
        "room_type": "LECTURE",
        "available_time": [],
    }
    create_resp = await client.post("/api/v1/classrooms", json=payload)
    assert create_resp.json()["code"] == 0

    content = _csv_bytes(
        [
            ["code", "name", "campus", "building", "capacity", "available_time"],
            [code, "覆盖教室", "紫金港", "西教", 120, "4-5"],
        ]
    )
    resp = await client.post(
        "/api/v1/classrooms/batch-import",
        params={"overwrite": "true"},
        files={"file": ("classrooms.csv", content, "text/csv")},
    )

    assert resp.json()["data"] == {"success": 1, "failed": []}
    classroom = await _find_classroom(client, code)
    assert classroom["name"] == "覆盖教室"
    assert classroom["building"] == "西教"
    assert classroom["capacity"] == 120
    assert classroom["available_time"] == [{"day": 4, "slot": 5}]


async def test_available_time_roundtrip_create_get_update_get(client: AsyncClient):
    code = _code("B4ROUND")
    initial_slots = [{"day": 1, "slot": 1}, {"day": 2, "slot": 3}]
    updated_slots = [{"day": 5, "slot": 6}, {"day": 7, "slot": 12}]

    create_resp = await client.post(
        "/api/v1/classrooms",
        json={
            "code": code,
            "name": "可用时间测试教室",
            "campus": "玉泉",
            "building": "教三",
            "capacity": 50,
            "room_type": "LECTURE",
            "available_time": initial_slots,
        },
    )
    classroom_id = create_resp.json()["data"]["id"]

    get_resp = await client.get(f"/api/v1/classrooms/{classroom_id}")
    assert get_resp.json()["data"]["available_time"] == initial_slots

    patch_resp = await client.patch(
        f"/api/v1/classrooms/{classroom_id}",
        json={"available_time": updated_slots},
    )
    assert patch_resp.json()["data"]["available_time"] == updated_slots

    get_again = await client.get(f"/api/v1/classrooms/{classroom_id}")
    assert get_again.json()["data"]["available_time"] == updated_slots


async def test_update_classroom_building(client: AsyncClient):
    code = _code("B4BUILD")
    create_resp = await client.post(
        "/api/v1/classrooms",
        json={
            "code": code,
            "name": "楼栋测试教室",
            "campus": "玉泉",
            "building": "旧楼",
            "capacity": 50,
            "room_type": "LECTURE",
            "available_time": [],
        },
    )
    classroom_id = create_resp.json()["data"]["id"]

    patch_resp = await client.patch(
        f"/api/v1/classrooms/{classroom_id}",
        json={"building": "新楼"},
    )

    assert patch_resp.status_code == 200
    assert patch_resp.json()["code"] == 0
    assert patch_resp.json()["data"]["building"] == "新楼"
