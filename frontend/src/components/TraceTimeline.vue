<template>
  <div class="trace">
    <button class="trace-head" @click="open = !open">
      <span class="trace-mark">⌁</span>
      <span>{{ headLabel }}</span>
      <span v-if="summary" class="small muted">{{ summary }}</span>
      <span class="chev" :class="{ up: open }">⌄</span>
    </button>
    <div v-if="open" class="trace-body">
      <div class="trace-summary" v-if="trace">
        <span class="tag" :class="verifiedClass">{{ traceVerifiedLabel }}</span>
        <span class="tag blue" v-if="trace.route">路由 {{ routeLabel(trace.route) }}</span>
        <span class="tag" v-if="trace.rewrite_count">改写 {{ trace.rewrite_count }} 次</span>
        <span class="tag" v-if="trace.regenerate_count">重生成 {{ trace.regenerate_count }} 次</span>
        <span class="tag">LLM {{ trace.llm_calls || 0 }} 次</span>
        <span class="tag" v-if="trace.latency_ms">{{ trace.latency_ms }} ms</span>
      </div>
      <div v-if="nodes?.length" class="nodes">
        <div v-for="(node, index) in nodes" :key="`${node.node}-${index}`" class="node">
          <div class="node-dot"></div>
          <div class="node-main">
            <div class="node-line">
              <strong>{{ label(node.node) }}</strong>
              <span class="muted small">{{ node.elapsed_ms }} ms</span>
            </div>
            <div class="node-detail" v-if="detail(node)">
              <span v-for="item in detail(node)" :key="item[0]" class="detail-chip">{{ item[0] }} {{ item[1] }}</span>
            </div>
          </div>
        </div>
      </div>
      <div v-else class="muted small">本次回答没有可展示的节点记录。</div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  trace: { type: Object, default: null },
  nodes: { type: Array, default: () => [] },
  live: { type: Boolean, default: false },
})
const open = ref(false)

const labels = {
  route_question: '问题路由',
  retrieve: '向量检索',
  grade_documents: '文档评分',
  generate: '生成回答',
  grade_generation: '生成校验',
  transform_query: '问题改写',
  web_search: '联网搜索',
  direct_answer: '直接回答',
}

function label(name) { return labels[name] || name }
function routeLabel(value) {
  return { vectorstore: '本地知识库', web_search: '联网搜索', direct: '直接回答' }[value] || value
}
const verifiedClass = computed(() => (props.trace?.verified ? 'green' : 'amber'))
const traceVerifiedLabel = computed(() => {
  if (props.trace?.route === 'direct') return '无需校验'
  return props.trace?.verified ? '已校验' : '未校验'
})
const headLabel = computed(() => (props.trace?.route === 'direct' ? '回答过程' : '检索过程'))
const summary = computed(() => {
  if (!props.trace) return props.live ? '正在执行' : ''
  const parts = []
  if (props.trace.route) parts.push(routeLabel(props.trace.route))
  if (props.trace.terminated_by) {
    parts.push(props.trace.terminated_by === 'direct' ? '无需检索' : props.trace.terminated_by)
  }
  return parts.join(' · ')
})

const detailKeys = ['hits', 'kept', 'total', 'route', 'method', 'chars', 'grounded', 'answers_question', 'results', 'rewritten_question', 'error']
function detail(node) {
  const d = node?.detail || {}
  return detailKeys
    .filter(key => d[key] !== undefined && d[key] !== '' && d[key] !== null)
    .map(key => [key, String(d[key]).slice(0, 70)])
}
</script>

<style scoped>
.trace { margin-top: 12px; padding-top: 10px; border-top: 1px dashed #dbe4f0; }
.trace-head { display: flex; align-items: center; gap: 8px; border: 0; background: transparent; padding: 0; color: var(--ink-3); font-size: 12px; font-weight: 600; }
.trace-mark { width: 20px; height: 20px; border-radius: 6px; background: #eff6ff; color: #1d4ed8; display: inline-flex; align-items: center; justify-content: center; }
.chev { color: var(--muted); transition: 0.2s; margin-left: auto; }
.chev.up { transform: rotate(180deg); }
.trace-body { margin-top: 10px; }
.trace-summary { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.nodes { display: grid; gap: 0; }
.node { display: flex; gap: 10px; position: relative; padding-bottom: 12px; }
.node:last-child { padding-bottom: 0; }
.node-dot { flex: 0 0 8px; height: 8px; border-radius: 50%; background: var(--brand-2); margin-top: 6px; position: relative; }
.node-dot::after { content: ""; position: absolute; left: 3px; top: 12px; width: 1px; height: calc(100% + 8px); background: #dbe4f0; }
.node:last-child .node-dot::after { display: none; }
.node-main { min-width: 0; }
.node-line { display: flex; align-items: baseline; gap: 8px; font-size: 13px; }
.node-detail { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 4px; }
.detail-chip { font-size: 11px; color: #5d6b82; background: #f1f5f9; border-radius: 5px; padding: 2px 6px; }
</style>
