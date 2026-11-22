import { wsUrl } from './base'

export class ChatSocket {
  constructor(sessionId, onEvent, debug = true) {
    this.sessionId = sessionId
    this.onEvent = onEvent
    this.debug = debug
    this.ws = null
    this.pingTimer = null
    this.closedByUser = false
  }

  connect() {
    return new Promise((resolve, reject) => {
      const url = wsUrl(`/api/chat/ws/${this.sessionId}?debug=${this.debug ? 1 : 0}`)
      const ws = new WebSocket(url)
      this.ws = ws
      const timer = setTimeout(() => reject(new Error('连接超时')), 8000)
      ws.onopen = () => {
        clearTimeout(timer)
        this.startPing()
        resolve()
      }
      ws.onmessage = event => {
        try {
          const payload = JSON.parse(event.data)
          this.onEvent(payload)
        } catch {
          // ignore malformed frame
        }
      }
      ws.onerror = () => {
        clearTimeout(timer)
        reject(new Error('WebSocket 连接失败'))
      }
      ws.onclose = () => {
        clearTimeout(timer)
        this.stopPing()
        if (!this.closedByUser) this.onEvent({ type: 'socket_close' })
      }
    })
  }

  startPing() {
    this.stopPing()
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 25000)
  }

  stopPing() {
    if (this.pingTimer) clearInterval(this.pingTimer)
    this.pingTimer = null
  }

  send(content) {
    if (this.ws?.readyState !== WebSocket.OPEN) throw new Error('连接已断开')
    this.ws.send(JSON.stringify({ type: 'chat', content }))
  }

  close() {
    this.closedByUser = true
    this.stopPing()
    this.ws?.close()
    this.ws = null
  }
}
