const BASE = import.meta.env.VITE_API_URL || ''


export async function createSession() {
  const res = await fetch(`${BASE}/sessions`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to create session')
  return res.json()
}

export async function listSessions() {
  const res = await fetch(`${BASE}/sessions`)
  if (!res.ok) throw new Error('Failed to list sessions')
  return res.json()
}

export async function getSessionDetail(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}`)
  if (!res.ok) throw new Error('Failed to get session')
  return res.json()
}

export async function deleteSession(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error('Failed to delete session')
}


export async function sendMessage(sessionId, content) {
  const res = await fetch(`${BASE}/sessions/${sessionId}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })
  if (!res.ok) throw new Error('Failed to send message')
  return res.json()
}


export async function approveStep(sessionId, approved, feedback = null) {
  const res = await fetch(`${BASE}/sessions/${sessionId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved, feedback }),
  })
  if (!res.ok) throw new Error('Failed to submit approval')
  return res.json()
}

export async function approveGeometry(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}/approve-geometry`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error('Failed to approve geometry')
  return res.json()
}


export function getRenderUrl(sessionId) {
  return `${BASE}/sessions/${sessionId}/render`
}

export function getModelUrl(sessionId) {
  return `${BASE}/sessions/${sessionId}/model`
}

export async function getSessionJobs(sessionId) {
  const res = await fetch(`${BASE}/sessions/${sessionId}/jobs`)
  if (!res.ok) throw new Error('Failed to get jobs')
  return res.json()
}
