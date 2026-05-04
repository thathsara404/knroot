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
}

export interface NewsResponse {
  news: string
}
