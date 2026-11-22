<template>
  <section class="session-panel">
    <div class="panel-head">
      <div class="panel-title">历史对话</div>
      <span class="panel-count">{{ total }}</span>
    </div>

    <div v-if="loading" class="panel-note">正在读取历史会话...</div>
    <div v-else-if="!sessions.length" class="panel-note">
      还没有历史对话。发出首条回答后，这里会生成对话编号。
    </div>
    <div v-else class="session-list">
      <button
        v-for="item in sessions"
        :key="item.session_id"
        class="session-item"
        :class="{ active: item.session_id === currentSessionId }"
        :disabled="busy"
        :aria-label="`打开对话 ${item.conversation_id}`"
        @click="$emit('select', item.session_id)"
      >
        <div class="session-item-head">
          <span class="conversation-id">对话 #{{ item.conversation_id }}</span>
          <span class="session-state">
            <i :class="item.status"></i>
            {{ item.status === 'active' ? '进行中' : '已结束' }}
          </span>
        </div>
        <div class="session-item-title">{{ item.title || '未命名对话' }}</div>
        <div class="session-item-foot">
          <span>{{ item.turn_count }} 轮</span>
          <span>{{ formatTime(item.last_active_at) }}</span>
        </div>
      </button>
    </div>
  </section>
</template>

<script setup>
defineProps({
  sessions: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
  currentSessionId: { type: Number, default: null },
  loading: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
})
defineEmits(['select'])

function formatTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const now = new Date()
  const sameDay = date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate()
  if (sameDay) {
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
  }
  return `${date.getMonth() + 1}/${date.getDate()}`
}
</script>

<style scoped>
.session-panel {
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 16px;
  padding: 15px 14px 13px;
  box-shadow: 0 7px 24px rgba(14, 27, 51, 0.045);
}
.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--ink-2);
  font-size: 12px;
  font-weight: 700;
}
.panel-title::before {
  content: "";
  width: 3px;
  height: 12px;
  border-radius: 2px;
  background: var(--brand-2);
}
.panel-count {
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: #f1f7f6;
  color: var(--brand);
  font-size: 10px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.panel-note {
  padding: 12px 2px 4px;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.7;
}
.session-list {
  max-height: 228px;
  margin-top: 10px;
  padding-right: 2px;
  display: grid;
  gap: 7px;
  overflow-y: auto;
  scrollbar-width: thin;
}
.session-item {
  width: 100%;
  padding: 9px 10px;
  border: 1px solid #e6edf6;
  border-radius: 11px;
  background: #fbfdff;
  text-align: left;
  transition: 0.16s ease;
}
.session-item:hover:not(:disabled) {
  border-color: #b9d8d3;
  background: #f5fcfa;
  transform: translateY(-1px);
}
.session-item.active {
  border-color: var(--brand);
  background: var(--brand-soft);
  box-shadow: 0 5px 14px rgba(15, 118, 110, 0.1);
}
.session-item:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.session-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.conversation-id {
  color: var(--brand);
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.2px;
}
.session-state {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--muted);
  font-size: 9px;
  white-space: nowrap;
}
.session-state i {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #94a3b8;
}
.session-state i.active {
  background: var(--success);
  box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.08);
}
.session-item-title {
  margin-top: 5px;
  overflow: hidden;
  color: var(--ink);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.5;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.session-item-foot {
  margin-top: 5px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--muted);
  font-size: 9px;
}
@media (max-width: 980px) {
  .session-list { max-height: 190px; }
}
</style>
