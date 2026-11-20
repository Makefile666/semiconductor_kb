<template>
  <div class="chat-shell">
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark"><span>芯</span></div>
        <div>
          <div class="brand-name">{{ store.brand.name }}</div>
          <div class="brand-slogan">{{ store.brand.slogan }}</div>
        </div>
      </div>
      <div class="top-actions">
        <span class="status-dot" :class="statusKey"></span>
        <span class="status-text">{{ statusLabel }}</span>
        <router-link class="admin-link" to="/admin">管理台 <span>↗</span></router-link>
      </div>
    </header>

    <main class="chat-main">
      <aside class="side">
        <div class="side-card hero">
          <div class="eyebrow">SEMICONDUCTOR KNOWLEDGE</div>
          <h2>把工艺文档，变成可以追问的知识。</h2>
          <p>覆盖材料、光刻、刻蚀、薄膜、封装与测试。回答会标注引用文档与切片。</p>
          <div class="hero-chips">
            <span>本地 RAG</span><span>BM25 + 向量</span><span>可追溯</span>
          </div>
        </div>

        <SessionList
          :sessions="store.sessions"
          :total="store.sessionsTotal"
          :current-session-id="store.session?.id || null"
          :loading="store.sessionsLoading"
          :busy="store.busy"
          @select="switchSession"
        />

        <div class="side-block session-card">
          <div class="side-title">当前会话</div>
          <div class="session-row"><span>会话</span><strong>#{{ store.session?.id || '—' }}</strong></div>
          <div class="session-row"><span>轮次</span><strong>{{ store.session?.turn_count || 0 }}</strong></div>
          <div class="session-row"><span>状态</span><span class="tag" :class="store.session?.status === 'active' ? 'green' : 'amber'">{{ store.session?.status === 'active' ? '进行中' : '已关闭' }}</span></div>
          <button class="btn btn-sm new-session" @click="newSession">新建会话</button>
        </div>

        <div class="side-block">
          <div class="side-title">可以这样问</div>
          <QuickQuestions :items="store.suggestions" @pick="pick" />
        </div>

        <div class="side-foot">
          <span class="tiny muted">RAG · 检索增强生成</span>
          <span class="tiny muted">回答请以原文为准</span>
        </div>
      </aside>

      <div class="mobile-session-wrap">
        <SessionList
          :sessions="store.sessions"
          :total="store.sessionsTotal"
          :current-session-id="store.session?.id || null"
          :loading="store.sessionsLoading"
          :busy="store.busy"
          @select="switchSession"
        />
      </div>

      <section class="conversation panel">
        <div class="conversation-head">
          <div>
            <div class="conv-title">知识问答</div>
            <div class="conv-sub">半导体工艺与芯片制造文档库</div>
          </div>
          <div class="conv-actions">
            <span v-if="store.session?.status === 'active'" class="tag brand">会话进行中</span>
            <span v-else class="tag amber">会话已结束</span>
            <button class="btn btn-sm" @click="closeSession" v-if="canChat">结束会话</button>
            <button class="btn btn-sm" @click="newSession" v-else>新建会话</button>
          </div>
        </div>

        <div ref="scroller" class="messages">
          <MessageBubble v-for="message in store.messages" :key="message.id" :message="message" @rate="onRate" />

          <div v-if="store.busy" class="stream-block">
            <div class="avatar bot">芯</div>
            <div class="stream-wrap">
              <div class="stream-bubble">
                <div v-if="store.streamingText" class="stream-text" v-html="renderedStream"></div>
                <div v-else class="thinking">
                  <span class="thinking-dots"><i></i><i></i><i></i></span>
                  <span>{{ activeLabel }}</span>
                </div>
                <span v-if="store.streamingText" class="cursor"></span>
              </div>
              <TraceTimeline v-if="store.liveNodes.length" :nodes="store.liveNodes" :live="true" />
            </div>
          </div>

          <div v-if="!store.messages.length && !store.busy" class="empty">
            <div class="empty-mark">芯</div>
            <strong>从一个具体的工艺问题开始</strong>
            <span>例如：EUV 光刻胶的分辨率极限如何突破</span>
          </div>
        </div>

        <div class="composer-wrap">
          <div v-if="store.error" class="error-bar">
            <span>{{ store.error }}</span>
            <button @click="store.error = ''">×</button>
          </div>
          <div class="composer">
            <textarea
              v-model="draft"
              class="composer-input"
              :maxlength="store.maxQuestionChars"
              :disabled="!canChat"
              :placeholder="canChat ? '输入你的问题，Enter 发送，Shift + Enter 换行' : '历史会话已结束，点击新建会话继续提问'"
              rows="1"
              @keydown.enter.exact.prevent="submit"
              @input="autoGrow"
              ref="input"
            ></textarea>
            <div class="composer-right">
              <span class="tiny muted">{{ draft.length }}/{{ store.maxQuestionChars }}</span>
              <button class="send-btn" :disabled="!canChat || store.busy || !draft.trim()" @click="submit">
                <span v-if="store.busy" class="spinner"></span>
                <span v-else>发送</span>
              </button>
            </div>
          </div>
          <div class="composer-hint">
            <span v-if="canChat">需要查资料的问题会检索知识库并标注引用。</span>
            <span v-else>历史会话只读。新建会话后可继续提问。</span>
            <span v-if="store.status === 'offline'" class="offline-tip" @click="store.connect()">重新连接</span>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useChatStore } from '../stores/chat'
import MessageBubble from '../components/MessageBubble.vue'
import QuickQuestions from '../components/QuickQuestions.vue'
import SessionList from '../components/SessionList.vue'
import TraceTimeline from '../components/TraceTimeline.vue'

const store = useChatStore()
const draft = ref('')
const scroller = ref(null)
const input = ref(null)

const statusMap = {
  idle: ['在线', 'green'],
  connecting: ['连接中', 'amber'],
  thinking: ['检索中', 'amber'],
  streaming: ['生成中', 'blue'],
  offline: ['离线', 'red'],
  closed: ['已关闭', 'gray'],
}
const statusLabel = computed(() => statusMap[store.status]?.[0] || store.status)
const statusKey = computed(() => statusMap[store.status]?.[1] || 'gray')
const canChat = computed(() => store.session?.status === 'active')
const nodeLabels = {
  route_question: '正在判断问题走向',
  retrieve: '正在检索文档库',
  grade_documents: '正在筛选相关文档',
  generate: '正在组织回答',
  grade_generation: '正在校验回答',
  transform_query: '正在改写检索问题',
  web_search: '正在联网补充资料',
}
const activeLabel = computed(() => nodeLabels[store.activeNode] || '正在检索与生成')

function escapeHtml(text) {
  return String(text || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}
const renderedStream = computed(() => escapeHtml(store.streamingText).replace(/\[(\d+)\]/g, '<span class="cite-ref">[$1]</span>'))

function scrollBottom() {
  nextTick(() => {
    if (scroller.value) scroller.value.scrollTop = scroller.value.scrollHeight
  })
}
watch(() => [store.messages.length, store.streamingText, store.busy], scrollBottom, { deep: false })

function autoGrow() {
  const el = input.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(150, el.scrollHeight)}px`
}

async function submit() {
  const text = draft.value.trim()
  if (store.busy || !text) return
  try {
    if (!canChat.value) await store.newSession()
    draft.value = ''
    autoGrow()
    await store.send(text)
    scrollBottom()
  } catch (e) {
    store.error = e.message || '新建会话失败'
  }
}

function pick(text) {
  draft.value = text
  submit()
}

async function switchSession(sessionId) {
  if (store.busy) return
  await store.selectSession(sessionId)
  draft.value = ''
  autoGrow()
  scrollBottom()
}

async function newSession() {
  await store.newSession()
  draft.value = ''
  autoGrow()
  scrollBottom()
}

async function closeSession() {
  await store.close()
}

function onRate(message, rating) {
  store.rate(message, rating)
}

onMounted(async () => {
  await store.init()
  scrollBottom()
})
onBeforeUnmount(() => store.closeSocket())
</script>

<style scoped>
.chat-shell { min-height: 100vh; background: radial-gradient(circle at 15% 0%, #e9f7f5 0, transparent 36%), radial-gradient(circle at 85% 15%, #eef4ff 0, transparent 34%), var(--paper); }
.topbar { height: 72px; display: flex; align-items: center; justify-content: space-between; padding: 0 28px; border-bottom: 1px solid rgba(223, 229, 240, 0.9); background: rgba(255, 255, 255, 0.74); backdrop-filter: blur(14px); position: sticky; top: 0; z-index: 10; }
.brand { display: flex; align-items: center; gap: 11px; }
.brand-mark { width: 38px; height: 38px; border-radius: 12px; background: linear-gradient(145deg, #0b1324, #1d4f63); color: #c8fbff; display: flex; align-items: center; justify-content: center; font-weight: 800; box-shadow: 0 8px 18px rgba(11, 19, 36, 0.22); }
.brand-name { font-weight: 800; letter-spacing: 0.2px; font-size: 16px; }
.brand-slogan { font-size: 11px; color: var(--muted); margin-top: 1px; }
.top-actions { display: flex; align-items: center; gap: 9px; }
.status-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--success); box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.1); }
.status-dot.amber { background: var(--accent); box-shadow: 0 0 0 4px rgba(245, 158, 11, 0.1); }
.status-dot.blue { background: var(--brand-2); box-shadow: 0 0 0 4px rgba(8, 145, 178, 0.1); }
.status-dot.red { background: var(--danger); box-shadow: 0 0 0 4px rgba(220, 38, 38, 0.1); }
.status-dot.gray { background: #94a3b8; box-shadow: 0 0 0 4px rgba(148, 163, 184, 0.12); }
.status-text { font-size: 12px; color: var(--ink-3); }
.admin-link { margin-left: 9px; padding: 8px 12px; border: 1px solid var(--line); border-radius: 9px; color: var(--ink-2); font-size: 12px; font-weight: 600; background: #fff; }
.admin-link:hover { text-decoration: none; border-color: #a7dcd6; color: var(--brand); }

.chat-main { max-width: 1320px; margin: 0 auto; padding: 24px 28px 28px; display: grid; grid-template-columns: 268px minmax(0, 1fr); gap: 20px; align-items: start; }
.side { display: grid; gap: 16px; position: sticky; top: 96px; max-height: calc(100vh - 120px); overflow-y: auto; padding-right: 4px; scrollbar-width: thin; }
.side-card { border-radius: 18px; padding: 20px; color: #effcff; background: linear-gradient(155deg, #0b1324 0%, #12344a 62%, #0f766e 130%); box-shadow: 0 20px 45px rgba(11, 19, 36, 0.18); overflow: hidden; position: relative; }
.side-card::after { content: ""; position: absolute; width: 140px; height: 140px; border: 1px solid rgba(125, 211, 252, 0.22); border-radius: 50%; right: -55px; bottom: -70px; }
.eyebrow { font-size: 9px; letter-spacing: 1.4px; color: #86e5dd; font-weight: 700; }
.hero h2 { font-size: 19px; line-height: 1.45; margin: 11px 0 9px; letter-spacing: 0.2px; }
.hero p { margin: 0; color: #b9cad9; font-size: 12px; line-height: 1.7; }
.hero-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; }
.hero-chips span { font-size: 10px; padding: 3px 7px; border: 1px solid rgba(153, 246, 228, 0.25); border-radius: 999px; color: #c8fff9; }
.side-block { background: #fff; border: 1px solid var(--line); border-radius: 16px; padding: 16px; box-shadow: 0 7px 24px rgba(14, 27, 51, 0.045); }
.side-title { font-size: 12px; font-weight: 700; color: var(--ink-2); margin-bottom: 11px; display: flex; align-items: center; gap: 7px; }
.side-title::before { content: ""; width: 3px; height: 12px; border-radius: 2px; background: var(--brand-2); }
.session-row { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--muted); margin-bottom: 9px; }
.session-row strong { color: var(--ink-2); font-family: "Cascadia Code", Consolas, monospace; font-size: 12px; }
.new-session { width: 100%; justify-content: center; margin-top: 4px; }
.side-foot { display: flex; justify-content: space-between; padding: 2px 3px; }

.conversation { min-height: calc(100vh - 124px); display: flex; flex-direction: column; overflow: hidden; }
.mobile-session-wrap { display: none; }
.conversation-head { padding: 17px 22px; border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; gap: 12px; background: linear-gradient(180deg, #fff, #fbfdff); }
.conv-title { font-weight: 800; font-size: 15px; }
.conv-sub { font-size: 11px; color: var(--muted); margin-top: 3px; }
.conv-actions { display: flex; align-items: center; gap: 8px; }
.messages { flex: 1; overflow-y: auto; padding: 24px 24px 8px; scroll-behavior: smooth; }
.stream-block { display: flex; gap: 12px; margin-bottom: 20px; }
.stream-wrap { min-width: 0; }
.stream-bubble { background: #fff; border: 1px solid #cfe9e6; border-radius: 3px 16px 16px 16px; padding: 14px 16px; min-width: 240px; box-shadow: 0 5px 18px rgba(14, 27, 51, 0.045); }
.stream-text { font-size: 14px; line-height: 1.8; white-space: pre-wrap; }
.stream-text :deep(.cite-ref) { color: var(--brand); font-weight: 700; font-size: 12px; }
.cursor { display: inline-block; width: 7px; height: 16px; background: var(--brand-2); border-radius: 2px; animation: blink 0.9s steps(2, start) infinite; vertical-align: -2px; margin-left: 2px; }
@keyframes blink { 50% { opacity: 0; } }
.thinking { display: flex; align-items: center; gap: 9px; color: var(--ink-3); font-size: 13px; }
.thinking-dots { display: inline-flex; gap: 3px; }
.thinking-dots i { width: 5px; height: 5px; border-radius: 50%; background: var(--brand-2); animation: pulse 1s ease-in-out infinite; }
.thinking-dots i:nth-child(2) { animation-delay: 0.16s; }
.thinking-dots i:nth-child(3) { animation-delay: 0.32s; }
@keyframes pulse { 0%, 100% { opacity: 0.35; transform: translateY(0); } 50% { opacity: 1; transform: translateY(-2px); } }

.composer-wrap { border-top: 1px solid var(--line); padding: 13px 18px 15px; background: #fff; }
.error-bar { display: flex; align-items: center; justify-content: space-between; background: #fff7ed; color: #9a3412; border: 1px solid #fed7aa; border-radius: 9px; padding: 8px 10px; font-size: 12px; margin-bottom: 9px; }
.error-bar button { border: 0; background: transparent; color: inherit; font-size: 16px; }
.composer { display: flex; gap: 12px; align-items: flex-end; border: 1px solid #dbe4f0; border-radius: 14px; padding: 7px 8px 7px 14px; background: #fbfdff; transition: 0.18s; }
.composer:focus-within { border-color: #83cfc7; box-shadow: 0 0 0 4px rgba(15, 118, 110, 0.08); background: #fff; }
.composer-input { flex: 1; border: 0; outline: none; resize: none; background: transparent; padding: 8px 0; max-height: 150px; line-height: 1.6; font-size: 14px; color: var(--ink); }
.composer-right { display: flex; align-items: center; gap: 9px; padding-bottom: 2px; }
.send-btn { border: 0; background: linear-gradient(135deg, var(--brand), var(--brand-2)); color: #fff; border-radius: 9px; min-width: 66px; height: 34px; padding: 0 13px; font-weight: 700; font-size: 12px; box-shadow: 0 7px 16px rgba(8, 145, 178, 0.2); }
.send-btn:disabled { opacity: 0.45; box-shadow: none; cursor: not-allowed; }
.composer-hint { display: flex; justify-content: space-between; gap: 10px; padding: 8px 3px 0; font-size: 11px; color: #9aa7bd; }
.offline-tip { color: var(--danger); cursor: pointer; font-weight: 600; }
.empty-mark { width: 42px; height: 42px; border-radius: 13px; background: var(--brand-soft); color: var(--brand); display: flex; align-items: center; justify-content: center; font-weight: 800; }

@media (max-width: 980px) {
  .chat-main { grid-template-columns: 1fr; padding: 16px; }
  .side { display: none; }
  .mobile-session-wrap { display: block; }
  .conversation { min-height: calc(100vh - 116px); }
}
@media (max-width: 640px) {
  .topbar { padding: 0 14px; height: 64px; }
  .brand-slogan { display: none; }
  .messages { padding: 16px 12px 4px; }
  .conversation-head { padding: 13px 14px; }
  .composer-wrap { padding: 10px 10px 12px; }
}
</style>
