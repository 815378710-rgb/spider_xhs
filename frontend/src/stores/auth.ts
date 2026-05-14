import { create } from 'zustand'

interface AuthState {
  token: string | null
  username: string
  role: string
  isLoggedIn: boolean
  login: (token: string, username: string, role: string) => void
  logout: () => void
  setRole: (role: string) => void
  setCookieConfigured: () => void
}

function loadAuth() {
  try {
    const token = localStorage.getItem('xhs_token')
    const username = localStorage.getItem('xhs_username') || ''
    const role = localStorage.getItem('xhs_role') || 'user'
    // Also check if user explicitly skipped login
    const skipped = localStorage.getItem('xhs_skipped_login') === '1'
    if (skipped && !token) {
      return { token: 'skipped', username: '访客', role: 'user', isLoggedIn: true }
    }
    return { token, username, role, isLoggedIn: !!token }
  } catch {
    return { token: null, username: '', role: 'user', isLoggedIn: false }
  }
}

export const useAuthStore = create<AuthState>((set) => ({
  ...loadAuth(),
  cookieConfigured: true, // kept for compatibility, always true now
  setCookieConfigured: () => {
    // Mark as skipped login so auth persists across reloads
    localStorage.setItem('xhs_skipped_login', '1')
    localStorage.setItem('xhs_token', 'skipped')
    localStorage.setItem('xhs_username', '访客')
    localStorage.setItem('xhs_role', 'user')
  },
  login: (token, username, role) => {
    localStorage.setItem('xhs_token', token)
    localStorage.setItem('xhs_username', username)
    localStorage.setItem('xhs_role', role)
    set({ token, username, role, isLoggedIn: true })
  },
  logout: () => {
    localStorage.removeItem('xhs_token')
    localStorage.removeItem('xhs_username')
    localStorage.removeItem('xhs_role')
    localStorage.removeItem('xhs_skipped_login')
    set({ token: null, username: '', role: 'user', isLoggedIn: false })
  },
  setRole: (role) => {
    localStorage.setItem('xhs_role', role)
    set({ role })
  },
}))
