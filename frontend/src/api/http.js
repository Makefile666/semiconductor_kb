const TOKEN_KEY = 'semikb_admin_token'
const API_BASE = import.meta.env.VITE_API_BASE || ''

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export async function request(path, options = {}) {
  const { method = 'GET', body, auth = false, headers = {} } = options
  const finalHeaders = { ...headers }
  if (auth) {
    const token = getToken()
    if (token) finalHeaders['X-Admin-Token'] = token
  }
  let payload = body
  if (body && !(body instanceof FormData)) {
    finalHeaders['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: finalHeaders,
    body: payload,
  })
  let data = null
  try {
    data = await response.json()
  } catch {
    data = { code: response.status, message: '响应不是合法 JSON', data: null }
  }
  if (!response.ok || (data && data.code && data.code >= 400)) {
    const error = new Error(data?.message || `请求失败 ${response.status}`)
    error.status = response.status
    error.code = data?.code
    error.payload = data
    if (response.status === 401) setToken('')
    throw error
  }
  return data?.data ?? data
}
