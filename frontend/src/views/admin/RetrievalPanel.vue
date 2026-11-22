<template>
  <div class="retrieval">
    <div class="page-head">
      <div>
        <div class="eyebrow">RETRIEVAL LAB</div>
        <h1>检索调试</h1>
        <p>直接观察稠密向量 + BM25 的 RRF 融合结果，不经过生成模型。</p>
      </div>
    </div>

    <section class="panel form-panel">
      <div class="field-row">
        <div class="grow">
          <label>查询语句</label>
          <input v-model="query" class="field" placeholder="例如：EUV 光刻胶的分辨率极限" @keydown.enter="run" />
        </div>
        <div class="mini-field">
          <label>top_k</label>
          <select v-model.number="topK" class="select">
            <option v-for="n in [2, 4, 6, 10, 20]" :key="n" :value="n">{{ n }}</option>
          </select>
        </div>
        <div class="mini-field">
          <label>RRF 阈值</label>
          <input v-model.number="threshold" class="field" type="number" min="0" max="1" step="0.001" />
        </div>
      </div>
      <div class="field-row lower">
        <div class="grow">
          <label>过滤表达式</label>
          <input v-model="expr" class="field mono" placeholder='category == "content"' />
        </div>
        <button class="btn btn-primary run-btn" @click="run" :disabled="loading">
          <span v-if="loading" class="spinner"></span>{{ loading ? '检索中' : '执行检索' }}
        </button>
      </div>
      <div class="hint">RRF 分数上限约为 1/100，阈值建议保持 0；调高会把结果全部过滤掉。</div>
    </section>

    <div v-if="error" class="error-line">{{ error }}</div>

    <div v-if="result" class="result-head">
      <div><strong>{{ result.hits.length }}</strong> 条结果 · {{ result.took_ms }} ms</div>
      <span class="tag brand mono">{{ result.expr || '默认过滤' }}</span>
    </div>

    <section v-if="result" class="hits">
      <article v-for="(hit, index) in result.hits" :key="hit.doc_uid + '-' + hit.chunk_index" class="panel hit">
        <div class="hit-top">
          <span class="hit-rank">{{ hit.rank }}</span>
          <div class="hit-title">
            <strong>{{ hit.title || hit.filename || '未命名' }}</strong>
            <span class="tiny muted mono">{{ hit.filename }} · 切片 {{ hit.chunk_index }}</span>
          </div>
          <span class="score-badge">RRF {{ Number(hit.score || 0).toFixed(4) }}</span>
        </div>
        <div class="hit-meta tiny muted">
          <span class="mono">{{ hit.doc_uid }}</span>
          <a v-if="hit.url" :href="hit.url" target="_blank" rel="noreferrer">打开原文</a>
        </div>
        <div class="hit-text" :class="{ expanded: expanded.has(index) }">{{ hit.text }}</div>
        <button class="expand-btn" @click="toggle(index)">{{ expanded.has(index) ? '收起全文' : '展开全文' }}</button>
      </article>
      <div v-if="!result.hits.length" class="empty panel">没有命中结果，换一个更具体的工艺词试试。</div>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { retrievalTest } from '../../api/admin'

const query = ref('EUV 光刻胶的分辨率极限')
const topK = ref(4)
const threshold = ref(0)
const expr = ref('category == "content"')
const loading = ref(false)
const error = ref('')
const result = ref(null)
const expanded = reactive(new Set())

function toggle(index) {
  if (expanded.has(index)) expanded.delete(index)
  else expanded.add(index)
}

async function run() {
  if (!query.value.trim() || loading.value) return
  loading.value = true
  error.value = ''
  try {
    result.value = await retrievalTest({
      query: query.value.trim(), top_k: topK.value, score_threshold: threshold.value, expr: expr.value || null,
    })
  } catch (e) {
    error.value = e.message
    result.value = null
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page-head { margin-bottom: 18px; }
.eyebrow { font-size: 9px; letter-spacing: 1.5px; color: var(--brand); font-weight: 800; }
h1 { margin: 5px 0 4px; font-size: 27px; letter-spacing: -0.5px; }
.page-head p { margin: 0; color: var(--muted); font-size: 12px; }
.form-panel { padding: 18px; }
.field-row { display: flex; gap: 12px; align-items: flex-end; }
.field-row.lower { margin-top: 12px; }
label { display: block; font-size: 10px; font-weight: 700; color: var(--muted); margin-bottom: 5px; }
.grow { flex: 1; min-width: 0; }
.mini-field { width: 100px; flex: 0 0 100px; }
.run-btn { height: 39px; min-width: 110px; justify-content: center; }
.hint { font-size: 10px; color: #9aa7bd; margin-top: 10px; }
.error-line { background: var(--danger-soft); color: var(--danger); border: 1px solid #f3c7c7; border-radius: 9px; padding: 9px 11px; font-size: 12px; margin: 12px 0; }
.result-head { display: flex; align-items: center; justify-content: space-between; margin: 18px 2px 9px; font-size: 13px; }
.hits { display: grid; gap: 10px; }
.hit { padding: 15px; }
.hit-top { display: flex; align-items: flex-start; gap: 10px; }
.hit-rank { flex: 0 0 25px; height: 25px; border-radius: 7px; background: #0b1324; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700; }
.hit-title { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.hit-title strong { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.score-badge { flex: 0 0 auto; font-size: 10px; color: var(--brand); background: var(--brand-soft); border-radius: 999px; padding: 3px 8px; font-family: "Cascadia Code", Consolas, monospace; }
.hit-meta { display: flex; gap: 16px; margin: 5px 0 7px 35px; }
.hit-text { font-size: 12px; line-height: 1.7; color: #4b5b72; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; white-space: pre-wrap; }
.hit-text.expanded { display: block; }
.expand-btn { border: 0; background: transparent; color: var(--brand); font-size: 10px; padding: 3px 0 0 35px; }
@media (max-width: 760px) { .field-row { flex-wrap: wrap; } .mini-field { flex: 1; width: auto; } .run-btn { width: 100%; } }
</style>
