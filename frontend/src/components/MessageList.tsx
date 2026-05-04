import { useEffect, useRef } from 'react'
import { BrainCircuit } from 'lucide-react'
import type { Message as MessageType } from '../types'
import { Message } from './Message'
import { TypingIndicator } from './TypingIndicator'

interface Props {
  messages: MessageType[]
  isLoading: boolean
}

const SUGGESTIONS = [
  'Explain the transformer attention mechanism',
  'What is RAG and how does it work?',
  'Compare LoRA vs full fine-tuning',
  'Latest breakthroughs in multimodal AI',
]

function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 px-8 text-center">
      <div className="w-16 h-16 rounded-2xl bg-violet-600/20 border border-violet-500/30 flex items-center justify-center">
        <BrainCircuit size={32} className="text-violet-400" />
      </div>
      <div>
        <h2 className="text-lg font-semibold text-zinc-200 mb-1">AI Technical Agent</h2>
        <p className="text-sm text-zinc-500 max-w-xs">
          Ask me anything about AI research, ML frameworks, deployment, or today's news.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-md">
        {SUGGESTIONS.map((s) => (
          <div
            key={s}
            className="px-3 py-2.5 text-xs text-zinc-400 bg-zinc-900 border border-zinc-800 rounded-xl text-left leading-snug"
          >
            {s}
          </div>
        ))}
      </div>
    </div>
  )
}

export function MessageList({ messages, isLoading }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  return (
    <div className="flex-1 overflow-y-auto scroll-smooth">
      {messages.length === 0 && !isLoading ? (
        <EmptyState />
      ) : (
        <div className="py-4">
          {messages.map((msg) => (
            <Message key={msg.id} message={msg} />
          ))}
          {isLoading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}
