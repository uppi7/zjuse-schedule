// 开发阶段固定角色；真实上线后由网关注入
const AUTH_HEADERS = {
  'Content-Type': 'application/json',
  'X-User-Id': 'dev-admin-001',
  'X-User-Role': 'ADMIN',
}

async function request(method, path, body = null) {
  const res = await fetch(path, {
    method,
    headers: AUTH_HEADERS,
    body: body !== null ? JSON.stringify(body) : undefined,
  })
  const data = await res.json()
  if (!res.ok) {
    // 把 HTTP status 一起抛出，让调用方判断 409 / 403 等
    throw Object.assign(new Error(data.msg ?? res.statusText), { status: res.status, ...data })
  }
  return data
}

export const api = {
  /** POST /api/v1/schedule/auto-schedule → { data: { task_id } } */
  triggerSchedule: (semester) =>
    request('POST', '/api/v1/schedule/auto-schedule', { semester }),

  /** GET /api/v1/schedule/schedule-status/:taskId → { data: { status, progress, ... } } */
  getScheduleStatus: (taskId) =>
    request('GET', `/api/v1/schedule/schedule-status/${taskId}`),

  /** GET /api/v1/schedule/entries?semester=...&teacher_id=...&course_id=... */
  getEntries: (params) =>
    request('GET', `/api/v1/schedule/entries?${new URLSearchParams(params)}`),
}
