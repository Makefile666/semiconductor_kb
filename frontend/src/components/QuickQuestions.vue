<template>
  <div class="quick">
    <button v-for="item in items" :key="item" class="quick-item" @click="$emit('pick', item)">
      <span class="quick-dot"></span>
      <span>{{ item }}</span>
    </button>
  </div>
</template>

<script setup>
defineProps({ items: { type: Array, default: () => [] } })
defineEmits(['pick'])
</script>

<style scoped>
.quick { display: grid; gap: 8px; }
.quick-item {
  display: flex; align-items: center; gap: 9px; text-align: left; border: 1px solid #e1e8f2;
  background: #fff; color: var(--ink-2); border-radius: 11px; padding: 10px 11px;
  font-size: 12.5px; line-height: 1.5; transition: 0.18s ease;
}
.quick-item:hover { border-color: #9edbd4; background: #f4fdfb; transform: translateX(2px); }
.quick-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--brand-2); flex: 0 0 6px; }
</style>
