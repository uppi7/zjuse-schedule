import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

export class BizError extends Error {
  constructor(code, msg, data) {
    super(msg)
    this.name = 'BizError'
    this.code = code
    this.msg = msg
    this.data = data
  }
}

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

http.interceptors.request.use((config) => {
  const auth = useAuthStore()
  config.headers['X-User-Id'] = auth.userId
  config.headers['X-User-Role'] = auth.role
  return config
})

http.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code === 0) return body.data
      ElMessage.error(`[${body.code}] ${body.msg}`)
      return Promise.reject(new BizError(body.code, body.msg, body.data))
    }
    return body
  },
  (err) => {
    const status = err.response?.status
    ElMessage.error(`网络异常: ${status ?? err.message}`)
    return Promise.reject(err)
  },
)

export default http
