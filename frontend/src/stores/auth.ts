import { create } from 'zustand'

interface AuthState {
  username: string
  isLoggedIn: boolean
  cookieConfigured: boolean
  setCookieConfigured: (v: boolean) => void
}

export const useAuthStore = create<AuthState>((set) => ({
  username: 'Admin',
  isLoggedIn: true,
  cookieConfigured: localStorage.getItem('xhs_cookie_configured') === '1',
  setCookieConfigured: (v: boolean) => {
    if (v) localStorage.setItem('xhs_cookie_configured', '1')
    else localStorage.removeItem('xhs_cookie_configured')
    set({ cookieConfigured: v })
  },
}))
