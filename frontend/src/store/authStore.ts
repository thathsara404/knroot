import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import type { UserProfile } from '../types'

interface AuthState {
  accessToken: string | null
  user: UserProfile | null
  setAuth: (token: string, user: UserProfile) => void
  setToken: (token: string) => void
  clearAuth: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      user: null,
      setAuth: (token, user) => set({ accessToken: token, user }),
      setToken: (token) => set((s) => ({ ...s, accessToken: token })),
      clearAuth: () => set({ accessToken: null, user: null }),
    }),
    {
      name: 'knroot-auth',
      storage: createJSONStorage(() => sessionStorage),
    }
  )
)
