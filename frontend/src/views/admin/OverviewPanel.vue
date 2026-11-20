<template>
  <div class="overview">
    <div class="page-head">
      <div>
        <div class="eyebrow">OVERVIEW</div>
        <h1>知识库总览</h1>
        <p>文档、问答质量与运行时状态，一屏看清。</p>
      </div>
      <div class="head-actions">
        <select v-model.number="days" class="select days" @change="refreshStats">
          <option :value="7">近 7 天</option>
          <option :value="14">近 14 天</option>
          <option :value="30">近 30 天</option>
        </select>
        <button class="btn btn-primary" @click="refreshAll" :disabled="loading">{{ loading ? '刷新中' : '刷新数据' }}</button>
      </div>
    </div>

    <div class="stat-grid">
      <div class="stat-card">
        <span class="stat-icon sea">文</span>
        <div class="stat-label">已入库文档</div>
        <div class="stat-value">{{ stats?.documents?.ready || 0 }}<small>/ {{ stats?.documents?.total || 0 }}</small></div>
        <div class="stat-foot">ready / 全部文档</div>
      </div>
      <div class="stat-card">
        <span class="stat-icon blue">片</span>
        <div class="stat-label">知识切片</div>
        <div class="stat-value">{{ formatNumber(stats?.documents?.chunks) }}</div>
        <div class="stat-foot">Milvus 可检索片段</div>
      </div>
      <div class="stat-card">
        <span class="stat-icon amber">问</span>
        <div class="stat-label">窗口内问答</div>
        <div class="stat-value">{{ stats?.qa?.window || 0 }}</div>
        <div class="stat-foot">累计 {{ stats?.qa?.total || 0 }} 次</div>
      </div>
      <div class="stat-card">
        <span class="stat-icon green">引</span>
        <div class="stat-label">引用覆盖率</div>
        <div class="stat-value">{{ percent(stats?.quality?.citation_rate) }}</div>
        <div class="stat-foot">{{ stats?.quality?.rated || 0 }} 次评价</div>
      </div>
      <div class="stat-card">
        <span class="stat-icon sea">验</span>
        <div class="stat-label">回答校验通过</div>
        <div class="stat-value">{{ percent(stats?.quality?.verified_rate) }}</div>
        <div class="stat-foot">生成校验 grounded + 解决</div>
      </div>
      <div class="stat-card">
        <span class="stat-icon blue">速</span>
        <div class="stat-label">平均时延</div>
        <div class="stat-value">{{ stats?.latency?.avg_ms || 0 }}<small>ms</small></div>
        <div class="stat-foot">P95 {{ stats?.latency?.p95_ms || 0 }} ms</div>
      </div>
    </div>

    <div class="two-col">
      <section class="panel block">
        <div class="block-head">
          <div><div class="block-title">检索来源分布</div><div class="block-sub">回答走本地库还是联网兜底</div></div>
          <span class="tag brand">{{ days }} 天</span>
        </div>
        <div v-if="stats?.routes?.length" class="route-bars">
          <div v-for="route in stats.routes" :key="route.source" class="route-row">
            <div class="route-label"><span class="route-dot" :class="route.source"></span>{{ routeLabel(route.source) }}</div>
            <div class="route-track"><div class="route-fill" :class="route.source" :style="{ width: barWidth(route.count) }"></div></div>
            <span class="route-count">{{ route.count }}</span>
          </div>
        </div>
        <div v-else class="empty small">窗口内还没有问答记录。</div>
        <div class="quality-row">
          <div class="quality-box"><span>改写率</span><strong>{{ percent(stats?.quality?.rewrite_rate) }}</strong></div>
          <div class="quality-box"><span>重生成率</span><strong>{{ percent(stats?.quality?.regenerate_rate) }}</strong></div>
          <div class="quality-box"><span>满意度</span><strong>{{ percent(stats?.quality?.satisfied_rate) }}</strong></div>
        </div>
      </section>

      <section class="panel block">
        <div class="block-head">
          <div><div class="block-title">热门引用文档</div><div class="block-sub">按引用次数排序</div></div>
        </div>
        <div v-if="stats?.top_documents?.length" class="top-docs">
          <div v-for="(doc, index) in stats.top_documents" :key="doc.doc_uid + index" class="top-doc">
            <span class="doc-rank">{{ index + 1 }}</span>
            <div class="doc-info">
              <div class="ellipsis doc-title">{{ doc.title }}</div>
              <div class="tiny muted mono">{{ doc.filename || doc.doc_uid }}</div>
            </div>
            <span class="cite-count">{{ doc.citations }} 次</span>
          </div>
        </div>
        <div v-else class="empty small">暂无引用统计。</div>
      </section>
    </div>

    <div class="two-col lower">
      <section class="panel block">
        <div class="block-head">
          <div><div class="block-title">近 {{ days }} 天问答趋势</div><div class="block-sub">每日问答量与引用回答数</div></div>
        </div>
        <div class="series" v-if="stats?.series?.length">
          <div v-for="day in stats.series" :key="day.date" class="series-col">
            <div class="series-bars">
              <div class="bar qa" :style="{ height: seriesHeight(day.qa_count) }"></div>
              <div class="bar cite" :style="{ height: seriesHeight(day.citation_count) }"></div>
            </div>
            <span class="series-num">{{ day.qa_count }}</span>
            <span class="series-date">{{ shortDate(day.date) }}</span>
          </div>
        </div>
        <div v-else class="empty small">暂无趋势数据。</div>
        <div class="legend"><span><i class="qa"></i>问答</span><span><i class="cite"></i>含引用</span></div>
      </section>

      <section class="panel block health-block">
        <div class="block-head">
          <div><div class="block-title">运行时状态</div><div class="block-sub">依赖与模型</div></div>
          <span class="tag" :class="health?.status === 'ok' ? 'green' : 'amber'">{{ health?.status === 'ok' ? '健康' : '降级' }}</span>
        </div>
        <div class="health-list">
          <div v-for="item in healthRows" :key="item.key" class="health-row">
            <span class="health-dot" :class="item.status"></span>
            <div class="health-main"><strong>{{ item.label }}</strong><span class="tiny muted">{{ item.detail }}</span></div>
            <span class="tag" :class="item.status === 'up' ? 'green' : 'red'">{{ item.status }}</span>
          </div>
        </div>
        <div class="health-foot muted tiny">uptime {{ formatUptime(health?.uptime_seconds) }} · {{ config?.brand?.name || '芯知 SemiKB' }}</div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAdminStore } from '../../stores/admin'

const store = useAdminStore()
const days = ref(7)
const loading = ref(false)
const stats = computed(() => store.stats)
const health = computed(() => store.health)
const config = computed(() => store.config)

const healthRows = computed(() => {
  const c = health.value?.components || {}
  return [
    { key: 'mysql', label: 'MySQL', status: c.mysql?.status || 'down', detail: c.mysql?.version || c.mysql?.error || '未连接' },
    { key: 'milvus', label: 'Milvus', status: c.milvus?.status || 'down', detail: `v${c.milvus?.version || '?'} · ${c.milvus?.entities || 0} 条` },
    { key: 'embedding', label: 'Embedding', status: c.embedding?.status || 'down', detail: `${c.embedding?.model || '?'} · ${c.embedding?.dim || 0} 维` },
    { key: 'llm', label: 'Chat LLM', status: c.llm?.status || 'down', detail: c.llm?.model || '未配置' },
  ]
})

function percent(value) { return `${Math.round(Number(value || 0) * 100)}%` }
function formatNumber(value) { return Number(value || 0).toLocaleString('zh-CN') }
function formatUptime(seconds) {
  const value = Number(seconds || 0)
  if (value < 60) return `${value}s`
  if (value < 3600) return `${Math.floor(value / 60)}m`
  return `${Math.floor(value / 3600)}h ${Math.floor((value % 3600) / 60)}m`
}
function shortDate(date) { return String(date || '').slice(5) }
function routeLabel(source) {
  return { vectorstore: '本地知识库', web_search: '联网搜索', extractive: '抽取兜底', fallback: '兜底回答', direct: '直接回答' }[source] || source
}
function barWidth(count) {
  const max = Math.max(...(stats.value?.routes || []).map(x => x.count), 1)
  return `${Math.max(4, Math.round((count / max) * 100))}%`
}
function seriesHeight(count) {
  const max = Math.max(...(stats.value?.series || []).map(x => Math.max(x.qa_count, x.citation_count)), 1)
  return `${Math.max(3, Math.round((count / max) * 100))}%`
}
async function refreshStats() {
  loading.value = true
  try { await store.loadStats(days.value) } finally { loading.value = false }
}
async function refreshAll() {
  loading.value = true
  try {
    await Promise.all([store.loadStats(days.value), store.loadHealth(), store.loadConfig()])
  } finally { loading.value = false }
}
onMounted(async () => {
  if (!store.stats) await store.loadStats(days.value)
  if (!store.health) await store.loadHealth()
})
</script>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; margin-bottom: 20px; }
.eyebrow { font-size: 9px; letter-spacing: 1.5px; color: var(--brand); font-weight: 800; }
h1 { margin: 5px 0 4px; font-size: 27px; letter-spacing: -0.5px; }
.page-head p { margin: 0; color: var(--muted); font-size: 12px; }
.head-actions { display: flex; gap: 8px; align-items: center; }
.days { width: auto; padding: 8px 10px; font-size: 12px; }
.stat-grid { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: 13px; margin-bottom: 16px; }
.stat-card { background: #fff; border: 1px solid var(--line); border-radius: 15px; padding: 16px; box-shadow: 0 7px 24px rgba(14,27,51,.045); }
.stat-icon { width: 27px; height: 27px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; margin-bottom: 12px; }
.stat-icon.sea { background: #e6f7f5; color: var(--brand); }
.stat-icon.blue { background: #eff6ff; color: #1d4ed8; }
.stat-icon.amber { background: #fff7ed; color: #c2410c; }
.stat-icon.green { background: #ecfdf3; color: var(--success); }
.stat-label { font-size: 11px; color: var(--muted); }
.stat-value { font-size: 25px; font-weight: 800; letter-spacing: -0.7px; margin: 3px 0 3px; }
.stat-value small { font-size: 12px; font-weight: 500; color: var(--muted); margin-left: 3px; }
.stat-foot { font-size: 10px; color: #9aa7bd; }
.two-col { display: grid; grid-template-columns: 1.05fr .95fr; gap: 16px; margin-bottom: 16px; }
.two-col.lower { grid-template-columns: 1.25fr .75fr; }
.block { padding: 18px; }
.block-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 16px; }
.block-title { font-weight: 800; font-size: 14px; }
.block-sub { font-size: 11px; color: var(--muted); margin-top: 3px; }
.route-bars { display: grid; gap: 12px; }
.route-row { display: grid; grid-template-columns: 92px 1fr 40px; gap: 9px; align-items: center; }
.route-label { font-size: 11px; color: var(--ink-3); display: flex; align-items: center; gap: 6px; }
.route-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--brand); }
.route-dot.web_search { background: #2563eb; }
.route-dot.direct { background: #16a34a; }
.route-dot.extractive { background: var(--accent); }
.route-dot.fallback { background: #94a3b8; }
.route-track { height: 7px; background: #edf1f7; border-radius: 999px; overflow: hidden; }
.route-fill { height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--brand), var(--brand-2)); }
.route-fill.web_search { background: linear-gradient(90deg, #2563eb, #38bdf8); }
.route-fill.direct { background: linear-gradient(90deg, #15803d, #4ade80); }
.route-fill.extractive { background: linear-gradient(90deg, #d97706, #fbbf24); }
.route-fill.fallback { background: #94a3b8; }
.route-count { font-size: 11px; text-align: right; color: var(--ink-3); font-family: "Cascadia Code", Consolas, monospace; }
.quality-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 20px; padding-top: 14px; border-top: 1px dashed #e5ebf4; }
.quality-box { background: #f8fafc; border-radius: 9px; padding: 10px; display: flex; flex-direction: column; gap: 3px; }
.quality-box span { font-size: 10px; color: var(--muted); }
.quality-box strong { font-size: 16px; }
.top-docs { display: grid; gap: 8px; }
.top-doc { display: flex; align-items: center; gap: 9px; padding-bottom: 8px; border-bottom: 1px dashed #edf1f7; }
.top-doc:last-child { border-bottom: 0; padding-bottom: 0; }
.doc-rank { flex: 0 0 20px; height: 20px; border-radius: 6px; background: #f1f5f9; color: var(--muted); display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; }
.doc-info { min-width: 0; flex: 1; }
.doc-title { font-size: 12px; font-weight: 600; }
.cite-count { font-size: 10px; color: var(--brand); background: var(--brand-soft); padding: 2px 7px; border-radius: 999px; }
.series { height: 150px; display: flex; align-items: flex-end; gap: 6px; padding-top: 6px; }
.series-col { flex: 1; display: flex; flex-direction: column; align-items: center; height: 100%; justify-content: flex-end; gap: 2px; min-width: 0; }
.series-bars { width: 100%; height: 100%; display: flex; gap: 2px; align-items: flex-end; justify-content: center; }
.bar { width: 36%; border-radius: 4px 4px 0 0; min-height: 2px; }
.bar.qa { background: linear-gradient(180deg, #2dd4bf, #0f766e); }
.bar.cite { background: #dbe4f0; }
.series-num { font-size: 9px; color: var(--ink-3); margin-top: 3px; }
.series-date { font-size: 9px; color: var(--muted); }
.legend { display: flex; gap: 14px; margin-top: 12px; padding-top: 9px; border-top: 1px dashed #e5ebf4; font-size: 10px; color: var(--muted); }
.legend span { display: inline-flex; align-items: center; gap: 5px; }
.legend i { width: 7px; height: 7px; border-radius: 2px; background: #0f766e; }
.legend i.cite { background: #dbe4f0; }
.health-list { display: grid; gap: 11px; }
.health-row { display: flex; align-items: center; gap: 9px; }
.health-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--danger); }
.health-dot.up { background: var(--success); }
.health-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.health-main strong { font-size: 12px; }
.health-foot { margin-top: 15px; padding-top: 11px; border-top: 1px dashed #e5ebf4; }
@media (max-width: 1100px) { .stat-grid { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 760px) { .stat-grid { grid-template-columns: repeat(2, 1fr); } .two-col, .two-col.lower { grid-template-columns: 1fr; } .page-head { align-items: flex-start; flex-direction: column; } }
</style>
