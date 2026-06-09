import { useEffect, useState } from 'react'
import { listSessions, deleteSession } from '../api/client'

const STATUS_COLORS = {
  idle:                   'bg-slate-600',
  planning:               'bg-cyan-500',
  awaiting_plan_approval: 'bg-amber-500',
  coding:                 'bg-cyan-500',
  awaiting_code_approval: 'bg-amber-500',
  executing:              'bg-violet-500',
  rendered:               'bg-emerald-500',
  approved:               'bg-emerald-600',
  error:                  'bg-red-500',
}

const STATUS_SHORT = {
  idle:                   'IDLE',
  planning:               'PLAN',
  awaiting_plan_approval: 'WAIT',
  coding:                 'CODE',
  awaiting_code_approval: 'WAIT',
  executing:              'EXEC',
  rendered:               'REND',
  approved:               'APPR',
  error:                  'ERR',
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m`
  if (hours < 24) return `${hours}h`
  return `${days}d`
}

export default function SessionSidebar({ activeSessionId, onSelect, onNewSession }) {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    load()
  }, [activeSessionId])

  async function load() {
    try {
      const data = await listSessions()
      setSessions(data)
    } catch (err) {
      console.error('Failed to load sessions:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(e, sessionId) {
    e.stopPropagation()
    try {
      await deleteSession(sessionId)
      setSessions(prev => prev.filter(s => s.id !== sessionId))
      if (sessionId === activeSessionId) onSelect(null)
    } catch (err) {
      console.error('Failed to delete session:', err)
    }
  }

  return (
    <div className="w-56 shrink-0 flex flex-col bg-slate-950 border-r border-slate-800 h-full">
      {/* Header */}
      <div className="px-3 pt-3 pb-2.5 border-b border-slate-800/60">
        <button
          onClick={onNewSession}
          className="w-full border border-slate-800 hover:border-amber-500/30 bg-transparent hover:bg-slate-900/50 text-slate-600 hover:text-amber-400/80 text-xs font-mono py-1.5 uppercase tracking-widest transition-colors flex items-center justify-center gap-2"
        >
          + New Session
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto">
        {loading && (
          <p className="text-xs font-mono text-slate-700 px-3 py-3 uppercase tracking-widest">Loading…</p>
        )}

        {!loading && sessions.length === 0 && (
          <p className="text-xs font-mono text-slate-700 px-3 py-3">
            No sessions yet.
          </p>
        )}

        {sessions.map(session => {
          const isActive = session.id === activeSessionId
          return (
            <div
              key={session.id}
              onClick={() => onSelect(session.id)}
              className={`
                group flex items-start gap-2 px-3 py-2 cursor-pointer transition-colors border-l-2
                ${isActive
                  ? 'border-l-amber-500 bg-slate-900'
                  : 'border-l-transparent hover:bg-slate-900/60 hover:border-l-slate-700'
                }
              `}
            >
              {/* Status indicator */}
              <div className={`w-1.5 h-1.5 mt-1.5 shrink-0 ${STATUS_COLORS[session.status] || 'bg-slate-600'}`} />

              {/* Session info */}
              <div className="flex-1 min-w-0">
                <p className={`text-xs truncate leading-snug font-mono ${isActive ? 'text-slate-200' : 'text-slate-400'}`}>
                  {session.title}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-xs font-mono text-slate-700">{timeAgo(session.created_at)}</span>
                  <span className="text-xs font-mono text-slate-800">{STATUS_SHORT[session.status] || '?'}</span>
                  {session.has_model && (
                    <span className="text-xs font-mono text-emerald-900">stl</span>
                  )}
                </div>
              </div>

              {/* Delete */}
              <button
                onClick={e => handleDelete(e, session.id)}
                className="opacity-0 group-hover:opacity-100 text-slate-700 hover:text-red-500 transition-all text-base leading-none shrink-0 mt-0.5 font-mono"
                title="Delete session"
              >
                ×
              </button>
            </div>
          )
        })}
      </div>

      {/* Footer */}
      {sessions.length > 0 && (
        <div className="px-3 py-2 border-t border-slate-800/60">
          <p className="text-xs font-mono text-slate-800">
            {sessions.length} session{sessions.length !== 1 ? 's' : ''}
          </p>
        </div>
      )}
    </div>
  )
}
