import { request } from './client'
import type { UserProfile, AuthResponse, RegisterPayload, LoginPayload } from '../types'

export function login(payload: LoginPayload): Promise<AuthResponse> {
  return request<AuthResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function register(payload: RegisterPayload): Promise<AuthResponse> {
  return request<AuthResponse>('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function refreshToken(): Promise<{ access_token: string }> {
  return request<{ access_token: string }>('/auth/refresh', { method: 'POST' })
}

export function logout(): Promise<void> {
  return request<void>('/auth/logout', { method: 'POST' })
}

export function getMe(): Promise<UserProfile> {
  return request<UserProfile>('/auth/me')
}
