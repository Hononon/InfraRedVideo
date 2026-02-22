<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api/client'

const props = defineProps({
  caseId: {
    type: String,
    required: false,
  },
})

const route = useRoute()
const router = useRouter()
// 既支持通过路由 /case/:id 使用，也支持作为组件在 Home 中通过 props.caseId 使用
const caseId = computed(() => props.caseId || route.params.caseId)

const info = ref(null)
const infoLoading = ref(false)

const result = ref(null)
const polling = ref(false)
let pollTimer = null
let previewTimer = null

const videoEl = ref(null)
const canvasEl = ref(null)
let drawing = false
let start = null
const rect = reactive({ x: null, y: null, w: null, h: null })

const form = reactive({
  distance: '',
  fov: '',
  Tb: '',
  Tg: '',
})

// 在 Home 中作为子组件使用时（通过 props.caseId 传入）不再使用整体 .page 布局，
// 以避免左右出现第二层 padding，导致宽度比“当前检测任务”卡片更窄
const isEmbedded = computed(() => !!props.caseId)

// 后端基地址（如 http://127.0.0.1:5001）
const apiBase = api.defaults.baseURL.replace(/\/$/, '')

const previewUrl = computed(() => {
  const p = info.value && info.value.preview_url
  if (!p) return null
  if (p.startsWith('http://') || p.startsWith('https://')) return p
  return apiBase + p
})

const finalUrl = computed(() => {
  const p = result.value && result.value.final_video_url
  if (!p) return null
  if (p.startsWith('http://') || p.startsWith('https://')) return p
  return apiBase + p
})
const showFinal = computed(() => !!finalUrl.value)

function backHome() {
  // 如果作为独立路由使用，则返回首页；在 Home 中嵌套使用时，这个按钮不会出现
  router.push('/home')
}

async function loadInfo() {
  infoLoading.value = true
  try {
    const { data } = await api.get(`/api/cases/${caseId.value}`)
    info.value = data
  } catch (e) {
    // 避免前端直接白屏，先把错误打到控制台
    console.error('加载 case 信息失败', e)
  } finally {
    infoLoading.value = false
  }
}

function resizeCanvas() {
  const vid = videoEl.value
  const canvas = canvasEl.value
  if (!vid || !canvas) return
  const w = vid.videoWidth
  const h = vid.videoHeight
  if (!w || !h) return
  canvas.width = w
  canvas.height = h
  drawRect()
}

function toCanvasXY(e) {
  const canvas = canvasEl.value
  const r = canvas.getBoundingClientRect()
  const scaleX = canvas.width / r.width
  const scaleY = canvas.height / r.height
  return {
    x: (e.clientX - r.left) * scaleX,
    y: (e.clientY - r.top) * scaleY,
  }
}

function drawRect() {
  const canvas = canvasEl.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  if (rect.x === null) return
  ctx.lineWidth = 2
  ctx.strokeStyle = '#67e8f9'
  ctx.setLineDash([6, 3])
  ctx.strokeRect(rect.x, rect.y, rect.w, rect.h)
}

function onMouseDown(e) {
  drawing = true
  start = toCanvasXY(e)
  rect.x = start.x
  rect.y = start.y
  rect.w = 0
  rect.h = 0
  drawRect()
}

function onMouseMove(e) {
  if (!drawing) return
  const p = toCanvasXY(e)
  let w = p.x - start.x
  let h = p.y - start.y
  const nx = w < 0 ? start.x + w : start.x
  const ny = h < 0 ? start.y + h : start.y
  w = Math.abs(w)
  h = Math.abs(h)
  rect.x = nx
  rect.y = ny
  rect.w = w
  rect.h = h
  drawRect()
}

function onMouseUp() {
  drawing = false
}

function clearRect() {
  rect.x = rect.y = rect.w = rect.h = null
  drawRect()
}

const rectText = computed(() => {
  if (rect.x === null) return '未选择裁剪区域'
  return `裁剪: x=${Math.round(rect.x)}, y=${Math.round(rect.y)}, w=${Math.round(rect.w)}, h=${Math.round(rect.h)}`
})

async function submitParams() {
  if (rect.x === null) throw new Error('请先框选矩形区域')
  if (!form.distance || !form.fov) throw new Error('请填写 distance / fov')

  const payload = {
    crop: {
      x: Math.round(rect.x),
      y: Math.round(rect.y),
      w: Math.round(rect.w),
      h: Math.round(rect.h),
    },
    distance: parseFloat(form.distance),
    fov: parseFloat(form.fov),
  }

  if (form.Tb) {
    payload.Tb = parseFloat(form.Tb)
  }
  if (form.Tg) {
    payload.Tg = parseFloat(form.Tg)
  }

  const { data } = await api.post(`/api/cases/${caseId.value}/params`, payload)
  if (!data.ok) throw new Error(data.msg || '提交失败')
  startPolling()
}

async function fetchResultOnce() {
  const { data } = await api.get(`/api/cases/${caseId.value}/result`)
  result.value = data
}

function startPolling() {
  if (pollTimer) return
  polling.value = true
  pollTimer = setInterval(fetchResultOnce, 2000)
  fetchResultOnce()
}

function stopPolling() {
  polling.value = false
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
}

function startPreviewPolling() {
  // 如果已经有预览地址，就不用轮询了
  if (previewUrl.value) return
  if (previewTimer) return
  previewTimer = setInterval(async () => {
    await loadInfo()
    if (previewUrl.value) {
      clearInterval(previewTimer)
      previewTimer = null
    }
  }, 2000)
}

function stopPreviewPolling() {
  if (previewTimer) clearInterval(previewTimer)
  previewTimer = null
}

onMounted(async () => {
  await loadInfo()
  startPolling()
  startPreviewPolling()
  window.addEventListener('resize', resizeCanvas)
})

onBeforeUnmount(() => {
  stopPolling()
  stopPreviewPolling()
  window.removeEventListener('resize', resizeCanvas)
})
</script>

<template>
  <div :class="isEmbedded ? 'case-embedded' : 'page'">
    <div class="row">
      <div class="card flex1">
        <div class="card-title">原始红外视频（预览）</div>
        <div class="muted" style="margin-bottom: 8px">{{ rectText }}</div>

        <div v-if="!previewUrl" class="muted">
          预览视频生成中...（RAW 解码与合成 preview.mp4 需要一些时间）
        </div>

        <div v-else class="player">
          <video
            ref="videoEl"
            :src="previewUrl"
            controls
            autoplay
            loop
            @loadedmetadata="resizeCanvas"
          />
          <canvas
            ref="canvasEl"
            class="overlay"
            @mousedown="onMouseDown"
            @mousemove="onMouseMove"
            @mouseup="onMouseUp"
          />
        </div>

        <div class="btns">
          <el-button @click="clearRect">清除矩形</el-button>
        </div>
      </div>

      <div class="card side">
        <div class="card-title">参数</div>
        <el-form label-position="top">
          <el-form-item label="距离（distance，m）">
            <el-input v-model="form.distance" placeholder="如 10" />
          </el-form-item>
          <el-form-item label="视场角（FOV，度）">
            <el-input v-model="form.fov" placeholder="如 45" />
          </el-form-item>
          <el-form-item label="背景温度 Tb（K，可选）">
            <el-input v-model="form.Tb" placeholder="如 290" />
          </el-form-item>
          <el-form-item label="环境温度 Tg（K，可选）">
            <el-input v-model="form.Tg" placeholder="如 285" />
          </el-form-item>
          <el-button type="primary" style="width: 100%" @click="submitParams">提交并开始计算</el-button>
        </el-form>

        <div style="margin-top: 14px">
          <div class="card-title">计算状态</div>
          <div class="muted">{{ (result && result.progress) || '等待中...' }}</div>
        </div>
      </div>
    </div>

    <!-- 独立泄漏量结果条，与参数卡片纵向拉开距离 -->
    <div v-if="result && result.result != null" class="result-wrapper">
      <div class="card result-card">
        <div class="result-title">泄漏量估计结果</div>
        <div class="result-value-large">{{ Number(result.result || 0).toFixed(4) }} kg/h</div>
        
      </div>
    </div>

    <!-- 下方两路视频，缩小后放在同一个卡片内 -->
    <div v-if="showFinal" class="card video-card">
      <div class="card-title">可视化结果</div>
      <div class="video-row">
        <div class="video-col">
          <div class="muted small-title">最终热力图视频</div>
          <div class="result-video-wrapper">
            <video class="result-video" :src="finalUrl" controls autoplay loop />
          </div>
        </div>
        <div class="video-col">
          <div class="muted small-title">原始预览（对照）</div>
          <div class="result-video-wrapper">
            <video class="result-video" :src="previewUrl" controls autoplay loop />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.case-embedded {
  margin: 0;
  padding: 0;
}

.row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.flex1 {
  flex: 1;
  min-width: 320px;
}
.side {
  width: 380px;
  max-width: 100%;
}
.player {
  position: relative;
  display: block;
  width: 100%;
  max-width: 640px;
  height: 360px; /* 固定预览区域高度，避免随视频尺寸抖动 */
  margin: 0 auto;
}
/* 仅预览区域的视频全铺满 player 容器，保持原始宽高比 */
.player > video {
  width: 100%;
  height: 100%;
  border-radius: 12px;
  display: block;
  object-fit: contain; /* 保留原始长宽比，必要时加黑边 */
  background: #000;
}
.overlay {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
  cursor: crosshair;
}
.btns {
  margin-top: 10px;
}
.result-wrapper {
  margin-top: 16px;
}
.result-card {
  text-align: center;
}
.result-title {
  font-size: 18px;
  font-weight: 800;
  margin-bottom: 10px;
}
.result-value-large {
  font-size: 24px;
  font-weight: 800;
  color: #4ade80;
  margin-bottom: 4px;
}

.video-card {
  margin-top: 18px;
}
.video-card .card-title {
  text-align: center;
  font-size: 18px;
  font-weight: 800;
}
.video-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: space-between;
}
.video-col {
  flex: 1 1 0;
  min-width: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
}
.small-title {
  margin-bottom: 6px;
}
.result-video-wrapper {
  width: 100%;
  max-width: 480px;
   margin: 0 auto;
  aspect-ratio: 5 / 4; /* 接近 320x256 的比例，保持视觉一致 */
  background: #000;
  border-radius: 12px;
  overflow: hidden;
}
.result-video {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: contain;
}
</style>

