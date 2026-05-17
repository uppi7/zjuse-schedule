# Golden case 占位模板

把这个目录复制为 `tests/solver/fixtures/golden/<case_name>/`（无前缀下划线），
然后修改 `input.json` 和 `expected.json`。

下划线开头的目录会被 `discover_golden_cases()` 跳过，不会进入测试用例

## 字段对照

### input.json

```jsonc
{
  "courses": [
    {
      "course_id": "C001",
      "teacher_ids": ["T001"],   // list[str]，合上课多教师
      "student_count": 30,
      "room_requirements": [     // 每项 {room_type, hours}，hours 是每周总学时
        {"room_type": "LECTURE", "hours": 2}
      ]
    }
  ],
  "classrooms": [
    {
      "classroom_id": 1,
      "campus": "玉泉",
      "capacity": 60,
      "room_type": "LECTURE",    // 取值见 RoomType 枚举（LECTURE / LAB_* / COMPUTER_LAB / GYM）
      "available_slots": [[1, 1], [1, 2], [2, 3]]  // [[day, slot], ...]
    }
  ],
  "preferences": [
    {
      "teacher_id": "T001",
      "semester": "2024-2025-1",
      "course_id": "C001",
      "day_of_week": 1,
      "slot_start": 1,
      "slot_end": 2,
      "is_negative": false
    }
  ]
}
```

### expected.json

```jsonc
{
  "scheduled_count": 1,         // 期望 run_schedule 返回的 ScheduleResult 数
  "unscheduled_ids": [],        // 期望未能排课的 course_id 列表
  "max_conflicts": 0,           // 允许的硬冲突上限（教师/教室同时段）
  "extra": {}                   // 额外断言由 test 函数读取，自由扩展
}
```

## 测试用例示例（建议产出 ≥5 个 case）

- [ ] `simple_small`        — 3 课 / 2 教室，全部可排
- [ ] `simple_medium`       — 20 课 / 8 教室，全部可排
- [ ] `with_conflicts`      — 故意构造教师同时段冲突，max_conflicts > 0 验证软冲突逻辑
- [ ] `with_neg_preference` — 含 is_negative=True 偏好，期望解避开禁忌时段
- [ ] `infeasible`          — 容量不足/无可用时段，scheduled_count=0、unscheduled_ids 非空