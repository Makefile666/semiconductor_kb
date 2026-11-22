<template>
  <div v-if="sources?.length" class="citations">
    <button class="citations-head" @click="open = !open">
      <span class="cite-icon">引</span>
      <span>{{ sources.length }} 条引用</span>
      <span class="muted small">{{ open ? '收起' : '展开' }}</span>
      <span class="chev" :class="{ up: open }">⌄</span>
    </button>
    <div v-if="open" class="citation-list">
      <div v-for="(source, index) in sources" :key="`${source.doc_uid}-${source.chunk_index}-${index}`" class="citation">
        <div class="cite-rank">{{ source.rank || index + 1 }}</div>
        <div class="cite-body">
          <div class="cite-title">
            <span class="ellipsis">{{ source.title || source.filename || '未命名文档' }}</span>
            <a v-if="sourceHref(source)" :href="sourceHref(source)" target="_blank" rel="noreferrer" class="small">原文</a>
          </div>
          <div class="cite-meta small muted">
            <span v-if="source.filename" class="mono">{{ source.filename }}</span>
            <span v-if="source.chunk_index !== null && source.chunk_index !== undefined">切片 {{ source.chunk_index }}</span>
            <span v-if="source.score" class="score">RRF {{ Number(source.score).toFixed(4) }}</span>
          </div>
          <div v-if="source.snippet" class="cite-snippet">{{ source.snippet }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({ sources: { type: Array, default: () => [] } })
const open = ref(false)

function sourceHref(source) {
  if (source.doc_uid) return `/document/${encodeURIComponent(source.doc_uid)}`
  const url = String(source.url || '').trim()
  return /^https?:\/\//i.test(url) ? url : ''
}
</script>

<style scoped>
.citations { margin-top: 12px; border-top: 1px dashed #dbe4f0; padding-top: 10px; }
.citations-head {
  display: flex; align-items: center; gap: 8px; border: 0; background: transparent;
  padding: 0; color: var(--ink-3); font-size: 12px; font-weight: 600;
}
.cite-icon {
  width: 20px; height: 20px; display: inline-flex; align-items: center; justify-content: center;
  border-radius: 6px; background: var(--brand-soft); color: var(--brand); font-size: 11px;
}
.chev { color: var(--muted); transition: 0.2s; }
.chev.up { transform: rotate(180deg); }
.citation-list { display: grid; gap: 8px; margin-top: 10px; }
.citation {
  display: flex; gap: 10px; padding: 10px; background: #f8fafc;
  border: 1px solid #e8edf5; border-radius: 10px;
}
.cite-rank {
  flex: 0 0 24px; height: 24px; border-radius: 7px; background: #0b1324; color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 700;
}
.cite-body { min-width: 0; flex: 1; }
.cite-title { display: flex; gap: 8px; align-items: center; font-size: 13px; font-weight: 600; }
.cite-meta { display: flex; gap: 12px; margin-top: 2px; flex-wrap: wrap; }
.score { color: var(--brand); font-family: "Cascadia Code", Consolas, monospace; }
.cite-snippet { margin-top: 5px; font-size: 12px; line-height: 1.65; color: #5d6b82; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
</style>
