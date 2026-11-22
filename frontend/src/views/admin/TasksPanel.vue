<template>
  <div class="tasks">
    <div class="page-head">
      <div>
        <div class="eyebrow">TASKS</div>
        <h1>入库任务</h1>
        <p>上传、重建索引、删除与全量重建的实时进度。</p>
      </div>
      <div class="head-actions">
        <select v-model="status" class="select filter" @change="load(1)">
          <option value="">全部</option>
          <option value="queued">排队中</option>
          <option value="running">执行中</option>
          <option value="succeeded">已完成</option>
          <option value="failed">失败</option>
        </select>
        <button class="btn" @click="load(1)">刷新</button>
        <button class="btn btn-primary" @click="rebuild" :disabled="running">全量重建</button>
      </div>
    </div>

    <div class="summary-row">
      <div class="summary-card"><span class="summary-label">待处理</span><strong>{{ store.tasks.items.filter(t => t.status === 'queued' || t.status === 'running').length }}</strong><span class="tiny muted">当前页活跃任务</span></div>
      <div class="summary-card"><span class="summary-label">任务总数</span><strong>{{ store.tasks.total }}</strong><span class="tiny muted">全部入库任务</span></div>
      <div class="summary-card wide"><span class="summary-label">实时通道</span><strong class="ws-state" :class="store.wsStatus">{{ store.wsStatus === 'online' ? '已连接' : store.wsStatus === 'connecting' ? '连接中' : '离线' }}</strong><span class="tiny muted">进度由 WebSocket 推送</span></div>
    </div>

    <section class="panel table-panel">
      <div class="table-wrap">
        <table class="data">
          <thead><tr><th>任务</th><th>类型</th><th>状态</th><th>进度</th><th>切片</th><th>说明</th><th>时间</th></tr></thead>
          <tbody>
            <tr v-for="task in store.tasks.items" :key="task.id">
              <td><span class="task-id">#{{ task.id }}</span><div v-if="task.doc_uid" class="tiny muted mono">{{ task.doc_uid.slice(0, 10) }}</div></td>
              <td><span class="tag" :class="typeClass(task.task_type)">{{ typeLabel(task.task_type) }}</span></td>
              <td><span class="tag" :class="statusClass(task.status)">{{ statusLabel(task.status) }}</span></td>
              <td class="progress-cell">
                <div class="progress"><i :style="{ width: `${task.progress || 0}%` }"></i></div>
                <span class="tiny muted">{{ task.progress || 0 }}%</span>
              </td>
              <td class="mono small">{{ task.done_chunks }}<span class="muted">/{{ task.total_chunks }}</span></td>
              <td class="message-cell small">{{ task.message || '—' }}</td>
              <td class="small muted">{{ fmtDate(task.created_at) }}<div v-if="task.finished_at" class="tiny">完成 {{ fmtDate(task.finished_at) }}</div></td>
            </tr>
            <tr v-if="!store.tasks.items.length"><td colspan="7"><div class="empty small">还没有入库任务。</div></td></tr>
          </tbody>
        </table>
      </div>
      <PaginationBar
        :page="store.tasks.page"
        :size="store.tasks.size"
        :total="store.tasks.total"
        unit="条"
        @change="load"
      />
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useAdminStore } from '../../stores/admin'
import PaginationBar from '../../components/PaginationBar.vue'

const store = useAdminStore()
const status = ref('')
const running = ref(false)

const statusLabels = { queued: '排队中', running: '执行中', succeeded: '已完成', failed: '失败', cancelled: '已取消' }
const statusClasses = { queued: 'amber', running: 'blue', succeeded: 'green', failed: 'red', cancelled: '' }
const typeLabels = { upload: '上传', reindex: '重建索引', delete: '删除', rebuild: '全量重建' }
const typeClasses = { upload: 'brand', reindex: 'blue', delete: 'red', rebuild: 'amber' }
function statusLabel(value) { return statusLabels[value] || value }
function statusClass(value) { return statusClasses[value] || '' }
function typeLabel(value) { return typeLabels[value] || value }
function typeClass(value) { return typeClasses[value] || '' }
function fmtDate(value) { return value ? String(value).replace('T', ' ').slice(5, 16) : '' }

async function load(page = 1) {
  await store.loadTasks({ page, size: store.tasks.size || 20, status: status.value })
}
async function rebuild() {
  if (!window.confirm('全量重建会新建影子集合并重新向量化所有 ready 文档，确定开始吗？')) return
  running.value = true
  try { await store.rebuild() } catch (e) { store.error = e.message } finally { running.value = false }
}
onMounted(() => { if (!store.tasks.items.length) load(1) })
</script>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 14px; margin-bottom: 18px; }
.eyebrow { font-size: 9px; letter-spacing: 1.5px; color: var(--brand); font-weight: 800; }
h1 { margin: 5px 0 4px; font-size: 27px; letter-spacing: -0.5px; }
.page-head p { margin: 0; color: var(--muted); font-size: 12px; }
.head-actions { display: flex; gap: 8px; align-items: center; }
.filter { width: 120px; padding: 8px 10px; font-size: 12px; }
.summary-row { display: grid; grid-template-columns: 1fr 1fr 1.4fr; gap: 12px; margin-bottom: 14px; }
.summary-card { background: #fff; border: 1px solid var(--line); border-radius: 13px; padding: 14px; display: flex; flex-direction: column; gap: 4px; box-shadow: 0 7px 22px rgba(14,27,51,.04); }
.summary-label { font-size: 10px; color: var(--muted); }
.summary-card strong { font-size: 23px; letter-spacing: -0.4px; }
.ws-state { font-size: 13px !important; }
.ws-state.online { color: var(--success); }
.ws-state.connecting { color: var(--accent); }
.table-panel { padding: 12px 14px 14px; }
.task-id { font-family: "Cascadia Code", Consolas, monospace; font-size: 12px; font-weight: 700; }
.progress-cell { width: 150px; }
.progress-cell .progress { margin-bottom: 3px; }
.progress-cell span { font-family: "Cascadia Code", Consolas, monospace; }
.message-cell { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 760px) { .summary-row { grid-template-columns: 1fr 1fr; } .summary-card.wide { grid-column: span 2; } .page-head { flex-direction: column; align-items: flex-start; } }
</style>
