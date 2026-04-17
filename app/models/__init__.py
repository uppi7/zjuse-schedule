# 在此 import 所有模型，确保 Alembic autogenerate 能发现全部表定义。
from app.models.classroom import Classroom  # noqa: F401
from app.models.schedule import ScheduleTask, ScheduleEntry  # noqa: F401
