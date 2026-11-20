<template>
  <div class="login-wrap">
    <div class="login-card">
      <div class="login-brand">
        <div class="brand-mark">芯</div>
        <div>
          <div class="brand-name">芯知 SemiKB</div>
          <div class="brand-sub">知识库管理台</div>
        </div>
      </div>
      <h2>登录管理台</h2>
      <p class="muted">管理文档、入库任务、检索调试与问答质量。</p>
      <form @submit.prevent="submit">
        <label>用户名</label>
        <input v-model="username" class="field" autocomplete="username" placeholder="admin" />
        <label>密码</label>
        <input v-model="password" class="field" type="password" autocomplete="current-password" placeholder="请输入密码" />
        <div v-if="error" class="login-error">{{ error }}</div>
        <button class="btn btn-primary login-btn" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          <span>{{ loading ? '登录中' : '进入管理台' }}</span>
        </button>
      </form>
      <div class="login-hint">开发环境默认账号 admin / 123456</div>
    </div>
    <div class="login-side">
      <div class="dot-grid"></div>
      <div class="login-quote">“把每一份工艺文档，变成可以追问的知识。”</div>
      <div class="login-tags"><span>RAG</span><span>Milvus 3.0.2</span><span>可追溯引用</span></div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useAdminStore } from '../../stores/admin'

const store = useAdminStore()
const username = ref('admin')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  if (loading.value) return
  error.value = ''
  loading.value = true
  try {
    await store.login(username.value.trim(), password.value)
  } catch (e) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap { min-height: 100vh; display: grid; grid-template-columns: 1fr 1fr; background: #f4f6fb; }
.login-card { width: min(430px, 90vw); margin: auto; background: #fff; border: 1px solid var(--line); border-radius: 22px; padding: 32px; box-shadow: 0 24px 60px rgba(14, 27, 51, 0.12); }
.login-brand { display: flex; gap: 10px; align-items: center; margin-bottom: 26px; }
.brand-mark { width: 38px; height: 38px; border-radius: 12px; background: linear-gradient(145deg, #0b1324, #1d4f63); color: #c8fbff; display: flex; align-items: center; justify-content: center; font-weight: 800; }
.brand-name { font-weight: 800; }
.brand-sub { font-size: 11px; color: var(--muted); margin-top: 2px; }
h2 { margin: 0 0 6px; font-size: 23px; }
p { margin: 0 0 22px; font-size: 12px; }
label { display: block; font-size: 12px; color: var(--ink-3); font-weight: 600; margin: 12px 0 6px; }
.login-btn { width: 100%; justify-content: center; margin-top: 20px; height: 42px; }
.login-error { background: var(--danger-soft); color: var(--danger); font-size: 12px; padding: 9px 11px; border-radius: 8px; margin-top: 12px; }
.login-hint { text-align: center; color: var(--muted); font-size: 11px; margin-top: 16px; }
.login-side { background: linear-gradient(150deg, #0b1324, #12344a 60%, #0f766e 130%); color: #fff; padding: 44px; display: flex; flex-direction: column; justify-content: flex-end; position: relative; overflow: hidden; }
.dot-grid { position: absolute; inset: 0; background-image: radial-gradient(rgba(125, 211, 252, 0.22) 1px, transparent 1px); background-size: 26px 26px; mask-image: linear-gradient(to bottom, black, transparent 85%); }
.login-quote { position: relative; font-size: 26px; line-height: 1.55; font-weight: 700; max-width: 520px; letter-spacing: 0.3px; }
.login-tags { display: flex; gap: 8px; margin-top: 20px; }
.login-tags span { font-size: 11px; border: 1px solid rgba(153, 246, 228, 0.25); border-radius: 999px; padding: 4px 9px; color: #c8fff9; }
@media (max-width: 820px) { .login-wrap { grid-template-columns: 1fr; } .login-side { display: none; } }
</style>
