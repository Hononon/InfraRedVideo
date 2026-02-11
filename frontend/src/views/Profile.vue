<script setup>
import { onMounted, computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api/client'
import logo from '../assets/logo.png'

const router = useRouter()

const loading = ref(false)
const error = ref('')
const username = ref('')
const recentUsage = ref([])
const cases = ref([])

const maxCount = computed(() => {
  if (!recentUsage.value.length) return 0
  return Math.max(...recentUsage.value.map((d) => d.count || 0))
})

async function loadHistory() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/api/user/history')
    if (!data.ok) throw new Error(data.msg || '获取历史记录失败')
    username.value = data.username || ''
    recentUsage.value = data.recent_usage || []
    cases.value = data.cases || []
  } catch (e) {
    error.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

function goHome() {
  router.push('/home')
}

onMounted(() => {
  loadHistory()
})
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
        <div class="user">当前用户：{{ username || '未知用户' }}</div>
        <el-button @click="goHome">返回首页</el-button>
      </div>
    </div>

    <div class="card" style="margin-bottom: 16px">
      <div class="card-title">个人中心</div>
      <div class="muted">
        当前用户：<strong>{{ username || '未知用户' }}</strong>
      </div>
    </div>

    <div class="card" style="margin-bottom: 16px">
      <div class="card-title">过去一周使用情况统计</div>
      <div v-if="loading" class="muted">加载中...</div>
      <el-alert v-else-if="error" :title="error" type="error" show-icon :closable="false" />
      <div v-else class="usage-chart">
        <div
          v-for="d in recentUsage"
          :key="d.date"
          class="usage-bar-item"
          :title="d.date + '：' + d.count + ' 次'"
        >
          <div
            class="bar"
            :style="{
              height: (maxCount ? 24 + (d.count / maxCount) * 60 : 8) + 'px',
            }"
          >
            <span class="bar-count">{{ d.count }}</span>
          </div>
          <div class="bar-label">{{ d.date.slice(5) }}</div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">历史检测记录</div>
      <div v-if="loading" class="muted">加载中...</div>
      <div v-else-if="!cases.length" class="muted">暂无检测记录。</div>
      <div v-else class="history-list">
        <div class="history-header">
          <div class="col time">检测时间</div>
          <div class="col case">Case ID</div>
          <div class="col value">泄漏量估计结果 (kg/h)</div>
        </div>
        <div v-for="item in cases" :key="item.case_id + (item.created_at || '')" class="history-row">
          <div class="col time">{{ item.created_at || '-' }}</div>
          <div class="col case">{{ item.case_id }}</div>
          <div class="col value">
            <span v-if="item.result != null">{{ Number(item.result).toFixed(4) }}</span>
            <span v-else class="muted">暂无结果</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.usage-chart {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding-top: 10px;
}
.usage-bar-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.bar {
  width: 24px;
  min-height: 8px;
  border-radius: 12px 12px 4px 4px;
  background: linear-gradient(180deg, #38bdf8, #0ea5e9);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  color: #e6edf3;
  font-size: 11px;
}
.bar-count {
  padding-bottom: 2px;
}
.bar-label {
  margin-top: 4px;
  font-size: 11px;
  color: #93a4b8;
}
.history-list {
  margin-top: 8px;
  font-size: 13px;
}
.history-header,
.history-row {
  display: flex;
  align-items: center;
  padding: 6px 0;
}
.history-header {
  border-bottom: 1px solid rgba(148, 163, 184, 0.3);
  font-weight: 600;
}
.history-row:nth-child(odd) {
  background: rgba(15, 23, 42, 0.4);
}
.col {
  padding-right: 8px;
}
.col.time {
  width: 210px;
  flex-shrink: 0;
}
.col.case {
  flex: 1;
  word-break: break-all;
}
.col.value {
  width: 180px;
  flex-shrink: 0;
}
</style>

