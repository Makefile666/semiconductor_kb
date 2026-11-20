<template>
  <div class="message" :class="message.role">
    <div class="avatar" :class="message.role">{{ message.role === 'user' ? '访' : '芯' }}</div>
    <div class="bubble-wrap">
      <div class="bubble">
        <div class="bubble-text" v-html="rendered"></div>
        <div v-if="message.role === 'bot'" class="bubble-tools">
          <span class="tag" :class="sourceClass">{{ sourceLabel }}</span>
          <span v-if="message.verified === false" class="tag amber">未校验</span>
          <span v-if="message.latency_ms" class="tiny muted">{{ message.latency_ms }} ms</span>
          <span class="tiny muted">{{ time }}</span>
          <span class="rate" v-if="message.id !== 'welcome'">
            <button :class="{ active: message.rating === 1 }" title="有帮助" @click="$emit('rate', message, 1)">赞</button>
            <button :class="{ active: message.rating === -1 }" title="没帮助" @click="$emit('rate', message, -1)">踩</button>
          </span>
        </div>
      </div>
      <CitationList v-if="message.role === 'bot' && message.sources?.length" :sources="message.sources" />
      <TraceTimeline v-if="message.role === 'bot' && message.trace" :trace="message.trace" :nodes="message.trace.nodes" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import CitationList from './CitationList.vue'
import TraceTimeline from './TraceTimeline.vue'

const props = defineProps({ message: { type: Object, required: true } })
defineEmits(['rate'])

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

const rendered = computed(() => {
  let text = escapeHtml(props.message.content)
  text = text.replace(/```([\s\S]*?)```/g, '<pre class="code-block">$1</pre>')
  text = text.replace(/`([^`]+)`/g, '<code>$1</code>')
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  text = text.replace(/\[(\d+)\]/g, '<span class="cite-ref">[$1]</span>')
  text = text.replace(/^###\s+/gm, '<span class="md-h3">').replace(/^##\s+/gm, '<span class="md-h2">')
  return text
})

const sourceLabel = computed(() => {
  const labels = { vectorstore: '本地文档', web_search: '联网搜索', extractive: '抽取兜底', fallback: '兜底回答', direct: '直接回答' }
  return labels[props.message.source] || (props.message.role === 'bot' ? '回答' : '')
})
const sourceClass = computed(() => {
  if (props.message.source === 'web_search') return 'blue'
  if (props.message.source === 'direct') return 'green'
  if (props.message.source === 'fallback' || props.message.source === 'extractive') return 'amber'
  return 'brand'
})
const time = computed(() => {
  if (!props.message.created_at) return ''
  try {
    const d = new Date(props.message.created_at)
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  } catch {
    return ''
  }
})
</script>

<style scoped>
.message { display: flex; gap: 12px; margin-bottom: 22px; align-items: flex-start; }
.message.user { flex-direction: row-reverse; }
.avatar {
  flex: 0 0 34px; width: 34px; height: 34px; border-radius: 11px; display: flex;
  align-items: center; justify-content: center; font-size: 13px; font-weight: 700;
}
.avatar.bot { background: linear-gradient(135deg, #0b1324, #193554); color: #d9fbff; }
.avatar.user { background: #e6f7f5; color: var(--brand); }
.bubble-wrap { max-width: min(760px, calc(100vw - 110px)); min-width: 0; }
.message.user .bubble-wrap { max-width: min(620px, calc(100vw - 110px)); }
.bubble {
  background: #fff; border: 1px solid var(--line); border-radius: 3px 16px 16px 16px;
  padding: 14px 16px; box-shadow: 0 5px 18px rgba(14, 27, 51, 0.045);
}
.message.user .bubble { background: #0b1324; border-color: #0b1324; color: #f7fbff; border-radius: 16px 3px 16px 16px; }
.bubble-text { font-size: 14px; line-height: 1.8; white-space: pre-wrap; word-break: break-word; }
.bubble-text :deep(.cite-ref) { color: var(--brand); font-weight: 700; font-size: 12px; padding: 0 1px; }
.message.user .bubble-text :deep(.cite-ref) { color: #7dd3fc; }
.bubble-text :deep(code) { background: #f1f5f9; padding: 1px 5px; border-radius: 4px; font-size: 0.9em; }
.bubble-text :deep(.code-block) { background: #f1f5f9; padding: 10px; border-radius: 8px; overflow: auto; }
.bubble-text :deep(.md-h2), .bubble-text :deep(.md-h3) { font-weight: 700; display: inline; }
.bubble-tools { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; margin-top: 10px; padding-top: 8px; border-top: 1px dashed #e5ebf4; }
.message.user .bubble-tools { display: none; }
.tiny { font-size: 11px; }
.rate { margin-left: auto; display: inline-flex; gap: 4px; }
.rate button { border: 0; background: transparent; color: #9aa7bd; font-size: 11px; padding: 2px 4px; border-radius: 5px; }
.rate button:hover, .rate button.active { background: var(--brand-soft); color: var(--brand); }
@media (max-width: 680px) {
  .message { gap: 8px; }
  .avatar { width: 30px; height: 30px; flex-basis: 30px; font-size: 12px; }
  .bubble { padding: 12px 13px; }
  .bubble-wrap { max-width: calc(100vw - 80px); }
}
</style>
