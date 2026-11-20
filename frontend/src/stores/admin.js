import { defineStore } from 'pinia'
import { getToken, setToken } from '../api/http'
import * as api from '../api/admin'
import { AdminSocket } from '../sockets/AdminSocket'

export const useAdminStore = defineStore('admin', {
  state: () => ({
    token: getToken(),
    admin: null,
    stats: null,
    health: null,
    config: null,
    documents: { items: [], total: 0, page: 1, size: 20 },
    tasks: { items: [], total: 0, page: 1, size: 20 },
    messages: { items: [], total: 0, page: 1, size: 20 },
    wsStatus: 'idle',
    socket: null,
    error: '',
    loading: false,
  }),
  getters: {
    loggedIn: state => Boolean(state.token && state.admin),
  },
  actions: {
    async restore() {
      if (!this.token) return false
      try {
        this.admin = await api.me()
        this.connect()
        await this.loadAll()
        return true
      } catch {
        this.reset()
        return false
      }
    },

    async login(username, password) {
      this.error = ''
      const data = await api.login(username, password)
      this.token = data.token
      setToken(data.token)
      this.admin = data.admin
      this.connect()
      await this.loadAll()
    },

    async logout() {
      try {
        if (this.token) await api.logout()
      } catch {
        // ignore
      }
      this.reset()
    },

    reset() {
      this.closeSocket()
      this.token = ''
      this.admin = null
      this.stats = null
      this.health = null
      this.config = null
      setToken('')
    },

    connect() {
      this.closeSocket()
      if (!this.token) return
      this.wsStatus = 'connecting'
      this.socket = new AdminSocket(this.token, event => this.handleEvent(event))
      this.socket.connect()
    },

    closeSocket() {
      if (this.socket) {
        this.socket.close()
        this.socket = null
      }
      this.wsStatus = 'idle'
    },

    handleEvent(event) {
      if (event.type === 'hello') {
        this.wsStatus = 'online'
        return
      }
      if (event.type === 'pong') return
      if (event.type === 'task_update') {
        const task = event.task
        const index = this.tasks.items.findIndex(item => item.id === task.id)
        if (index >= 0) this.tasks.items.splice(index, 1, { ...this.tasks.items[index], ...task })
        else this.loadTasks({ page: 1, size: this.tasks.size })
        if (task.status === 'succeeded' || task.status === 'failed') {
          this.loadDocuments({ page: 1, size: this.documents.size })
          this.loadStats(this.stats?.days || 7)
        }
        return
      }
      if (event.type === 'document_update') {
        this.loadDocuments({ page: this.documents.page, size: this.documents.size })
        return
      }
      if (event.type === 'socket_close') {
        this.wsStatus = 'offline'
      }
    },

    async loadAll() {
      this.loading = true
      try {
        await Promise.all([
          this.loadStats(7),
          this.loadDocuments({ page: 1, size: 20 }),
          this.loadTasks({ page: 1, size: 20 }),
          this.loadHealth(),
          this.loadConfig(),
        ])
      } finally {
        this.loading = false
      }
    },

    async loadStats(days = 7) {
      this.stats = await api.overview(days)
    },

    async loadDocuments(params = {}) {
      const data = await api.documents(params)
      this.documents = data
    },

    async loadTasks(params = {}) {
      const data = await api.tasks(params)
      this.tasks = data
    },

    async loadMessages(params = {}) {
      const data = await api.messages(params)
      this.messages = data
    },

    async loadHealth() {
      this.health = await api.health()
    },

    async loadConfig() {
      this.config = await api.config()
    },

    async uploadFiles(files) {
      this.error = ''
      const data = await api.upload(files)
      await this.loadDocuments({ page: 1, size: this.documents.size })
      await this.loadTasks({ page: 1, size: this.tasks.size })
      return data
    },

    async reindex(docUid) {
      await api.reindex(docUid)
      await this.loadDocuments({ page: this.documents.page, size: this.documents.size })
      await this.loadTasks({ page: 1, size: this.tasks.size })
    },

    async removeDocument(docUid) {
      await api.removeDocument(docUid)
      await this.loadDocuments({ page: this.documents.page, size: this.documents.size })
      await this.loadTasks({ page: 1, size: this.tasks.size })
    },

    async rebuild() {
      await api.rebuild()
      await this.loadTasks({ page: 1, size: this.tasks.size })
    },
  },
})
