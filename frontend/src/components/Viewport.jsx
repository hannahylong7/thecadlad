import { useState, useEffect } from 'react'
import STLViewer from './STLViewer'
import { approveGeometry, getRenderUrl, getModelUrl } from '../api/client'

export default function Viewport({ sessionId, sessionStatus, onGeometryApproved }) {
  const [approving, setApproving] = useState(false)
  const [frozenModelUrl, setFrozenModelUrl] = useState(null)

  const hasRender = sessionStatus === 'rendered' || sessionStatus === 'approved'
  const hasModel = sessionStatus === 'approved'
  const isExecuting = sessionStatus === 'executing'

  useEffect(() => {
    if (hasModel && sessionId) {
      setFrozenModelUrl(getModelUrl(sessionId) + '?t=' + Date.now())
    } else if (!hasModel) {
      setFrozenModelUrl(null)
    }
  }, [hasModel, sessionId])

  async function handleApproveGeometry() {
    setApproving(true)
    try {
      await approveGeometry(sessionId)
      onGeometryApproved()
    } finally {
      setApproving(false)
    }
  }

  // Empty state
  if (!sessionId || (!hasRender && !isExecuting)) {
    return (
      <div className="h-full eng-grid flex flex-col items-center justify-center text-slate-600">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#1e2d3d" strokeWidth="1" className="mb-5">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>
        <p className="text-xs font-mono uppercase tracking-widest text-slate-700">No model</p>
        <p className="text-xs font-mono text-slate-800 mt-1">Describe a part to begin</p>
      </div>
    )
  }

  // Executing spinner
  if (isExecuting) {
    return (
      <div className="h-full eng-grid flex flex-col items-center justify-center text-slate-400">
        <div className="w-8 h-8 border border-slate-700 border-t-cyan-600 animate-spin mb-4" />
        <p className="text-xs font-mono uppercase tracking-widest text-slate-600">Executing</p>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Viewport header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-800 bg-slate-950">
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono uppercase tracking-widest text-slate-500">
            {hasModel ? 'Viewport · 3D' : 'Viewport · Render'}
          </span>
          {hasModel && (
            <span className="text-xs font-mono text-emerald-500 border border-emerald-800 px-1.5 py-px">
              LIVE
            </span>
          )}
        </div>
        {hasModel && (
          <a
            href={frozenModelUrl || getModelUrl(sessionId)}
            download="model.stl"
            className="text-xs font-mono text-slate-500 hover:text-amber-400 border border-slate-700 hover:border-amber-500/50 px-2.5 py-1 uppercase tracking-wide transition-colors"
          >
            ↓ STL
          </a>
        )}
      </div>

      {/* Render or 3D viewer */}
      <div className="flex-1 relative eng-grid">
        {hasModel ? (
          <STLViewer modelUrl={frozenModelUrl} />
        ) : (
          <div className="h-full flex flex-col">
            <div className="flex-1 flex items-center justify-center p-4">
              <img
                src={`${getRenderUrl(sessionId)}?t=${Date.now()}`}
                alt="CAD render"
                className="max-w-full max-h-full object-contain"
              />
            </div>
            {sessionStatus === 'rendered' && (
              <div className="p-3 border-t border-slate-800 bg-slate-950">
                <p className="text-xs font-mono text-slate-600 uppercase tracking-widest text-center mb-2">
                  Geometry ready — approve to load 3D viewer
                </p>
                <button
                  onClick={handleApproveGeometry}
                  disabled={approving}
                  className="w-full bg-emerald-950 border border-emerald-700 hover:bg-emerald-900 disabled:opacity-40 text-emerald-400 py-2 text-xs font-mono uppercase tracking-widest transition-colors"
                >
                  {approving ? 'Loading…' : '✓ Approve Geometry'}
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {hasModel && (
        <div className="px-4 py-1.5 border-t border-slate-800 bg-slate-950">
          <p className="text-xs font-mono text-slate-700 text-center tracking-wide">DRAG · ROTATE &nbsp;|&nbsp; SCROLL · ZOOM</p>
        </div>
      )}
    </div>
  )
}
