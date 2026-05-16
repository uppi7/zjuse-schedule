// Dev 阶段固定身份；上线后由网关注入 X-User-Id / X-User-Role。
// 改 role 默认值即可切换视角（'ADMIN' | 'TEACHER' | 'STUDENT'），不要在此基础上加登录页。
import { defineStore } from 'pinia'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    userId: 'dev-admin-001',
    role: 'ADMIN',
  }),
  actions: {
    setUser(userId, role) {
      this.userId = userId
      this.role = role
    },
  },
})
