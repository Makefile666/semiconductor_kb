<template>
  <div class="messages-page">
    <div class="page-head">
      <div>
        <div class="eyebrow">AUDIT</div>
        <h1>消息审计</h1>
        <p>查看助手回答、引用、校验结果与用户评价。</p>
      </div>
    </div>

    <section class="panel filter-panel">
      <div class="filters">
        <select v-model="source" class="select">
          <option value="">全部来源</option>
          <option value="vectorstore">本地文档</option>
          <option value="web_search">联网搜索</option>
          <option value="direct">直接回答</option>
          <option value="extractive">抽取兜底</option>
          <option value="fallback">兜底回答</option>
        </select>
        <select v-model.number="days" class="select">
          <option :value="0">全部时间</option>
          <option :value="1">今天</option>
          <option :value="7">近 7 天</option>
          <option :value="30">近 30 天</option>
        </select>
        <input v-model="keyword" class="field search" placeholder="搜索回答内容" @keydown.enter="load(1)" />
        <button class="btn" @click="load(1)">筛选</button>
      </div>
      <span class="muted small">共 {{ store.messages.total }} 条</span>
    </section>

    <section class="panel table-panel">
      <div class="table-wrap">
        <table class="data">
          <thead><tr><th>回答</th><th>来源</th><th>校验</th><th>引用</th><th>评价</th><th>时延</th><th>时间</th><th></th></tr></thead>
          <tbody>
            <tr v-for="item in store.messages.items" :key="item.id">
              <td class="content-cell">
                <div class="content-text">{{ item.content }}</div>
                <div class="tiny muted">会话 #{{ item.session_id }}</div>
              </td>
              <td><span class="tag" :class="sourceClass(item.source)">{{ sourceLabel(item.source) }}</span></td>
              <td><span class="tag" :class="item.verified ? 'green' : 'amber'">{{ item.verified ? '通过' : '未过' }}</span></td>
              <td><span class="mono">{{ item.citation_count }}</span></td>
              <td><span v-if="item.rating === 1" class="rating up">赞</span><span v-else-if="item.rating === -1" class="rating down">踩</span><span v-else class="muted small">—</span></td>
              <td class="mono small">{{ item.latency_ms || 0 }} ms</td>
              <td class="small muted">{{ fmtDate(item.created_at) }}</td>
              <td><button class="btn btn-sm" @click="openDetail(item)">详情</button></td>
            </tr>
            <tr v-if="!store.messages.items.length"><td colspan="8"><div class="empty small">暂无回答记录。</div></td></tr>
          </tbody>
        </table>
      </div>
      <PaginationBar
        :page="store.messages.page"
        :size="store.messages.size"
        :total="store.messages.total"
        unit="条"
        @change="load"
      />
    </section>

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal message-modal">
        <div class="modal-head">
          <div><h3>回答详情</h3><div class="tiny muted">消息 #{{ detail.id }} · 会话 #{{ detail.session_id }}</div></div>
          <button class="icon-close" @click="detail = null">×</button>
        </div>
        <div class="detail-tags">
          <span class="tag" :class="sourceClass(detail.source)">{{ sourceLabel(detail.source) }}</span>
          <span class="tag" :class="detail.verified ? 'green' : 'amber'">{{ detail.verified ? '校验通过' : '未通过校验' }}</span>
          <span class="tag">{{ detail.latency_ms }} ms</span>
          <span class="tag" v-if="detail.rating">{{ detail.rating === 1 ? '用户赞' : '用户踩' }}</span>
        </div>
        <div class="detail-content">{{ detail.content }}</div>
        <CitationList :sources="detail.sources" />
        <TraceTimeline v-if="detail.trace" :trace="detail.trace" :nodes="detail.trace.nodes || []" />
        <div class="session-box">
          <span>访客 {{ detail.session?.visitor_name || '—' }}</span>
          <span>轮次 {{ detail.session?.turn_count || 0 }}</span>
          <span>{{ fmtDate(detail.created_at) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useAdminStore } from '../../stores/admin'
import { messageDetail } from '../../api/admin'
import CitationList from '../../components/CitationList.vue'
import PaginationBar from '../../components/PaginationBar.vue'
import TraceTimeline from '../../components/TraceTimeline.vue'

const store = useAdminStore()
const source = ref('')
const days = ref(7)
const keyword = ref('')
const detail = ref(null)

const sourceLabels = { vectorstore: '本地文档', web_search: '联网', extractive: '抽取', fallback: '兜底', direct: '直接回答' }
const sourceClasses = { vectorstore: 'brand', web_search: 'blue', extractive: 'amber', fallback: '', direct: 'green' }
function sourceLabel(value) { return sourceLabels[value] || value || '未知' }
function sourceClass(value) { return sourceClasses[value] || '' }
function fmtDate(value) { return value ? String(value).replace('T', ' ').slice(5, 16) : '' }

async function load(page = 1) {
  await store.loadMessages({
    page, size: store.messages.size || 20, source: source.value,
    days: days.value || undefined, keyword: keyword.value,
  })
}
async function openDetail(item) {
  try { detail.value = await messageDetail(item.id) } catch (e) { store.error = e.message }
}
onMounted(() => { if (!store.messages.items.length) load(1) })
</script>

<style scoped>
.page-head { margin-bottom: 18px; }
.eyebrow { font-size: 9px; letter-spacing: 1.5px; color: var(--brand); font-weight: 800; }
h1 { margin: 5px 0 4px; font-size: 27px; letter-spacing: -0.5px; }
.page-head p { margin: 0; color: var(--muted); font-size: 12px; }
.filter-panel { padding: 12px 14px; display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
.filters { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.select { width: 120px; padding: 8px 10px; font-size: 12px; }
.search { width: 220px; padding: 8px 10px; font-size: 12px; }
.table-panel { padding: 12px 14px 14px; }
.content-cell { max-width: 390px; }
.content-text { font-size: 12px; line-height: 1.6; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.rating { font-size: 11px; padding: 2px 7px; border-radius: 999px; }
.rating.up { color: var(--success); background: var(--success-soft); }
.rating.down { color: var(--danger); background: var(--danger-soft); }
.icon-close { border: 0; background: transparent; font-size: 22px; color: var(--muted); }
.modal-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.detail-tags { display: flex; gap: 6px; flex-wrap: wrap; margin: 14px 0; }
.detail-content { font-size: 13px; line-height: 1.8; white-space: pre-wrap; background: #fbfdff; border: 1px solid #e8edf5; border-radius: 10px; padding: 13px; }
.session-box { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 15px; padding-top: 11px; border-top: 1px dashed #e5ebf4; font-size: 11px; color: var(--muted); }
@media (max-width: 760px) { .filter-panel { flex-direction: column; align-items: flex-start; } .search { width: 180px; } }
</style>
