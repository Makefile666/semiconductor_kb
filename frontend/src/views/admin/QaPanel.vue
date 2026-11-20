<template>
  <div class="qa">
    <div class="page-head">
      <div>
        <div class="eyebrow">RAG PLAYGROUND</div>
        <h1>问答链路测试</h1>
        <p>走完整 LangGraph 链路：路由、检索、评分、生成、校验与改写。</p>
      </div>
    </div>

    <section class="panel form-panel">
      <label>问题</label>
      <textarea v-model="question" class="textarea" rows="3" placeholder="输入一个半导体工艺问题，例如：GAAFET 相比 FinFET 有哪些优势"></textarea>
      <div class="form-bottom">
        <label class="switch"><input v-model="debug" type="checkbox" /><span>返回节点细节</span></label>
        <div class="prompt-row">
          <button v-for="item in presets" :key="item" class="preset" @click="question = item">{{ item }}</button>
        </div>
        <button class="btn btn-primary" @click="run" :disabled="loading">
          <span v-if="loading" class="spinner"></span>{{ loading ? '执行中' : '运行链路' }}
        </button>
      </div>
      <div v-if="error" class="error-line">{{ error }}</div>
    </section>

    <section v-if="result" class="panel answer-panel">
      <div class="answer-head">
        <div class="answer-label">回答</div>
        <div class="answer-tags">
          <span class="tag" :class="result.verified ? 'green' : 'amber'">{{ result.route === 'direct' ? '无需校验' : result.verified ? '已校验' : '未校验' }}</span>
          <span class="tag blue">{{ routeLabel(result.route) }}</span>
          <span class="tag">{{ result.source }}</span>
          <span class="tiny muted">{{ result.latency_ms }} ms</span>
        </div>
      </div>
      <div class="answer-text">{{ result.answer }}</div>
      <CitationList :sources="result.sources" />
      <TraceTimeline :trace="result.trace" :nodes="result.trace?.nodes || []" />
      <div class="raw-json">
        <details><summary>查看原始结果</summary><pre>{{ JSON.stringify(result, null, 2) }}</pre></details>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { qaTest } from '../../api/admin'
import CitationList from '../../components/CitationList.vue'
import TraceTimeline from '../../components/TraceTimeline.vue'

const question = ref('GAAFET 相比 FinFET 有哪些优势')
const debug = ref(false)
const loading = ref(false)
const error = ref('')
const result = ref(null)
const presets = ['EUV 光刻胶的分辨率极限如何突破', '3D NAND 堆叠工艺的主要挑战', 'CMP 在先进制程中起什么作用']
function routeLabel(value) {
  return { vectorstore: '本地知识库', web_search: '联网兜底', direct: '直接回答' }[value] || value || '未知'
}

async function run() {
  if (!question.value.trim() || loading.value) return
  loading.value = true
  error.value = ''
  try {
    result.value = await qaTest(question.value.trim(), debug.value)
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
label { display: block; font-size: 10px; font-weight: 700; color: var(--muted); margin-bottom: 6px; }
.form-bottom { display: flex; align-items: center; gap: 12px; margin-top: 11px; flex-wrap: wrap; }
.switch { display: flex; align-items: center; gap: 6px; margin: 0; }
.switch input { accent-color: var(--brand); }
.prompt-row { display: flex; gap: 5px; flex-wrap: wrap; flex: 1; }
.preset { border: 1px solid #dce6f1; background: #fbfdff; color: var(--ink-3); border-radius: 7px; padding: 5px 8px; font-size: 10px; }
.preset:hover { border-color: #9edbd4; color: var(--brand); }
.error-line { background: var(--danger-soft); color: var(--danger); border: 1px solid #f3c7c7; border-radius: 9px; padding: 9px 11px; font-size: 12px; margin-top: 10px; }
.answer-panel { margin-top: 16px; padding: 20px; }
.answer-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding-bottom: 12px; border-bottom: 1px dashed #e5ebf4; }
.answer-label { font-size: 12px; font-weight: 800; color: var(--brand); }
.answer-tags { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.answer-text { margin-top: 14px; font-size: 14px; line-height: 1.85; white-space: pre-wrap; }
.raw-json { margin-top: 14px; border-top: 1px dashed #e5ebf4; padding-top: 10px; }
.raw-json summary { font-size: 11px; color: var(--muted); cursor: pointer; }
.raw-json pre { background: #f8fafc; border-radius: 8px; padding: 10px; font-size: 10px; overflow: auto; max-height: 300px; }
</style>
