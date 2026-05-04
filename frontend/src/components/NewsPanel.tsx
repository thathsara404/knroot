import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { RefreshCw, Newspaper } from 'lucide-react'

interface Props {
  news: string | null
  isLoading: boolean
  error: boolean
  onRefresh: () => void
}

function Skeleton() {
  return (
    <div className="p-4 space-y-4 animate-pulse">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="space-y-2">
          <div className="h-2.5 bg-zinc-800 rounded w-20" />
          <div className="h-3.5 bg-zinc-800 rounded w-full" />
          <div className="h-3 bg-zinc-800 rounded w-4/5" />
        </div>
      ))}
    </div>
  )
}

export function NewsPanel({ news, isLoading, error, onRefresh }: Props) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800 shrink-0">
        <div className="flex items-center gap-2">
          <Newspaper size={15} className="text-violet-400" />
          <span className="text-xs font-semibold text-zinc-300 uppercase tracking-wider">
            Today's AI News
          </span>
        </div>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="text-zinc-500 hover:text-zinc-300 disabled:opacity-40 transition-colors"
          aria-label="Refresh news"
        >
          <RefreshCw size={13} className={isLoading ? 'animate-spin' : ''} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {isLoading && <Skeleton />}

        {error && !isLoading && (
          <div className="p-4 text-center text-xs text-zinc-500">
            Failed to load news.{' '}
            <button onClick={onRefresh} className="text-violet-400 hover:underline">
              Retry
            </button>
          </div>
        )}

        {news && !isLoading && (
          <div className="p-4 prose prose-invert prose-xs max-w-none prose-headings:text-zinc-200 prose-headings:text-xs prose-headings:font-semibold prose-headings:mt-4 prose-headings:mb-1 prose-p:text-zinc-400 prose-p:text-xs prose-p:leading-relaxed prose-p:my-0.5 prose-a:text-violet-400 prose-a:text-xs prose-a:no-underline hover:prose-a:underline prose-strong:text-zinc-300 prose-li:text-zinc-400 prose-li:text-xs prose-ul:my-1 prose-hr:border-zinc-800">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{news}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}
