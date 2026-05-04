import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message as MessageType } from '../types'
import { CodeBlock } from './CodeBlock'

interface Props {
  message: MessageType
}

function formatTime(date: Date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

function AssistantContent({ content }: { content: string }) {
  return (
    <div className="prose prose-invert prose-sm max-w-none prose-p:leading-relaxed prose-p:my-1.5 prose-headings:text-zinc-100 prose-a:text-violet-400 prose-a:no-underline hover:prose-a:underline prose-strong:text-zinc-100 prose-code:text-violet-300 prose-code:bg-zinc-700/50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-xs prose-pre:p-0 prose-pre:bg-transparent prose-li:my-0.5 prose-ul:my-1.5 prose-ol:my-1.5">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          pre({ children }) {
            return <>{children}</>
          },
          code({ children, className }) {
            const lang = /language-(\w+)/.exec(className ?? '')?.[1]
            if (!lang) {
              return (
                <code className="bg-zinc-700/50 text-violet-300 px-1.5 py-0.5 rounded text-xs font-mono">
                  {children}
                </code>
              )
            }
            return (
              <CodeBlock language={lang}>{String(children).replace(/\n$/, '')}</CodeBlock>
            )
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

export function Message({ message }: Props) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end items-end gap-2 px-4 py-1.5 group">
        <div className="flex flex-col items-end gap-1 max-w-[75%]">
          <div className="bg-violet-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words">
            {message.content}
          </div>
          <span className="text-xs text-zinc-600 group-hover:text-zinc-500 transition-colors px-1">
            {formatTime(message.timestamp)}
          </span>
        </div>
        <div className="w-7 h-7 rounded-full bg-zinc-700 flex items-center justify-center text-zinc-300 text-xs font-bold shrink-0 mb-5">
          You
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-end gap-3 px-4 py-1.5 group">
      <div className="w-7 h-7 rounded-full bg-violet-600 flex items-center justify-center text-white text-xs font-bold shrink-0 mb-5">
        AI
      </div>
      <div className="flex flex-col gap-1 max-w-[85%]">
        <div className="bg-zinc-800 text-zinc-100 rounded-2xl rounded-bl-sm px-4 py-3 text-sm">
          <AssistantContent content={message.content} />
        </div>
        <span className="text-xs text-zinc-600 group-hover:text-zinc-500 transition-colors px-1">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </div>
  )
}
