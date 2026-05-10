import { create } from 'zustand'

interface AuthState {
  username: string
  isLoggedIn: boolean
}

export const useAuthStore = create<AuthState>(() => ({
  username: 'Admin',
  isLoggedIn: true,
}))
