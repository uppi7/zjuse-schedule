"""
tests/solver/test_solver_golden.py
参数化跑 fixtures/golden/* 下所有 case，对 run_schedule() 做回归。

Owner: tester
覆盖目标：solver 算法在 ≥5 个代表性输入下的输出稳定性。
"""

import pytest

from app.algorithm.engine import run_schedule
from tests.solver.conftest import (
    discover_golden_cases,
    load_golden_case,
    assert_solver_result,
)

pytestmark = pytest.mark.solver


GOLDEN_CASES = discover_golden_cases()


@pytest.mark.parametrize(
    "case_dir",
    GOLDEN_CASES,
    ids=[p.name for p in GOLDEN_CASES] if GOLDEN_CASES else ["no-cases"],
)
def test_solver_golden_case(case_dir):
    """对每个 golden case 跑 solver 并校验输出。"""
    if not GOLDEN_CASES:
        pytest.skip("尚无 golden case：在 tests/solver/fixtures/golden/ 下添加 case 目录")

    solver_input, expected = load_golden_case(case_dir)
    results, unscheduled = run_schedule(
        solver_input.courses,
        solver_input.classrooms,
        solver_input.preferences,
    )
    assert_solver_result(results, unscheduled, expected)


def test_minimal_input_does_not_crash():
    """smoke级：最小输入应当 run_schedule 不抛异常。与 golden case 解耦的兜底用例"""
    from tests.factories import make_minimal_solver_input

    courses, classrooms, preferences = make_minimal_solver_input()
    results, unscheduled = run_schedule(courses, classrooms, preferences)

    assert isinstance(results, list)
    assert isinstance(unscheduled, list)
    assert len(results) + len(unscheduled) == len(courses)
