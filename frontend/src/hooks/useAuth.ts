import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login, register, logout } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import type { LoginPayload, RegisterPayload } from '../types'

export function useAuth() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string> | null>(null)

  const { setAuth, clearAuth } = useAuthStore()
  const navigate = useNavigate()

  async function signIn(payload: LoginPayload): Promise<void> {
    setIsLoading(true)
    setError(null)
    setFieldErrors(null)
    try {
      const data = await login(payload)
      setAuth(data.access_token, data.user)
      navigate('/app')
    } catch (err: unknown) {
      const e = err as Error & { fields?: Record<string, string> }
      setFieldErrors(e.fields ?? null)
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }

  async function signUp(payload: RegisterPayload): Promise<void> {
    setIsLoading(true)
    setError(null)
    setFieldErrors(null)
    try {
      const data = await register(payload)
      setAuth(data.access_token, data.user)
      navigate('/app')
    } catch (err: unknown) {
      const e = err as Error & { fields?: Record<string, string> }
      setFieldErrors(e.fields ?? null)
      setError(e.message)
    } finally {
      setIsLoading(false)
    }
  }

  async function signOut(): Promise<void> {
    try { await logout() } catch { /* ignore */ }
    clearAuth()
    navigate('/login')
  }

  return { isLoading, error, fieldErrors, signIn, signUp, signOut }
}
