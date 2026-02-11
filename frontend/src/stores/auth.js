import { defineStore } from 'pinia'
import { api } from '../api/client'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: null,
    loading: false,
  }),
  actions: {
    async refresh() {
      this.loading = true
      try {
        const { data } = await api.get('/api/auth/me')
        this.user = data.user
      } finally {
        this.loading = false
      }
    },
    async login(username, password) {
      const { data } = await api.post('/api/auth/login', { username, password })
      if (!data.ok) throw new Error(data.msg || '登录失败')
      this.user = data.user
    },
    async register(username, password) {
      const { data } = await api.post('/api/auth/register', { username, password })
      if (!data.ok) throw new Error(data.msg || '注册失败')
      this.user = data.user
    },
    async logout() {
      await api.post('/api/auth/logout')
      this.user = null
    },
  },
})

