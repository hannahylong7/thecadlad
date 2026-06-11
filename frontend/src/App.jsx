import { useState, useRef, useEffect } from 'react'
import {
  UserMessage, AssistantMessage, PlanProposal,
  CodeProposal, ThinkingIndicator, StatusBadge
} from './components/ChatMessages'
import Viewport from './components/Viewport'
import SessionSidebar from './components/SessionSidebar'
import {
  createSession,
  sendMessage,
  approveStep,
  getSessionDetail,
} from './api/client'

const CODE_REJECTED_PREFIX = 'Code rejected. Feedback: '
const PLAN_REJECTED_PREFIX = 'Plan rejected. Feedback: '

function replayMessages(messages) {
  return messages
    .map(m => {
      if (m.role === 'user' && m.content === 'Plan approved. Please write the CadQuery code.') return null
      if (m.role === 'user' && m.content.startsWith('Execution failed:')) return null

      if (m.role === 'user' && m.content.startsWith(CODE_REJECTED_PREFIX)) {
        return { type: 'user', content: `Revise: ${m.content.slice(CODE_REJECTED_PREFIX.length)}`, id: m.timestamp }
      }
      if (m.role === 'user' && m.content.startsWith(PLAN_REJECTED_PREFIX)) {
        return { type: 'user', content: `Revise: ${m.content.slice(PLAN_REJECTED_PREFIX.length)}`, id: m.timestamp }
      }

      if (m.role === 'user') return { type: 'user', content: m.content, id: m.timestamp }

      if (m.content.startsWith('[tool_call:')) {
        if (m.plan) return { type: 'plan', plan: m.plan, assumptions: [], id: m.timestamp }
        if (m.code && m.content.includes('self_correct')) return { type: 'correction', code: m.code, id: m.timestamp }
        if (m.code) return { type: 'code', code: m.code, description: '', id: m.timestamp }
        return null
      }

      return { type: 'assistant', content: m.content, id: m.timestamp }
    })
    .filter(Boolean)
}

export default function App() {
  const [sessionId, setSessionId] = useState(null)
  const [sessionStatus, setSessionStatus] = useState('idle')
  const [sessionTitle, setSessionTitle] = useState('')
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [thinking, setThinking] = useState(false)
  const [pendingType, setPendingType] = useState(null)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking])

  // Session management

  async function handleNewSession() {
    // Reset all state to a clean slate
    setSessionId(null)
    setSessionStatus('idle')
    setSessionTitle('')
    setMessages([])
    setInput('')
    setPendingType(null)
  }

  async function handleSelectSession(id) {
    if (!id) {
      handleNewSession()
      return
    }

    try {
      const session = await getSessionDetail(id)
      setSessionId(id)
      setSessionStatus(session.status)
      setSessionTitle(session.title)
      setPendingType(null)

      setMessages(replayMessages(session.messages))

      if (session.status === 'awaiting_plan_approval') setPendingType('plan')
      else if (session.status === 'awaiting_code_approval') setPendingType('code')

    } catch (err) {
      console.error('Failed to load session:', err)
    }
  }

  async function ensureSession() {
    if (sessionId) return sessionId
    const session = await createSession()
    setSessionId(session.id)
    return session.id
  }

  // Messaging

  function addMessage(msg) {
    setMessages(prev => [...prev, { ...msg, id: Date.now() + Math.random() }])
  }

  async function handleSend() {
    if (!input.trim() || thinking) return
    const text = input.trim()
    setInput('')
    addMessage({ type: 'user', content: text })
    setThinking(true)

    try {
      const sid = await ensureSession()
      const result = await sendMessage(sid, text)
      setSessionStatus(result.session_status)
      handleAgentResult(result)
    } catch (err) {
      addMessage({ type: 'assistant', content: `Error: ${err.message}` })
    } finally {
      setThinking(false)
    }
  }

  function handleAgentResult(result) {
    if (result.type === 'plan_proposal') {
      addMessage({ type: 'plan', plan: result.plan, assumptions: result.assumptions })
      setPendingType('plan')
    } else if (result.type === 'code_proposal') {
      addMessage({ type: 'code', code: result.code, description: result.description })
      setPendingType('code')
    } else if (result.type === 'self_correction') {
      addMessage({ type: 'correction', code: result.code, errorAnalysis: result.error_analysis })
      setPendingType('correction')
    } else if (result.type === 'render_complete') {
      setSessionStatus('rendered')
      addMessage({ type: 'assistant', content: '✓ Model rendered. Approve the geometry above to load the 3D viewer, or describe changes.' })
      setPendingType(null)
    } else if (result.type === 'message') {
      if (!result.content.startsWith('[tool_call:')) {
        addMessage({ type: 'assistant', content: result.content })
      }
      setPendingType(null)
    } else if (result.type === 'error') {
      addMessage({ type: 'assistant', content: `⚠ ${result.content}` })
      setPendingType(null)
    }
  }

  async function handleApprove(feedback = null) {
    setThinking(true)
    setPendingType(null)
    try {
      const result = await approveStep(sessionId, true, feedback)
      setSessionStatus(result.session_status)
      if (result.session_status === 'executing') {
        const poll = setInterval(async () => {
          try {
            const session = await getSessionDetail(sessionId)
            setSessionStatus(session.status)
            if (session.status !== 'executing') {
              clearInterval(poll)
              if (session.status === 'rendered') {
                handleAgentResult({ type: 'render_complete', session_status: session.status })
              } else {
                const updated = await getSessionDetail(sessionId)
                setMessages(replayMessages(updated.messages))
                setPendingType(session.status === 'awaiting_code_approval' ? 'correction' : null)
              }
              setThinking(false)
            }
          } catch (pollErr) {
            clearInterval(poll)
            setThinking(false)
          }
        }, 2000)
      } else {
        handleAgentResult(result)
        setThinking(false)
      }
    } catch (err) {
      addMessage({ type: 'assistant', content: `Error: ${err.message}` })
      setThinking(false)
    }
  }

  async function handleReject(feedback) {
    setThinking(true)
    setPendingType(null)
    addMessage({ type: 'user', content: `Revise: ${feedback}` })
    try {
      const result = await approveStep(sessionId, false, feedback)
      setSessionStatus(result.session_status)
      handleAgentResult(result)
    } catch (err) {
      addMessage({ type: 'assistant', content: `Error: ${err.message}` })
    } finally {
      setThinking(false)
    }
  }

  function handleGeometryApproved() {
    setSessionStatus('approved')
    addMessage({ type: 'assistant', content: '✓ 3D viewer loaded. Rotate and zoom the model, download the STL, or describe further changes.' })
  }

  const canType = !thinking && pendingType === null

  return (
    <div className="h-screen flex flex-col bg-slate-950">
      {/* Header */}
      <header className="flex items-center justify-between px-6 py-2.5 border-b border-slate-800 bg-slate-950 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 border border-amber-500/50 flex items-center justify-center shrink-0">
            <span className="text-amber-400 text-xs font-mono font-bold">*</span>
          </div>
          <div>
            <h1 className="text-xs font-mono font-semibold text-slate-200 tracking-widest uppercase">The CAD Lad</h1>
            {sessionTitle && (
              <p className="text-xs font-mono text-slate-600 truncate max-w-64">{sessionTitle}</p>
            )}
          </div>
        </div>
        <StatusBadge status={sessionStatus} />
      </header>

      {/* Main layout */}
      <div className="flex-1 flex overflow-hidden">

        {/* Sidebar */}
        <SessionSidebar
          activeSessionId={sessionId}
          onSelect={handleSelectSession}
          onNewSession={handleNewSession}
        />

        {/* Chat panel */}
        <div className="w-[420px] shrink-0 flex flex-col border-r border-slate-800 bg-slate-950">
          <div className="flex-1 overflow-y-auto p-4 chat-scroll eng-lines">
            {messages.length === 0 && (
              <div className="h-full flex flex-col items-center justify-center text-center px-8">
                <p className="text-xs font-mono text-slate-500 uppercase tracking-widest mb-2">Awaiting input</p>
                <p className="text-xs font-mono text-slate-700">
                  e.g. "50×30×10mm mounting bracket with four M3 holes"
                </p>
              </div>
            )}

            {messages.map((msg) => {
              const isLatestPending = msg.id === messages[messages.length - 1]?.id && pendingType !== null

              if (msg.type === 'user') return <UserMessage key={msg.id} content={msg.content} />
              if (msg.type === 'assistant') return <AssistantMessage key={msg.id} content={msg.content} />
              if (msg.type === 'plan') return (
                <PlanProposal key={msg.id}
                  plan={msg.plan}
                  assumptions={msg.assumptions}
                  onApprove={() => handleApprove()}
                  onReject={handleReject}
                  disabled={!isLatestPending || thinking}
                />
              )
              if (msg.type === 'code' || msg.type === 'correction') return (
                <CodeProposal key={msg.id}
                  code={msg.code}
                  description={msg.description}
                  isSelfCorrection={msg.type === 'correction'}
                  errorAnalysis={msg.errorAnalysis}
                  onApprove={() => handleApprove()}
                  onReject={handleReject}
                  disabled={!isLatestPending || thinking}
                />
              )
              return null
            })}

            {thinking && <ThinkingIndicator />}
            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t border-slate-800 bg-slate-950">
            <div className="flex gap-2">
              <input
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && !e.shiftKey && handleSend()}
                placeholder={canType ? "Describe a part or request changes…" : "Awaiting approval…"}
                disabled={!canType}
                className="flex-1 bg-slate-900 border border-slate-700 px-3 py-2 text-sm font-mono text-slate-200 placeholder-slate-600 focus:outline-none focus:border-amber-500/50 disabled:opacity-30"
              />
              <button
                onClick={handleSend}
                disabled={!canType || !input.trim()}
                className="bg-amber-500 hover:bg-amber-400 disabled:bg-slate-800 disabled:text-slate-600 text-slate-950 px-4 py-2 text-xs font-mono font-bold uppercase tracking-widest transition-colors"
              >
                Send
              </button>
            </div>
          </div>
        </div>

        {/* Viewport */}
        <div className="flex-1 bg-slate-950">
          <Viewport
            sessionId={sessionId}
            sessionStatus={sessionStatus}
            onGeometryApproved={handleGeometryApproved}
          />
        </div>

      </div>
    </div>
  )
}
