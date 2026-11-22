<template>
  <div class="pagination-bar">
    <div class="page-summary">
      <span>共 <strong>{{ total }}</strong> {{ unit }}</span>
      <span class="summary-dot">·</span>
      <span>每页 {{ size }} {{ unit }}</span>
      <span class="summary-dot">·</span>
      <span>第 <strong>{{ page }}</strong> / {{ pageCount }} 页</span>
    </div>

    <div v-if="pageCount > 1" class="page-controls">
      <button class="page-btn text-btn" :disabled="page <= 1" title="第一页" @click="go(1)">首页</button>
      <button class="page-btn arrow" :disabled="page <= 1" title="上一页" @click="go(page - 1)">‹</button>

      <template v-for="token in pageTokens" :key="token.key">
        <span v-if="token.ellipsis" class="page-ellipsis">…</span>
        <button
          v-else
          class="page-btn number"
          :class="{ active: token.page === page }"
          :aria-current="token.page === page ? 'page' : undefined"
          @click="go(token.page)"
        >
          {{ token.page }}
        </button>
      </template>

      <button class="page-btn arrow" :disabled="page >= pageCount" title="下一页" @click="go(page + 1)">›</button>
      <button class="page-btn text-btn" :disabled="page >= pageCount" title="最后一页" @click="go(pageCount)">末页</button>

      <div class="page-jump">
        <span>跳至</span>
        <input
          v-model="jumpText"
          class="jump-input"
          inputmode="numeric"
          maxlength="6"
          aria-label="跳转页码"
          @keydown.enter.prevent="submitJump"
        />
        <span>页</span>
        <button class="page-btn text-btn jump-btn" @click="submitJump">跳转</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  page: { type: Number, default: 1 },
  size: { type: Number, default: 20 },
  total: { type: Number, default: 0 },
  unit: { type: String, default: '条' },
})
const emit = defineEmits(['change'])
const jumpText = ref(String(props.page || 1))

const pageCount = computed(() => Math.max(1, Math.ceil((Number(props.total) || 0) / Math.max(1, Number(props.size) || 20))))
const currentPage = computed(() => Math.min(pageCount.value, Math.max(1, Number(props.page) || 1)))

const pageTokens = computed(() => {
  const last = pageCount.value
  const current = currentPage.value
  const pages = new Set([1, last, current])
  for (let offset = 1; offset <= 2; offset += 1) {
    if (current - offset >= 1) pages.add(current - offset)
    if (current + offset <= last) pages.add(current + offset)
  }
  if (current <= 3) {
    for (let item = 2; item <= Math.min(5, last); item += 1) pages.add(item)
  }
  if (current >= last - 2) {
    for (let item = Math.max(2, last - 4); item <= last - 1; item += 1) pages.add(item)
  }
  const sorted = [...pages].filter((item) => item >= 1 && item <= last).sort((a, b) => a - b)
  const tokens = []
  sorted.forEach((item, index) => {
    const previous = sorted[index - 1]
    if (index > 0 && item - previous > 1) {
      tokens.push({ key: `ellipsis-${previous}-${item}`, ellipsis: true })
    }
    tokens.push({ key: `page-${item}`, page: item })
  })
  return tokens
})

watch(() => props.page, (value) => { resetJump(value) })

function resetJump(value = props.page) {
  jumpText.value = String(Math.min(pageCount.value, Math.max(1, Number(value) || 1)))
}

function go(target) {
  const page = Math.min(pageCount.value, Math.max(1, Number(target) || 1))
  if (page === currentPage.value) {
    resetJump(page)
    return
  }
  resetJump(page)
  emit('change', page)
}

function submitJump() {
  const value = Number.parseInt(String(jumpText.value).trim(), 10)
  if (!Number.isFinite(value)) {
    resetJump()
    return
  }
  go(value)
}
</script>

<style scoped>
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  flex-wrap: wrap;
  padding-top: 15px;
  border-top: 1px solid #edf1f7;
  margin-top: 2px;
}
.page-summary {
  display: flex;
  align-items: center;
  gap: 7px;
  color: var(--muted);
  font-size: 11px;
  white-space: nowrap;
}
.page-summary strong {
  color: var(--ink);
  font-family: "Cascadia Code", Consolas, monospace;
  font-weight: 700;
}
.summary-dot { color: #c3cedd; }
.page-controls {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}
.page-btn {
  height: 29px;
  min-width: 29px;
  padding: 0 8px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: #fff;
  color: var(--ink-2);
  font-size: 11px;
  font-weight: 600;
  transition: 0.16s ease;
}
.page-btn:hover:not(:disabled):not(.active) {
  border-color: #b9d8d3;
  background: #f3fbf9;
  color: var(--brand);
}
.page-btn:disabled {
  cursor: not-allowed;
  opacity: 0.38;
}
.page-btn.arrow {
  padding: 0;
  font-size: 18px;
  font-family: Arial, sans-serif;
  line-height: 1;
}
.page-btn.number.active {
  border-color: var(--brand);
  background: var(--brand);
  color: #fff;
  box-shadow: 0 5px 12px rgba(15, 118, 110, 0.18);
}
.page-btn.text-btn {
  padding: 0 9px;
  font-size: 10px;
  font-weight: 700;
}
.page-ellipsis {
  min-width: 18px;
  text-align: center;
  color: #9aa8bb;
  font-size: 11px;
}
.page-jump {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-left: 6px;
  padding-left: 10px;
  border-left: 1px dashed #dfe7f1;
  color: var(--muted);
  font-size: 10px;
  white-space: nowrap;
}
.jump-input {
  width: 42px;
  height: 29px;
  border: 1px solid var(--line);
  border-radius: 8px;
  text-align: center;
  color: var(--ink);
  font-size: 11px;
  font-family: "Cascadia Code", Consolas, monospace;
  outline: none;
  background: #fff;
}
.jump-input:focus {
  border-color: var(--brand-2);
  box-shadow: 0 0 0 3px rgba(8, 145, 178, 0.1);
}
.jump-btn {
  border-color: #b9d8d3;
  color: var(--brand);
  background: #f3fbf9;
}
@media (max-width: 900px) {
  .pagination-bar { align-items: flex-start; flex-direction: column; }
  .page-controls { width: 100%; }
  .page-jump { margin-left: 0; padding-left: 0; border-left: 0; }
}
</style>
