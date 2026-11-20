<template>
  <div class="documents">
    <div class="page-head">
      <div>
        <div class="eyebrow">DOCUMENTS</div>
        <h1>文档管理</h1>
        <p>上传 Markdown，追踪解析、切片与入库状态。</p>
      </div>
      <button class="btn btn-primary" @click="refresh">刷新</button>
    </div>

    <section class="panel upload-panel" @dragover.prevent @drop.prevent="onDrop">
      <div class="upload-copy">
        <div class="upload-icon">↑</div>
        <div>
          <div class="upload-title">拖入 Markdown 文件，或点击上传</div>
          <div class="upload-sub">支持 .md / .markdown，单文件不超过 5 MB，一次最多 20 个。</div>
        </div>
      </div>
      <div class="upload-actions">
        <input ref="fileInput" type="file" accept=".md,.markdown" multiple hidden @change="onPick" />
        <button class="btn" @click="fileInput?.click()" :disabled="uploading">
          <span v-if="uploading" class="spinner dark"></span>{{ uploading ? '上传中' : '选择文件' }}
        </button>
      </div>
    </section>

    <div v-if="uploadResult" class="upload-result">
      <div class="result-head">
        <strong>上传结果</strong>
        <button @click="uploadResult = null">×</button>
      </div>
      <div v-if="uploadResult.accepted?.length" class="result-line ok">
        已接收 {{ uploadResult.accepted.length }} 个文件，任务 #{{ uploadResult.task_id }} 已进入队列。
      </div>
      <div v-for="item in uploadResult.rejected" :key="item.filename" class="result-line warn">
        {{ item.filename }}：{{ item.reason }}<span v-if="item.existing_doc_uid" class="muted"> · 已存在 {{ item.existing_doc_uid.slice(0, 8) }}</span>
      </div>
    </div>

    <div class="toolbar">
      <div class="toolbar-left">
        <select v-model="status" class="select filter" @change="search">
          <option value="">全部状态</option>
          <option value="ready">已就绪</option>
          <option value="pending">待处理</option>
          <option value="parsing">解析中</option>
          <option value="indexing">入库中</option>
          <option value="failed">失败</option>
        </select>
        <input v-model="keyword" class="field search" placeholder="搜索文件名或标题" @keydown.enter="search" />
        <button class="btn btn-sm" @click="search">搜索</button>
      </div>
      <div class="toolbar-right muted small">共 {{ store.documents.total }} 篇</div>
    </div>

    <section class="panel table-panel">
      <div class="table-wrap">
        <table class="data">
          <thead><tr><th>文档</th><th>状态</th><th>切片</th><th>大小</th><th>更新时间</th><th>操作</th></tr></thead>
          <tbody>
            <tr v-for="doc in store.documents.items" :key="doc.doc_uid">
              <td>
                <div class="doc-cell">
                  <div class="file-badge">MD</div>
                  <div class="doc-meta">
                    <button class="doc-name" @click="openDetail(doc)">{{ doc.title || doc.filename }}</button>
                    <span class="tiny muted mono">{{ doc.filename }}</span>
                  </div>
                </div>
              </td>
              <td><span class="tag" :class="statusClass(doc.status)">{{ statusLabel(doc.status) }}</span></td>
              <td class="mono">{{ doc.chunk_count }}</td>
              <td>{{ formatSize(doc.size_bytes) }}</td>
              <td class="small muted">{{ fmtDate(doc.updated_at) }}</td>
              <td>
                <div class="row-actions">
                  <button class="btn btn-sm" @click="openDetail(doc)">查看</button>
                  <button class="btn btn-sm" @click="reindex(doc)" :disabled="doc.status === 'parsing' || doc.status === 'indexing'">重建索引</button>
                  <button class="btn btn-sm btn-danger" @click="remove(doc)">删除</button>
                </div>
              </td>
            </tr>
            <tr v-if="!store.documents.items.length"><td colspan="6"><div class="empty small">还没有文档，先上传几篇 Markdown 试试。</div></td></tr>
          </tbody>
        </table>
      </div>
      <PaginationBar
        :page="store.documents.page"
        :size="store.documents.size"
        :total="store.documents.total"
        unit="篇"
        @change="go"
      />
    </section>

    <div v-if="detail" class="modal-mask" @click.self="detail = null">
      <div class="modal doc-modal">
        <div class="modal-head">
          <div><h3>{{ detail.title || detail.filename }}</h3><div class="tiny muted mono">{{ detail.filename }}</div></div>
          <button class="icon-close" @click="detail = null">×</button>
        </div>
        <div class="detail-meta">
          <div><span>状态</span><strong class="tag" :class="statusClass(detail.status)">{{ statusLabel(detail.status) }}</strong></div>
          <div><span>切片</span><strong>{{ detail.chunk_count }}</strong></div>
          <div><span>集合</span><strong class="mono">{{ detail.milvus_collection }}</strong></div>
          <div><span>入库时间</span><strong>{{ fmtDate(detail.indexed_at) || '—' }}</strong></div>
        </div>
        <div v-if="detail.error_msg" class="detail-error">{{ detail.error_msg }}</div>
        <div class="chunks-head">
          <strong>切片预览</strong>
          <span class="muted small">共 {{ chunkTotal }} 条</span>
        </div>
        <div v-if="detailLoading" class="empty small"><span class="spinner dark"></span>加载切片</div>
        <div v-else class="chunk-list">
          <div v-for="chunk in detailChunks" :key="chunk.chunk_index" class="chunk-item">
            <span class="chunk-index">#{{ chunk.chunk_index }}</span>
            <div><div class="chunk-title">{{ chunk.title || '无标题切片' }}</div><div class="chunk-text">{{ chunk.text }}</div></div>
          </div>
          <div v-if="!detailChunks.length" class="empty small">Milvus 里还没有这篇文档的切片。</div>
        </div>
        <div class="modal-actions">
          <button class="btn" @click="detail = null">关闭</button>
          <button class="btn btn-primary" @click="reindex(detail)">重建索引</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useAdminStore } from '../../stores/admin'
import { chunks as fetchChunks, documentDetail } from '../../api/admin'
import PaginationBar from '../../components/PaginationBar.vue'

const store = useAdminStore()
const fileInput = ref(null)
const status = ref('')
const keyword = ref('')
const uploading = ref(false)
const uploadResult = ref(null)
const detail = ref(null)
const detailChunks = ref([])
const detailLoading = ref(false)
const chunkTotal = ref(0)

const labelMap = { pending: '待处理', parsing: '解析中', indexing: '入库中', ready: '已就绪', failed: '失败', deleted: '已删除' }
const classMap = { pending: 'amber', parsing: 'blue', indexing: 'blue', ready: 'green', failed: 'red', deleted: '' }
function statusLabel(value) { return labelMap[value] || value }
function statusClass(value) { return classMap[value] || '' }
function formatSize(bytes) {
  const value = Number(bytes || 0)
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / 1024 / 1024).toFixed(1)} MB`
}
function fmtDate(value) {
  if (!value) return ''
  return String(value).replace('T', ' ').slice(0, 16)
}

async function load(params = {}) {
  await store.loadDocuments({ page: params.page || store.documents.page || 1, size: store.documents.size || 20, status: status.value, keyword: keyword.value })
}
function search() { load({ page: 1 }) }
function go(page) { load({ page }) }
function refresh() { load({ page: 1 }) }

async function doUpload(files) {
  if (!files || !files.length || uploading.value) return
  uploading.value = true
  uploadResult.value = null
  try {
    uploadResult.value = await store.uploadFiles(files)
  } catch (e) {
    uploadResult.value = { accepted: [], rejected: [{ filename: '上传失败', reason: e.message }] }
  } finally {
    uploading.value = false
    if (fileInput.value) fileInput.value.value = ''
  }
}
function onPick(event) { doUpload(event.target.files) }
function onDrop(event) { doUpload(event.dataTransfer.files) }

async function reindex(doc) {
  if (doc.status === 'parsing' || doc.status === 'indexing') return
  if (!window.confirm(`确定重建「${doc.title || doc.filename}」的索引吗？`)) return
  try { await store.reindex(doc.doc_uid) } catch (e) { store.error = e.message }
}
async function remove(doc) {
  if (!window.confirm(`确定删除「${doc.title || doc.filename}」及其向量吗？`)) return
  try { await store.removeDocument(doc.doc_uid) } catch (e) { store.error = e.message }
}
async function openDetail(doc) {
  detailLoading.value = true
  detailChunks.value = []
  try {
    detail.value = await documentDetail(doc.doc_uid)
    const data = await fetchChunks(doc.doc_uid, 50, 0)
    detailChunks.value = data.items || []
    chunkTotal.value = data.total || 0
  } catch (e) {
    store.error = e.message
  } finally {
    detailLoading.value = false
  }
}
onMounted(() => { if (!store.documents.items.length) load({ page: 1 }) })
</script>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 14px; margin-bottom: 18px; }
.eyebrow { font-size: 9px; letter-spacing: 1.5px; color: var(--brand); font-weight: 800; }
h1 { margin: 5px 0 4px; font-size: 27px; letter-spacing: -0.5px; }
.page-head p { margin: 0; color: var(--muted); font-size: 12px; }
.upload-panel { padding: 18px; display: flex; align-items: center; justify-content: space-between; gap: 16px; border-style: dashed; background: linear-gradient(135deg, #fff, #f7fdfb); }
.upload-copy { display: flex; align-items: center; gap: 13px; }
.upload-icon { width: 40px; height: 40px; border-radius: 11px; background: var(--brand-soft); color: var(--brand); display: flex; align-items: center; justify-content: center; font-size: 21px; font-weight: 700; }
.upload-title { font-size: 14px; font-weight: 700; }
.upload-sub { font-size: 11px; color: var(--muted); margin-top: 3px; }
.upload-result { margin-top: 12px; border: 1px solid #fde3b3; background: #fffbeb; border-radius: 10px; padding: 10px 12px; font-size: 12px; }
.result-head { display: flex; justify-content: space-between; margin-bottom: 5px; }
.result-head button { border: 0; background: transparent; font-size: 16px; color: inherit; }
.result-line { line-height: 1.65; }
.result-line.ok { color: var(--success); }
.result-line.warn { color: #9a3412; }
.toolbar { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin: 16px 0 11px; }
.toolbar-left { display: flex; gap: 8px; align-items: center; }
.filter { width: 130px; padding: 8px 10px; font-size: 12px; }
.search { width: 230px; padding: 8px 10px; font-size: 12px; }
.table-panel { padding: 12px 14px 14px; }
.doc-cell { display: flex; align-items: center; gap: 9px; min-width: 230px; }
.file-badge { flex: 0 0 28px; height: 30px; border-radius: 7px; background: #eff6ff; color: #1d4ed8; display: flex; align-items: center; justify-content: center; font-size: 9px; font-weight: 800; }
.doc-meta { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.doc-name { border: 0; background: transparent; padding: 0; text-align: left; font-size: 12px; font-weight: 600; color: var(--ink); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 300px; }
.doc-name:hover { color: var(--brand); }
.row-actions { display: flex; gap: 4px; }
.icon-close { border: 0; background: transparent; font-size: 22px; color: var(--muted); }
.modal-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.detail-meta { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 16px 0; padding: 12px; background: #f8fafc; border-radius: 10px; }
.detail-meta > div { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.detail-meta span { font-size: 10px; color: var(--muted); }
.detail-meta strong { font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.detail-error { background: var(--danger-soft); color: var(--danger); font-size: 12px; padding: 9px 10px; border-radius: 8px; margin-bottom: 12px; }
.chunks-head { display: flex; justify-content: space-between; align-items: baseline; border-top: 1px dashed #e5ebf4; padding-top: 14px; }
.chunk-list { margin-top: 10px; display: grid; gap: 7px; }
.chunk-item { display: flex; gap: 9px; background: #fbfdff; border: 1px solid #e8edf5; border-radius: 8px; padding: 9px; }
.chunk-index { flex: 0 0 35px; font-size: 10px; color: var(--brand); font-family: "Cascadia Code", Consolas, monospace; }
.chunk-title { font-size: 11px; font-weight: 600; }
.chunk-text { margin-top: 3px; font-size: 11px; color: #5d6b82; line-height: 1.65; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
@media (max-width: 700px) { .detail-meta { grid-template-columns: repeat(2, 1fr); } .upload-panel { flex-direction: column; align-items: flex-start; } .toolbar { flex-wrap: wrap; } .search { width: 180px; } }
</style>
