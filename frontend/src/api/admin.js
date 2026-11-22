import { request } from './http'

export function login(username, password) {
  return request('/api/admin/login', { method: 'POST', body: { username, password } })
}

export function logout() {
  return request('/api/admin/logout', { method: 'POST', auth: true })
}

export function me() {
  return request('/api/admin/me', { auth: true })
}

export function documents(params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value)
  })
  return request(`/api/admin/documents?${query.toString()}`, { auth: true })
}

export function documentDetail(docUid) {
  return request(`/api/admin/documents/${docUid}`, { auth: true })
}

export function chunks(docUid, limit = 50, offset = 0) {
  return request(`/api/admin/documents/${docUid}/chunks?limit=${limit}&offset=${offset}`, { auth: true })
}

export function upload(files) {
  const form = new FormData()
  Array.from(files).forEach(file => form.append('files', file))
  return request('/api/admin/documents/upload', { method: 'POST', body: form, auth: true })
}

export function reindex(docUid) {
  return request(`/api/admin/documents/${docUid}/reindex`, { method: 'POST', auth: true })
}

export function removeDocument(docUid) {
  return request(`/api/admin/documents/${docUid}`, { method: 'DELETE', auth: true })
}

export function tasks(params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value)
  })
  return request(`/api/admin/tasks?${query.toString()}`, { auth: true })
}

export function rebuild() {
  return request('/api/admin/rebuild', { method: 'POST', body: { scope: 'all' }, auth: true })
}

export function retrievalTest(payload) {
  return request('/api/admin/retrieval-test', { method: 'POST', body: payload, auth: true })
}

export function qaTest(question, debug = false) {
  return request('/api/admin/qa-test', { method: 'POST', body: { question, debug }, auth: true })
}

export function overview(days = 7) {
  return request(`/api/admin/stats/overview?days=${days}`, { auth: true })
}

export function messages(params = {}) {
  const query = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') query.set(key, value)
  })
  return request(`/api/admin/messages?${query.toString()}`, { auth: true })
}

export function messageDetail(id) {
  return request(`/api/admin/messages/${id}`, { auth: true })
}

export function health() {
  return request('/api/admin/health', { auth: true })
}

export function config() {
  return request('/api/admin/config', { auth: true })
}
