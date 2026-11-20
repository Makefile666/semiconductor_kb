<template>
  <div v-if="!store.loggedIn" class="admin-login-shell">
    <LoginPanel />
  </div>
  <div v-else class="admin-shell">
    <header class="admin-top">
      <div class="admin-brand">
        <div class="brand-mark">芯</div>
        <div>
          <div class="admin-name">芯知 SemiKB</div>
          <div class="admin-sub">知识库管理台</div>
        </div>
      </div>
      <nav class="admin-tabs">
        <button v-for="tab in tabs" :key="tab.key" :class="{ active: active === tab.key }" @click="active = tab.key">
          {{ tab.label }}
          <span v-if="tab.key === 'tasks' && store.tasks.items.some(t => t.status === 'running' || t.status === 'queued')" class="tab-dot"></span>
        </button>
      </nav>
      <div class="admin-right">
        <span class="ws-pill" :class="store.wsStatus"><i></i>{{ store.wsStatus === 'online' ? '实时在线' : store.wsStatus === 'connecting' ? '连接中' : '离线' }}</span>
        <router-link to="/" class="btn btn-sm">问答页</router-link>
        <span class="admin-user">{{ store.admin?.display_name || store.admin?.username }}</span>
        <button class="btn btn-sm btn-ghost" @click="doLogout">退出</button>
      </div>
    </header>

    <main class="admin-main">
      <div v-if="store.error" class="admin-error">{{ store.error }}<button @click="store.error = ''">×</button></div>
      <OverviewPanel v-if="active === 'overview'" />
      <DocumentsPanel v-else-if="active === 'documents'" />
      <TasksPanel v-else-if="active === 'tasks'" />
      <RetrievalPanel v-else-if="active === 'retrieval'" />
      <QaPanel v-else-if="active === 'qa'" />
      <MessagesPanel v-else-if="active === 'messages'" />
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useAdminStore } from '../../stores/admin'
import LoginPanel from './LoginPanel.vue'
import OverviewPanel from './OverviewPanel.vue'
import DocumentsPanel from './DocumentsPanel.vue'
import TasksPanel from './TasksPanel.vue'
import RetrievalPanel from './RetrievalPanel.vue'
import QaPanel from './QaPanel.vue'
import MessagesPanel from './MessagesPanel.vue'

const store = useAdminStore()
const active = ref('overview')
const tabs = [
  { key: 'overview', label: '总览' },
  { key: 'documents', label: '文档' },
  { key: 'tasks', label: '任务' },
  { key: 'retrieval', label: '检索调试' },
  { key: 'qa', label: '问答测试' },
  { key: 'messages', label: '消息审计' },
]

onMounted(async () => {
  await store.restore()
})

async function doLogout() {
  await store.logout()
}
</script>

<style scoped>
.admin-login-shell { min-height: 100vh; }
.admin-shell { min-height: 100vh; background: var(--paper); }
.admin-top { min-height: 70px; display: flex; align-items: center; gap: 24px; padding: 12px 24px; background: rgba(255,255,255,.86); border-bottom: 1px solid var(--line); backdrop-filter: blur(14px); position: sticky; top: 0; z-index: 20; }
.admin-brand { display: flex; align-items: center; gap: 9px; flex: 0 0 auto; }
.brand-mark { width: 34px; height: 34px; border-radius: 10px; background: linear-gradient(145deg, #0b1324, #1d4f63); color: #c8fbff; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 13px; }
.admin-name { font-size: 14px; font-weight: 800; }
.admin-sub { font-size: 10px; color: var(--muted); margin-top: 1px; }
.admin-tabs { display: flex; align-items: center; gap: 3px; flex: 1; overflow-x: auto; }
.admin-tabs button { border: 0; background: transparent; border-radius: 8px; padding: 8px 12px; font-size: 12px; color: var(--ink-3); white-space: nowrap; position: relative; font-weight: 600; }
.admin-tabs button:hover { background: #f1f7f6; color: var(--brand); }
.admin-tabs button.active { background: var(--brand-soft); color: var(--brand); }
.tab-dot { width: 6px; height: 6px; background: var(--accent); border-radius: 50%; display: inline-block; margin-left: 3px; vertical-align: 2px; }
.admin-right { display: flex; align-items: center; gap: 9px; flex: 0 0 auto; }
.ws-pill { display: inline-flex; align-items: center; gap: 5px; font-size: 10px; color: var(--muted); }
.ws-pill i { width: 6px; height: 6px; border-radius: 50%; background: #94a3b8; }
.ws-pill.online i { background: var(--success); }
.ws-pill.connecting i { background: var(--accent); }
.admin-user { font-size: 11px; color: var(--muted); max-width: 150px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.admin-main { max-width: 1440px; margin: 0 auto; padding: 22px 24px 34px; }
.admin-error { display: flex; justify-content: space-between; background: #fff7ed; color: #9a3412; border: 1px solid #fed7aa; border-radius: 10px; padding: 10px 12px; font-size: 12px; margin-bottom: 14px; }
.admin-error button { border: 0; background: transparent; color: inherit; font-size: 16px; }
@media (max-width: 980px) {
  .admin-top { flex-wrap: wrap; gap: 10px; }
  .admin-tabs { order: 3; flex-basis: 100%; }
  .admin-right { margin-left: auto; }
}
</style>
