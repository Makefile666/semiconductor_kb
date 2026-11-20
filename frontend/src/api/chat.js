import { request } from './http'

export function createSession(visitorName = '') {
  return request('/api/chat/sessions', { method: 'POST', body: { visitor_name: visitorName || null } })
}

export function listSessions(limit = 50) {
  return request(`/api/chat/sessions?limit=${limit}`)
}

export function getHistory(sessionId, limit = 30) {
  return request(`/api/chat/sessions/${sessionId}/messages?limit=${limit}`)
}

export function closeSession(sessionId) {
  return request(`/api/chat/sessions/${sessionId}/close`, { method: 'POST' })
}

export function rateMessage(messageId, rating) {
  return request(`/api/chat/messages/${messageId}/rate`, { method: 'POST', body: { rating } })
}

export function meta() {
  return request('/api/meta')
}
