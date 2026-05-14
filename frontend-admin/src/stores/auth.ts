import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import client from '../api/client'

interface AuthState {
  token: string
  username: string
  role: string
  isLoggedIn: boolean
  _hydrated: boolean
  login: (username: string, password: string) => Promise<boolean>
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: '',
      username: '',
      role: '',
      isLoggedIn: false,
      _hydrated: false,
      login: async (username, password) => {
        try {
          const r = await client.post('/auth/admin-login', { username, password })
          if (r.data.success) {
            const { token, user } = r.data.data
            localStorage.setItem('admin_token', token)
            set({ token, username: user.username, role: user.role, isLoggedIn: true })
            return true
          }
          return false
        } catch {
          return false
        }
      },
      logout: () => {
        localStorage.removeItem('admin_token')
        set({ token: '', username: '', role: '', isLoggedIn: false })
      },
    }),
    {
      name: 'admin-auth',
      onRehydrateStorage: () => {
        // 返回回调：hydration 完成后设置 _hydrated = true
        return (_state, _error) => {
          useAuthStore.setState({ _hydrated: true })
        }
      },
    }
  )
)

// 兜底：如果 onRehydrateStorage 没触发，200ms 后强制标记为已水合
setTimeout(() => {
  if (!useAuthStore.getState()._hydrated) {
    useAuthStore.setState({ _hydrated: true })
  }
}, 200)
