import { useState, useCallback } from 'react'
import type { Message } from '../types'
import { sendMessage } from '../api/client'

const STORAGE_KEY = 'ai_agent_chat'

interface StoredChat {
  threadId: string
  messages: Array<Omit<Message, 'timestamp'> & { timestamp: string }>
}

function load(): { threadId?: string; messages: Message[] } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { messages: [] }
    const data: StoredChat = JSON.parse(raw)
    return {
      threadId: data.threadId,
      messages: data.messages.map((m) => ({ ...m, timestamp: new Date(m.timestamp) })),
    }
  } catch {
    return { messages: [] }
  }
}

function save(threadId: string, messages: Message[]) {
  const data: StoredChat = {
    threadId,
    messages: messages.map((m) => ({ ...m, timestamp: m.timestamp.toISOString() })),
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
}

export function useChat() {
  const [{ threadId, messages }, setChat] = useState(load)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const send = useCallback(
    async (content: string) => {
      const userMsg: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content,
        timestamp: new Date(),
      }

      setChat((prev) => ({ ...prev, messages: [...prev.messages, userMsg] }))
      setIsLoading(true)
      setError(null)

      try {
        const data = await sendMessage(content, threadId)
        const assistantMsg: Message = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: data.response,
          timestamp: new Date(),
        }
        setChat((prev) => {
          const next = { threadId: data.thread_id, messages: [...prev.messages, assistantMsg] }
          save(data.thread_id, next.messages)
          return next
        })
      } catch (err) {
        // Roll back optimistic user message on failure
        setChat((prev) => ({ ...prev, messages: prev.messages.slice(0, -1) }))
        setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
      } finally {
        setIsLoading(false)
      }
    },
    [threadId],
  )

  const newChat = useCallback(() => {
    setChat({ threadId: undefined, messages: [] })
    setError(null)
    localStorage.removeItem(STORAGE_KEY)
  }, [])

  return { messages, isLoading, error, send, newChat, threadId }
}
