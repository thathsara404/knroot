import { BrainCircuit, Plus, PanelRight } from 'lucide-react'

interface Props {
  threadId?: string
  onNewChat: () => void
  showNews: boolean
  onToggleNews: () => void
}

export function Header({ threadId, onNewChat, showNews, onToggleNews }: Props) {
  return (
    <header className="flex items-center justify-between px-4 py-3 bg-zinc-900 border-b border-zinc-800 shrink-0">
      <div className="flex items-center gap-2.5">
        <div className="w-8 h-8 rounded-xl bg-violet-600 flex items-center justify-center">
          <BrainCircuit size={18} className="text-white" />
        </div>
        <div>
          <h1 className="text-sm font-semibold text-zinc-100 leading-tight">AI Technical Agent</h1>
          {threadId ? (
            <p className="text-xs text-zinc-600 leading-tight font-mono">
              {threadId.slice(0, 8)}…
            </p>
          ) : (
            <p className="text-xs text-zinc-600 leading-tight">New conversation</p>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <button
          onClick={onToggleNews}
          title={showNews ? 'Hide news panel' : 'Show news panel'}
          className={`hidden lg:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs transition-colors ${
            showNews
              ? 'bg-zinc-800 text-zinc-300 hover:bg-zinc-700'
              : 'bg-zinc-800/50 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300'
          }`}
        >
          <PanelRight size={14} />
          News
        </button>

        <button
          onClick={onNewChat}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs bg-violet-600 hover:bg-violet-500 text-white transition-colors font-medium"
        >
          <Plus size={14} />
          New Chat
        </button>
      </div>
    </header>
  )
}
