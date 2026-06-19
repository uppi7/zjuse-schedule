"""Seed Schedule DB data required by the cross-service integration stack."""

from __future__ import annotations

import asyncio

from sqlalchemy.dialects.mysql import insert

from app.core.database import AsyncSessionLocal, engine, init_db
from app.models.classroom import Classroom, ClassroomType


async def main() -> None:
    try:
        await init_db()
        available_time = [
            {"day": day, "slot": slot}
            for day in range(1, 6)
            for slot in range(1, 13)
        ]
        async with AsyncSessionLocal() as db:
            stmt = insert(Classroom).values(
                code="AUTO-L-101",
                name="Integration Lecture Room",
                campus="Yuquan",
                building="Integration Building",
                capacity=120,
                room_type=ClassroomType.LECTURE,
                available_time=available_time,
                is_active=True,
            )
            stmt = stmt.on_duplicate_key_update(
                name=stmt.inserted.name,
                campus=stmt.inserted.campus,
                building=stmt.inserted.building,
                capacity=stmt.inserted.capacity,
                room_type=stmt.inserted.room_type,
                available_time=stmt.inserted.available_time,
                is_active=True,
            )
            await db.execute(stmt)
            await db.commit()
        print("Schedule integration seed ready: classroom=AUTO-L-101")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
