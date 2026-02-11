<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { api } from '../api/client'
import CaseView from './CaseView.vue'
import logo from '../assets/logo.png'

const router = useRouter()
const auth = useAuthStore()

const uploading = ref(false)
const lastCaseId = ref('')
const lastCaseCreatedAt = ref('')
const lastMsg = ref('')

async function logout() {
  await auth.logout()
  router.push('/login')
}

async function upload(type, file) {
  lastMsg.value = ''
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('type', type)
    if (file) {
      fd.append('file', file)
    }
    const { data } = await api.post('/api/cases', fd)
    if (!data.ok) throw new Error(data.msg || '创建 case 失败')
    lastCaseId.value = data.case_id
    lastCaseCreatedAt.value = data.created_at || ''
  } catch (e) {
    lastMsg.value = e?.message || String(e)
  } finally {
    uploading.value = false
  }
}

function pickAndUpload(type, accept) {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = accept
  input.onchange = () => {
    const file = input.files?.[0]
    if (file) upload(type, file)
  }
  input.click()
}

function goProfile() {
  router.push('/profile')
}
</script>

<template>
  <div class="page">
    <div class="topbar">
      <div class="brand">
        <img class="brand-logo" :src="logo" alt="logo" />
        <div class="brand-text">
          <div class="brand-title">量化光学气体成像平台</div>
          <div class="brand-sub">Quantitative Optical Gas Imaging Platform</div>
        </div>
      </div>
      <div class="topbar-actions">
        <div class="user" @click="goProfile">当前用户：{{ auth.user?.username }}</div>
        <el-button @click="logout">退出</el-button>
      </div>
    </div>

    <div class="card">
      <div class="card-title">上传红外视频 / 数据源</div>
      <div class="grid">
        <el-button type="primary" :loading="uploading" @click="pickAndUpload('folder', '.zip')">
          导入文件夹（zip）
        </el-button>
        <el-button type="primary" :loading="uploading" @click="pickAndUpload('mp4', '.mp4')">
          导入视频（mp4）
        </el-button>
        <el-button type="primary" :loading="uploading" @click="pickAndUpload('raw', '.raw')">
          导入视频（raw）
        </el-button>
        <el-button type="warning" :loading="uploading" @click="upload('camera')">
          打开摄像头
        </el-button>
      </div>
      <el-alert v-if="lastMsg" :title="lastMsg" type="error" show-icon :closable="false" style="margin-top: 12px" />
    </div>

    <div v-if="lastCaseId" style="margin-top: 16px">
      <div class="card" style="margin-bottom: 12px">
        <div class="card-title">当前检测任务</div>
        <div class="muted">
          Case ID：{{ lastCaseId }}
          <span v-if="lastCaseCreatedAt">（检测时间：{{ lastCaseCreatedAt }}）</span>
        </div>
      </div>
      <!-- 在同一页面下方展示检测流程 -->
      <CaseView :case-id="lastCaseId" />
    </div>
  </div>
</template>

