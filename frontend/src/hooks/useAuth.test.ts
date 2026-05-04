import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useAuth } from './useAuth'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', () => ({ useNavigate: () => mockNavigate }))

const mockSetAuth = vi.fn()
const mockClearAuth = vi.fn()
vi.mock('../store/authStore', () => ({
  useAuthStore: () => ({ setAuth: mockSetAuth, clearAuth: mockClearAuth }),
}))

const mockLogin = vi.fn()
const mockRegister = vi.fn()
const mockLogout = vi.fn()
vi.mock('../api/auth', () => ({
  login: (...a: unknown[]) => mockLogin(...a),
  register: (...a: unknown[]) => mockRegister(...a),
  logout: (...a: unknown[]) => mockLogout(...a),
}))

const FAKE_USER = {
  id: 'u1',
  username: 'alice',
  email: 'alice@example.com',
  phone: null,
  full_name: 'Alice',
  created_at: '2026-01-01T00:00:00Z',
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('useAuth – signIn', () => {
  it('calls login, stores auth, navigates to /app on success', async () => {
    mockLogin.mockResolvedValue({ access_token: 'tok', user: FAKE_USER })
    const { result } = renderHook(() => useAuth())

    await act(() => result.current.signIn({ identifier: 'alice', password: 'pass' }))

    expect(mockLogin).toHaveBeenCalledWith({ identifier: 'alice', password: 'pass' })
    expect(mockSetAuth).toHaveBeenCalledWith('tok', FAKE_USER)
    expect(mockNavigate).toHaveBeenCalledWith('/app')
    expect(result.current.error).toBeNull()
  })

  it('sets error state on login failure', async () => {
    const err = Object.assign(new Error('Invalid credentials'), { fields: null })
    mockLogin.mockRejectedValue(err)
    const { result } = renderHook(() => useAuth())

    await act(() => result.current.signIn({ identifier: 'x', password: 'y' }))

    expect(result.current.error).toBe('Invalid credentials')
    expect(mockSetAuth).not.toHaveBeenCalled()
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('sets fieldErrors when server returns field-level errors', async () => {
    const err = Object.assign(new Error('Validation failed'), {
      fields: { email: 'Already taken' },
    })
    mockLogin.mockRejectedValue(err)
    const { result } = renderHook(() => useAuth())

    await act(() => result.current.signIn({ identifier: 'x', password: 'y' }))

    expect(result.current.fieldErrors).toEqual({ email: 'Already taken' })
  })

  it('sets isLoading=true during request and false after', async () => {
    let resolve!: (v: unknown) => void
    mockLogin.mockReturnValue(new Promise((r) => { resolve = r }))
    const { result } = renderHook(() => useAuth())

    act(() => { result.current.signIn({ identifier: 'x', password: 'y' }) })
    expect(result.current.isLoading).toBe(true)

    await act(() => { resolve({ access_token: 'tok', user: FAKE_USER }) })
    expect(result.current.isLoading).toBe(false)
  })
})

describe('useAuth – signUp', () => {
  it('calls register, stores auth, navigates to /app on success', async () => {
    mockRegister.mockResolvedValue({ access_token: 'tok', user: FAKE_USER })
    const { result } = renderHook(() => useAuth())

    const payload = { username: 'alice', email: 'alice@example.com', password: 'Pass1', full_name: 'Alice' }
    await act(() => result.current.signUp(payload))

    expect(mockRegister).toHaveBeenCalledWith(payload)
    expect(mockSetAuth).toHaveBeenCalledWith('tok', FAKE_USER)
    expect(mockNavigate).toHaveBeenCalledWith('/app')
  })

  it('exposes fieldErrors from registration failure', async () => {
    const err = Object.assign(new Error('Bad input'), {
      fields: { username: 'Too short' },
    })
    mockRegister.mockRejectedValue(err)
    const { result } = renderHook(() => useAuth())

    await act(() => result.current.signUp({ username: 'a', email: 'a@b.com', password: 'Pass1', full_name: 'A' }))

    expect(result.current.fieldErrors).toEqual({ username: 'Too short' })
    expect(result.current.error).toBe('Bad input')
  })
})

describe('useAuth – signOut', () => {
  it('clears auth and navigates to /login', async () => {
    mockLogout.mockResolvedValue(undefined)
    const { result } = renderHook(() => useAuth())

    await act(() => result.current.signOut())

    expect(mockClearAuth).toHaveBeenCalled()
    expect(mockNavigate).toHaveBeenCalledWith('/login')
  })

  it('still clears auth even if logout request fails', async () => {
    mockLogout.mockRejectedValue(new Error('network'))
    const { result } = renderHook(() => useAuth())

    await act(() => result.current.signOut())

    expect(mockClearAuth).toHaveBeenCalled()
    expect(mockNavigate).toHaveBeenCalledWith('/login')
  })
})
