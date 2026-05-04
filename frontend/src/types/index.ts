export interface UserProfile {
  id: string
  username: string
  email: string
  phone: string | null
  full_name: string
  created_at: string
}

export interface AuthResponse {
  access_token: string
  user: UserProfile
}

export interface LoginPayload {
  identifier: string
  password: string
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
  full_name: string
  phone?: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
}

export interface ChatResponse {
  response: string
  thread_id: string
  is_new_conversation: boolean
  suggested_topics: string[]
}

export interface NewsArticle {
  source: string
  title: string
  link: string
  summary: string
}

export interface NewsResponse {
  news: string
}

export interface ApiError {
  error: string
  fields?: Record<string, string | null>
}
