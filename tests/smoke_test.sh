#!/usr/bin/env bash
# smoke_test.sh — 集成冒烟测试（合并到 main 后手动执行）
# 用途：快速验证核心链路是否正常，约 30 秒完成
# 使用：bash tests/smoke_test.sh [BASE_URL]

set -e

BASE_URL="${1:-http://localhost:8002}"
ADMIN_HEADERS='-H "X-User-Id: smoke-admin" -H "X-User-Role: ADMIN"'
PASS=0
FAIL=0

_pass() { echo "  ✓ $1"; ((PASS++)); }
_fail() { echo "  ✗ $1"; ((FAIL++)); }

check() {
  local desc="$1" expected="$2"
  local actual
  actual=$(eval "$3" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('${4:-code}',''))" 2>/dev/null)
  [ "$actual" = "$expected" ] && _pass "$desc" || _fail "$desc (got: $actual)"
}

echo "=== 冒烟测试 ==> $BASE_URL ==="

# 1. 健康检查
echo ""
echo "【1】健康检查"
STATUS=$(curl -sf "$BASE_URL/health" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null)
[ "$STATUS" = "ok" ] && _pass "Health check" || _fail "Health check (got: $STATUS)"

# 2. 创建教室
echo ""
echo "【2】教室创建"
CODE=$(curl -sf -X POST "$BASE_URL/api/v1/classrooms" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: smoke-admin" -H "X-User-Role: ADMIN" \
  -d '{"code":"SMOKE01","name":"冒烟测试教室","building":"测试楼","capacity":50,"room_type":"LECTURE"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['code'])" 2>/dev/null)
[ "$CODE" = "0" ] && _pass "创建教室 SMOKE01" || _fail "创建教室 (code=$CODE)"

# 3. 查询教室列表
echo ""
echo "【3】教室查询"
CODE=$(curl -sf "$BASE_URL/api/v1/classrooms" \
  -H "X-User-Id: smoke-admin" -H "X-User-Role: ADMIN" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['code'])" 2>/dev/null)
[ "$CODE" = "0" ] && _pass "查询教室列表" || _fail "查询教室列表 (code=$CODE)"

# 4. 权限拦截
echo ""
echo "【4】权限控制"
HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/v1/classrooms" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: smoke-student" -H "X-User-Role: STUDENT" \
  -d '{"code":"X","name":"X","building":"X","capacity":10,"room_type":"LECTURE"}' 2>/dev/null || echo "403")
[ "$HTTP_CODE" = "403" ] && _pass "STUDENT 被拦截返回 403" || _fail "权限拦截 (got: $HTTP_CODE)"

# 5. 触发排课
echo ""
echo "【5】排课异步链路"
RESP=$(curl -sf -X POST "$BASE_URL/api/v1/schedule/auto-schedule" \
  -H "Content-Type: application/json" \
  -H "X-User-Id: smoke-admin" -H "X-User-Role: ADMIN" \
  -d '{"semester":"smoke-test-1"}' 2>/dev/null)
TASK_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])" 2>/dev/null)
[ -n "$TASK_ID" ] && _pass "触发排课，task_id=$TASK_ID" || _fail "触发排课失败"

# 6. 查询进度（等待最多 15 秒）
if [ -n "$TASK_ID" ]; then
  echo ""
  echo "【6】排课进度查询（最多等待 15 秒）"
  for i in {1..5}; do
    sleep 3
    STATUS=$(curl -sf "$BASE_URL/api/v1/schedule/schedule-status/$TASK_ID" \
      -H "X-User-Id: smoke-admin" -H "X-User-Role: ADMIN" \
      | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['status'])" 2>/dev/null)
    if [ "$STATUS" = "SUCCESS" ] || [ "$STATUS" = "FAILED" ]; then
      [ "$STATUS" = "SUCCESS" ] && _pass "排课完成，status=SUCCESS" || _fail "排课失败，status=FAILED"
      break
    fi
    echo "    等待中... status=$STATUS (${i}/5)"
  done
fi

# ── 汇总 ──────────────────────────────────────────────────────────────
echo ""
echo "==============================="
echo "通过: $PASS  失败: $FAIL"
[ "$FAIL" -eq 0 ] && echo "✅ 冒烟测试全部通过" || echo "❌ 有 $FAIL 项失败，请检查日志"
echo "==============================="
[ "$FAIL" -eq 0 ]
