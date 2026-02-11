<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const err = ref('')

const form = reactive({
  username: '',
  password: '',
})

async function onSubmit() {
  err.value = ''
  try {
    await auth.register(form.username, form.password)
    router.push('/home')
  } catch (e) {
    err.value = e?.message || String(e)
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-title">量化光学气体成像平台</div>
      <div class="auth-subtitle">Quantitative Optical Gas Imaging Platform · 注册</div>

      <el-form label-position="top" @submit.prevent>
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码（至少 6 位）">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-button type="primary" style="width: 100%" @click="onSubmit">注册并登录</el-button>
      </el-form>

      <div class="auth-hint">
        已有账号？
        <router-link to="/login">去登录</router-link>
      </div>

      <el-alert v-if="err" :title="err" type="error" show-icon :closable="false" />
    </div>
  </div>
</template>

