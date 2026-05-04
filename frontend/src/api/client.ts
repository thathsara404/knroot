import { useAuthStore } from '../store/authStore'

export const BASE = import.meta.env.VITE_API_URL ?? '/api'

let _refreshing: Promise<string | null> | null = null

async function doRefresh(): Promise<string | null> {
  if (_refreshing) return _refreshing
  _refreshing = fetch(`${BASE}/auth/refresh`, { method: 'POST', credentials: 'include' })
    .then(async (res) => {
      if (!res.ok) return null
      const data: { access_token: string } = await res.json()
      useAuthStore.getState().setToken(data.access_token)
      return data.access_token
    })
    .catch(() => null)
    .finally(() => { _refreshing = null })
  return _refreshing
}

function buildHeaders(token: string | null, extra?: HeadersInit): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(extra as Record<string, string>),
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = useAuthStore.getState().accessToken

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: 'include',
    headers: buildHeaders(token, init.headers),
  })

  if (res.status !== 401) {
    if (!res.ok) {
      const body = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
      const err = new Error(body.error ?? `HTTP ${res.status}`) as Error & { fields?: unknown }
      err.fields = body.fields
      throw err
    }
    return res.json() as Promise<T>
  }

  const newToken = await doRefresh()
  if (!newToken) {
    useAuthStore.getState().clearAuth()
    window.location.href = '/login'
    throw new Error('Session expired')
  }

  const retry = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: 'include',
    headers: buildHeaders(newToken, init.headers),
  })
  if (!retry.ok) {
    const body = await retry.json().catch(() => ({ error: `HTTP ${retry.status}` }))
    throw new Error(body.error ?? `HTTP ${retry.status}`)
  }
  return retry.json() as Promise<T>
}

export function sendMessage(message: string, threadId?: string) {
  return request<import('../types').ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, thread_id: threadId }),
    signal: AbortSignal.timeout(90_000),
  })
}

export async function fetchNews(): Promise<string> {
  const data = await request<import('../types').NewsResponse>('/news', {
    signal: AbortSignal.timeout(15_000),
  })
  return data.news
}
