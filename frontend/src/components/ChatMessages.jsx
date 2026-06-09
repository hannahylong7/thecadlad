import { useState } from 'react'

const STATUS_COLORS = {
  idle:                   'bg-slate-900 text-slate-500 border-slate-700',
  planning:               'bg-cyan-950 text-cyan-400 border-cyan-700',
  awaiting_plan_approval: 'bg-amber-950 text-amber-400 border-amber-700',
  coding:                 'bg-cyan-950 text-cyan-400 border-cyan-700',
  awaiting_code_approval: 'bg-amber-950 text-amber-400 border-amber-700',
  executing:              'bg-violet-950 text-violet-400 border-violet-700',
  rendered:               'bg-emerald-950 text-emerald-400 border-emerald-700',
  approved:               'bg-emerald-950 text-emerald-400 border-emerald-700',
  error:                  'bg-red-950 text-red-400 border-red-700',
}

const STATUS_LABELS = {
  idle:                   'READY',
  planning:               'PLANNING',
  awaiting_plan_approval: 'AWAITING APPROVAL',
  coding:                 'CODING',
  awaiting_code_approval: 'AWAITING APPROVAL',
  executing:              'EXECUTING',
  rendered:               'RENDERED',
  approved:               'APPROVED',
  error:                  'ERROR',
}

const PULSE_STATUSES = new Set(['planning', 'coding', 'executing'])

export function StatusBadge({ status }) {
  const colors = STATUS_COLORS[status] || 'bg-slate-900 text-slate-500 border-slate-700'
  const pulse = PULSE_STATUSES.has(status)
  return (
    <span className={`inline-flex items-center gap-2 text-xs font-mono tracking-widest px-2 py-0.5 border ${colors}`}>
      <span className={`w-1 h-1 bg-current shrink-0 ${pulse ? 'animate-pulse' : ''}`} />
      {STATUS_LABELS[status] || status.toUpperCase()}
    </span>
  )
}

export function UserMessage({ content }) {
  return (
    <div className="flex justify-end mb-3">
      <div className="bg-slate-900 border border-slate-700 border-r-2 border-r-amber-500 px-3 py-2 max-w-sm text-sm text-slate-200">
        {content}
      </div>
    </div>
  )
}

export function AssistantMessage({ content }) {
  return (
    <div className="flex gap-3 mb-3 max-w-lg">
      <span className="text-xs font-mono text-cyan-500 shrink-0 pt-0.5 select-none">[AI]</span>
      <div className="border-l border-slate-700 pl-3 text-sm text-slate-300 leading-relaxed">
        {content}
      </div>
    </div>
  )
}

export function PlanProposal({ plan, assumptions, onApprove, onReject, disabled }) {
  const [feedback, setFeedback] = useState('')
  const [rejecting, setRejecting] = useState(false)

  return (
    <div className="flex gap-3 mb-4 max-w-lg w-full">
      <span className="text-xs font-mono text-cyan-500 shrink-0 pt-0.5 select-none">[AI]</span>
      <div className="flex-1 border border-amber-500/40 border-l-2 border-l-amber-500 bg-slate-900/60 overflow-hidden">
        <div className="px-3 py-1.5 border-b border-amber-500/20">
          <span className="text-amber-400/80 text-xs font-mono tracking-widest uppercase">Plan</span>
        </div>
        <div className="px-3 py-3">
          <p className="text-sm text-slate-200 whitespace-pre-line leading-relaxed font-mono text-xs">{plan}</p>
          {assumptions?.length > 0 && (
            <div className="mt-3 pt-3 border-t border-slate-800">
              <p className="text-xs font-mono text-slate-500 uppercase tracking-widest mb-2">Assumptions</p>
              <ul className="space-y-1">
                {assumptions.map((a, i) => (
                  <li key={i} className="text-xs text-slate-400 font-mono flex gap-2">
                    <span className="text-amber-500/60">›</span>{a}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        {!disabled && (
          <div className="px-3 pb-3">
            {rejecting ? (
              <div className="space-y-2">
                <textarea
                  value={feedback}
                  onChange={e => setFeedback(e.target.value)}
                  placeholder="Describe required changes..."
                  rows={2}
                  className="w-full bg-slate-950 border border-slate-700 px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-amber-500/50 resize-none"
                />
                <div className="flex gap-2">
                  <button onClick={() => onReject(feedback)} className="flex-1 bg-red-950 border border-red-700 hover:bg-red-900 text-red-400 text-xs font-mono py-1.5 uppercase tracking-wide transition-colors">Reject</button>
                  <button onClick={() => setRejecting(false)} className="px-4 border border-slate-700 hover:border-slate-500 text-slate-400 text-xs font-mono py-1.5 uppercase tracking-wide transition-colors">Cancel</button>
                </div>
              </div>
            ) : (
              <div className="flex gap-2">
                <button onClick={onApprove} className="flex-1 bg-emerald-950 border border-emerald-700 hover:bg-emerald-900 text-emerald-400 text-xs font-mono py-1.5 uppercase tracking-wide transition-colors">
                  ✓ Approve Plan
                </button>
                <button onClick={() => setRejecting(true)} className="px-4 border border-slate-700 hover:border-slate-500 text-slate-400 text-xs font-mono py-1.5 uppercase tracking-wide transition-colors">
                  Revise
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export function CodeProposal({ code, description, isSelfCorrection, errorAnalysis, onApprove, onReject, disabled }) {
  const [feedback, setFeedback] = useState('')
  const [rejecting, setRejecting] = useState(false)
  const [expanded, setExpanded] = useState(true)

  const accentColor = isSelfCorrection ? 'border-l-orange-500 border-orange-500/30' : 'border-l-cyan-500 border-cyan-500/20'
  const headerColor = isSelfCorrection ? 'text-orange-400/80 border-orange-500/20' : 'text-cyan-400/80 border-cyan-500/20'
  const label = isSelfCorrection ? 'Correction' : 'Code'

  return (
    <div className="flex gap-3 mb-4 max-w-lg w-full">
      <span className="text-xs font-mono text-cyan-500 shrink-0 pt-0.5 select-none">[AI]</span>
      <div className={`flex-1 border border-l-2 ${accentColor} bg-slate-900/60 overflow-hidden`}>
        <div className={`px-3 py-1.5 border-b flex items-center justify-between ${headerColor}`}>
          <span className="text-xs font-mono tracking-widest uppercase">{label}</span>
          <button onClick={() => setExpanded(e => !e)} className="text-xs font-mono text-slate-600 hover:text-slate-400 uppercase tracking-wide transition-colors">
            {expanded ? '[−]' : '[+]'}
          </button>
        </div>
        {isSelfCorrection && errorAnalysis && (
          <div className="px-3 py-2 border-b border-red-900/50 bg-red-950/30">
            <p className="text-xs font-mono text-red-400">{errorAnalysis}</p>
          </div>
        )}
        {description && (
          <div className="px-3 py-1.5 border-b border-slate-800">
            <p className="text-xs font-mono text-slate-500">{description}</p>
          </div>
        )}
        {expanded && (
          <div className="px-3 py-3 overflow-x-auto">
            <pre className="!p-0 !border-0 !bg-transparent !border-l-0"><code className="text-green-400 text-xs font-mono">{code}</code></pre>
          </div>
        )}
        {!disabled && (
          <div className="px-3 pb-3">
            {rejecting ? (
              <div className="space-y-2">
                <textarea
                  value={feedback}
                  onChange={e => setFeedback(e.target.value)}
                  placeholder="Describe required changes..."
                  rows={2}
                  className="w-full bg-slate-950 border border-slate-700 px-3 py-2 text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500/50 resize-none"
                />
                <div className="flex gap-2">
                  <button onClick={() => onReject(feedback)} className="flex-1 bg-red-950 border border-red-700 hover:bg-red-900 text-red-400 text-xs font-mono py-1.5 uppercase tracking-wide transition-colors">Reject</button>
                  <button onClick={() => setRejecting(false)} className="px-4 border border-slate-700 hover:border-slate-500 text-slate-400 text-xs font-mono py-1.5 uppercase tracking-wide transition-colors">Cancel</button>
                </div>
              </div>
            ) : (
              <div className="flex gap-2">
                <button onClick={onApprove} className="flex-1 bg-emerald-950 border border-emerald-700 hover:bg-emerald-900 text-emerald-400 text-xs font-mono py-1.5 uppercase tracking-wide transition-colors">
                  ✓ Execute
                </button>
                <button onClick={() => setRejecting(true)} className="px-4 border border-slate-700 hover:border-slate-500 text-slate-400 text-xs font-mono py-1.5 uppercase tracking-wide transition-colors">
                  Revise
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export function ThinkingIndicator() {
  return (
    <div className="flex gap-3 mb-3">
      <span className="text-xs font-mono text-cyan-500 shrink-0 pt-0.5 select-none">[AI]</span>
      <div className="border-l border-slate-700 pl-3 flex items-center gap-1 py-1">
        <span className="w-1 h-3 bg-cyan-500/70 animate-pulse" style={{animationDelay:'0ms'}} />
        <span className="w-1 h-3 bg-cyan-500/70 animate-pulse" style={{animationDelay:'200ms'}} />
        <span className="w-1 h-3 bg-cyan-500/70 animate-pulse" style={{animationDelay:'400ms'}} />
      </div>
    </div>
  )
}
