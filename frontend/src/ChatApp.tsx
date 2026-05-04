import { useState } from 'react'
import { Header } from './components/Header'
import { MessageList } from './components/MessageList'
import { InputBar } from './components/InputBar'
import { NewsPanel } from './components/NewsPanel'
import { useChat } from './hooks/useChat'
import { useNews } from './hooks/useNews'

export default function ChatApp() {
  const [showNews, setShowNews] = useState(true)
  const { messages, isLoading, error, send, newChat, threadId } = useChat()
  const { news, isLoading: newsLoading, error: newsError, refresh } = useNews()

  return (
    <div className="flex flex-col h-screen bg-zinc-950 text-zinc-100 overflow-hidden">
      <Header
        threadId={threadId}
        onNewChat={newChat}
        showNews={showNews}
        onToggleNews={() => setShowNews((v) => !v)}
      />

      <div className="flex flex-1 overflow-hidden">
        <main className="flex flex-col flex-1 overflow-hidden min-w-0">
          <MessageList messages={messages} isLoading={isLoading} />

          {error && (
            <div className="mx-4 mb-2 px-4 py-2.5 bg-red-950/60 border border-red-900 text-red-400 text-xs rounded-xl">
              {error}
            </div>
          )}

          <InputBar onSend={send} disabled={isLoading} />
        </main>

        {showNews && (
          <aside className="hidden lg:flex flex-col w-72 xl:w-80 border-l border-zinc-800 bg-zinc-900/50 overflow-hidden shrink-0">
            <NewsPanel
              news={news}
              isLoading={newsLoading}
              error={newsError}
              onRefresh={refresh}
            />
          </aside>
        )}
      </div>
    </div>
  )
}
