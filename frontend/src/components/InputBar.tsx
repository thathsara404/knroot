import { useState, useRef, type KeyboardEvent } from 'react'
import { SendHorizonal } from 'lucide-react'

interface Props {
  onSend: (message: string) => void
  disabled: boolean
}

export function InputBar({ onSend, disabled }: Props) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const submit = () => {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  const onInput = () => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  return (
    <div className="px-4 py-3 bg-zinc-950 border-t border-zinc-800">
      <div className="flex items-end gap-2 max-w-4xl mx-auto bg-zinc-900 border border-zinc-700 rounded-2xl px-4 py-2 focus-within:border-violet-500/60 focus-within:ring-1 focus-within:ring-violet-500/20 transition-all">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          onInput={onInput}
          placeholder="Ask about AI research, models, papers…"
          disabled={disabled}
          className="flex-1 resize-none bg-transparent text-sm text-zinc-100 placeholder:text-zinc-600 outline-none py-1.5 min-h-[36px] max-h-40 disabled:opacity-50"
          aria-label="Message input"
        />
        <button
          onClick={submit}
          disabled={disabled || !value.trim()}
          className="mb-1 w-8 h-8 rounded-xl flex items-center justify-center bg-violet-600 hover:bg-violet-500 disabled:bg-zinc-700 disabled:text-zinc-600 text-white transition-colors shrink-0"
          aria-label="Send message"
        >
          <SendHorizonal size={15} />
        </button>
      </div>
      <p className="text-center text-xs text-zinc-700 mt-2">
        Enter to send · Shift+Enter for new line
      </p>
    </div>
  )
}
