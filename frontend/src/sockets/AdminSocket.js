import { wsUrl } from './base'

export class AdminSocket {
  constructor(token, onEvent) {
    this.token = token
    this.onEvent = onEvent
    this.ws = null
    this.pingTimer = null
    this.closedByUser = false
  }

  connect() {
    if (!this.token) return
    const ws = new WebSocket(wsUrl(`/api/admin/ws?token=${encodeURIComponent(this.token)}`))
    this.ws = ws
    ws.onopen = () => this.startPing()
    ws.onmessage = event => {
      try {
        this.onEvent(JSON.parse(event.data))
      } catch {
        // ignore
      }
    }
    ws.onclose = () => {
      this.stopPing()
      if (!this.closedByUser) this.onEvent({ type: 'socket_close' })
    }
  }

  startPing() {
    this.stopPing()
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) this.ws.send('ping')
    }, 25000)
  }

  stopPing() {
    if (this.pingTimer) clearInterval(this.pingTimer)
    this.pingTimer = null
  }

  close() {
    this.closedByUser = true
    this.stopPing()
    this.ws?.close()
    this.ws = null
  }
}
