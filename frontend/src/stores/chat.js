import { defineStore } from 'pinia'
import { createSession, getHistory, closeSession, rateMessage, meta, listSessions } from '../api/chat'
import { ChatSocket } from '../sockets/ChatSocket'

const SESSION_KEY = 'semikb_chat_session'

export const useChatStore = defineStore('chat', {
  state: () => ({
    session: null,
    sessions: [],
    sessionsTotal: 0,
    sessionsLoading: false,
    messages: [],
    suggestions: [],
    brand: { name: '芯知 SemiKB', slogan: '让每一份工艺文档都能被问出来' },
    status: 'idle',
    streamingText: '',
    liveNodes: [],
    activeNode: '',
    error: '',
    busy: false,
    socket: null,
    maxQuestionChars: 2000,
  }),
  actions: {
    async init() {
      try {
        const data = await meta()
        this.brand = data.brand || this.brand
        this.suggestions = data.suggestions || []
        this.maxQuestionChars = data.max_question_chars || 2000
      } catch {
        // keep defaults
      }
      await this.loadSessions()
      const saved = Number(localStorage.getItem(SESSION_KEY) || 0)
      if (saved) {
        try {
          const history = await getHistory(saved, 100)
          this.session = history.session
          this.messages = history.messages || []
          this.streamingText = ''
          this.liveNodes = []
          this.activeNode = ''
          this.busy = false
          if (this.session.status === 'closed') {
            await this.newSession()
          } else {
            await this.connect()
          }
          await this.loadSessions()
          return
        } catch {
          localStorage.removeItem(SESSION_KEY)
        }
      }
      await this.newSession()
      await this.loadSessions()
    },

    async loadSessions() {
      this.sessionsLoading = true
      try {
        const data = await listSessions(100)
        this.sessions = data.items || []
        this.sessionsTotal = Number(data.total || 0)
      } catch {
        // keep previous list when the history endpoint is temporarily unavailable
      } finally {
        this.sessionsLoading = false
      }
    },

    async selectSession(sessionId) {
      const target = Number(sessionId)
      if (!target || this.busy || this.session?.id === target) return
      this.error = ''
      let history
      try {
        history = await getHistory(target, 100)
      } catch (e) {
        this.error = e.message || '读取历史会话失败'
        return
      }
      this.closeSocket()
      this.session = history.session
      this.messages = history.messages || []
      this.streamingText = ''
      this.liveNodes = []
      this.activeNode = ''
      this.busy = false
      localStorage.setItem(SESSION_KEY, String(target))
      if (this.session.status === 'active') {
        await this.connect()
      } else {
        this.status = 'closed'
      }
      await this.loadSessions()
    },

    async newSession() {
      this.closeSocket()
      const data = await createSession('访客')
      this.session = data.session
      this.suggestions = data.suggestions || this.suggestions
      this.messages = [
        {
          id: 'welcome',
          role: 'bot',
          content: data.welcome,
          sources: [],
          trace: null,
          verified: true,
          rating: null,
          created_at: new Date().toISOString(),
        },
      ]
      this.streamingText = ''
      this.liveNodes = []
      this.activeNode = ''
      this.error = ''
      localStorage.setItem(SESSION_KEY, String(this.session.id))
      await this.connect()
    },

    connect() {
      if (!this.session?.id) return Promise.resolve()
      this.closeSocket()
      this.socket = new ChatSocket(this.session.id, event => this.handleEvent(event), true)
      this.status = 'connecting'
      return this.socket.connect().then(() => {
        if (this.status === 'connecting') this.status = 'idle'
      }).catch(() => {
        this.status = 'offline'
        this.error = '无法连接问答服务，请确认后端已启动'
      })
    },

    closeSocket() {
      if (this.socket) {
        this.socket.close()
        this.socket = null
      }
    },

    handleEvent(event) {
      if (event.type === 'ready') {
        this.session = { ...this.session, ...event.session }
        this.status = 'idle'
        return
      }
      if (event.type === 'user_message') {
        const last = this.messages[this.messages.length - 1]
        if (last && last.role === 'user' && last._optimistic) {
          this.messages.splice(this.messages.length - 1, 1, event.message)
        }
        return
      }
      if (event.type === 'node') {
        if (event.phase === 'start') {
          this.activeNode = event.node
          this.status = 'thinking'
        } else {
          this.activeNode = ''
          this.liveNodes.push({
            node: event.node,
            elapsed_ms: event.elapsed_ms,
            detail: event.detail || {},
          })
        }
        return
      }
      if (event.type === 'chunk') {
        if (this.status !== 'streaming') this.status = 'streaming'
        this.streamingText += event.delta || ''
        return
      }
      if (event.type === 'message_end') {
        this.messages.push(event.message)
        this.streamingText = ''
        this.activeNode = ''
        this.busy = false
        this.status = 'idle'
        this.loadSessions()
        return
      }
      if (event.type === 'session_status') {
        this.session = { ...this.session, ...event.session }
        return
      }
      if (event.type === 'error') {
        this.error = event.message || '服务返回错误'
        this.busy = false
        this.status = 'idle'
        return
      }
      if (event.type === 'socket_close') {
        this.status = 'offline'
        this.busy = false
        this.error = '连接已断开，点击重新连接'
      }
    },

    async send(content) {
      const text = content.trim()
      if (!text || this.busy) return
      if (!this.session || this.session.status !== 'active') {
        await this.newSession()
      }
      this.messages.push({
        id: `tmp-${Date.now()}`,
        role: 'user',
        content: text,
        _optimistic: true,
      })
      const needConnect = !this.socket || this.status === 'offline'
      this.busy = true
      this.status = 'thinking'
      this.streamingText = ''
      this.liveNodes = []
      this.error = ''
      try {
        if (needConnect) await this.connect()
        this.socket.send(text)
      } catch (e) {
        this.busy = false
        this.status = 'idle'
        this.error = e.message || '发送失败'
      }
    },

    async rate(message, rating) {
      if (!message?.id || message.id === 'welcome') return
      const previous = message.rating
      message.rating = rating
      try {
        await rateMessage(message.id, rating)
      } catch {
        message.rating = previous
      }
    },

    async close() {
      if (this.session?.id) {
        try {
          const session = await closeSession(this.session.id)
          this.session = { ...this.session, ...session }
        } catch {
          // ignore
        }
      }
      this.closeSocket()
      this.status = 'closed'
      await this.loadSessions()
    },
  },
})
