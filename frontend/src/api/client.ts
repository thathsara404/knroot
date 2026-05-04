import type { ChatResponse, NewsResponse } from '../types'

const BASE = import.meta.env.VITE_API_URL ?? '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) {
    const text = await res.text().catch(() => `HTTP ${res.status}`)
    throw new Error(text)
  }
  return res.json() as Promise<T>
}

export function sendMessage(message: string, threadId?: string): Promise<ChatResponse> {
  return request<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, thread_id: threadId }),
    signal: AbortSignal.timeout(90_000),
  })
}

export async function fetchNews(): Promise<string> {
  const data = await request<NewsResponse>('/news', {
    signal: AbortSignal.timeout(15_000),
  })
  return data.news
}
