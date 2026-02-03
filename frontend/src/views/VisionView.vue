<template>
  <div class="vision-view">
    <div class="page-header">
      <h1 class="page-title">视觉监控</h1>
      <div class="header-actions">
        <button class="btn btn-secondary" @click="toggleFullscreen">
          {{ isFullscreen ? '退出全屏' : '全屏' }}
        </button>
        <button class="btn btn-primary" @click="takeSnapshot">
          截图
        </button>
      </div>
    </div>

    <div class="vision-grid">
      <div class="video-container" ref="videoContainer">
        <img
          v-if="cameraUrl"
          :src="cameraUrl"
          alt="Camera Feed"
          class="camera-feed"
          :class="{ fullscreen: isFullscreen }"
        />
        <div v-else class="camera-placeholder">
          <div class="placeholder-icon">📹</div>
          <p>摄像头未连接</p>
        </div>

        <div class="video-overlay">
          <div class="timestamp">{{ currentTime }}</div>
          <div class="recording-indicator" v-if="isRecording">
            <span class="recording-dot"></span>
            REC
          </div>
        </div>

        <div class="detection-boxes" v-if="detections.length > 0">
          <div
            v-for="(detection, index) in detections"
            :key="index"
            class="detection-box"
            :style="{
              left: detection.x + '%',
              top: detection.y + '%',
              width: detection.width + '%',
              height: detection.height + '%'
            }"
          >
            <span class="detection-label">{{ detection.label }} ({{ Math.round(detection.confidence * 100) }}%)</span>
          </div>
        </div>
      </div>

      <div class="vision-sidebar">
        <div class="sidebar-section">
          <h3>检测设置</h3>
          <div class="setting-item">
            <label class="checkbox-label">
              <input v-model="settings.enableObjectDetection" type="checkbox" />
              <span>启用物体检测</span>
            </label>
          </div>
          <div class="setting-item">
            <label class="checkbox-label">
              <input v-model="settings.enableFaceDetection" type="checkbox" />
              <span>启用人脸检测</span>
            </label>
          </div>
          <div class="setting-item">
            <label class="checkbox-label">
              <input v-model="settings.enableMotionDetection" type="checkbox" />
              <span>启用运动检测</span>
            </label>
          </div>
          <div class="setting-item">
            <label>置信度阈值</label>
            <input
              v-model.number="settings.confidenceThreshold"
              type="range"
              min="0"
              max="100"
              class="range-input"
            />
            <span>{{ settings.confidenceThreshold }}%</span>
          </div>
        </div>

        <div class="sidebar-section">
          <h3>检测结果</h3>
          <div class="detections-list">
            <div
              v-for="(detection, index) in detections"
              :key="index"
              class="detection-item"
            >
              <span class="detection-icon">{{ getDetectionIcon(detection.label) }}</span>
              <div class="detection-info">
                <div class="detection-name">{{ detection.label }}</div>
                <div class="detection-confidence">
                  置信度: {{ Math.round(detection.confidence * 100) }}%
                </div>
              </div>
            </div>
            <div class="empty-detections" v-if="detections.length === 0">
              暂无检测结果
            </div>
          </div>
        </div>

        <div class="sidebar-section">
          <h3>控制</h3>
          <button
            class="btn"
            :class="isRecording ? 'btn-danger' : 'btn-secondary'"
            @click="toggleRecording"
          >
            {{ isRecording ? '停止录制' : '开始录制' }}
          </button>
          <button class="btn btn-secondary" @click="clearDetections">
            清除检测
          </button>
        </div>
      </div>
    </div>

    <div class="snapshots-section" v-if="snapshots.length > 0">
      <h3>快照</h3>
      <div class="snapshots-grid">
        <div
          v-for="(snapshot, index) in snapshots"
          :key="index"
          class="snapshot-item"
          @click="viewSnapshot(snapshot)"
        >
          <img :src="snapshot.url" :alt="`Snapshot ${index}`" />
          <div class="snapshot-time">{{ formatTime(snapshot.time) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useAppStore } from '@/stores/app'
import dayjs from 'dayjs'

const store = useAppStore()

const videoContainer = ref<HTMLElement>()
const cameraUrl = ref('')
const isFullscreen = ref(false)
const isRecording = ref(false)
const currentTime = ref('')
const detections = ref<Array<{
  label: string
  confidence: number
  x: number
  y: number
  width: number
  height: number
}>>([])

const settings = ref({
  enableObjectDetection: true,
  enableFaceDetection: true,
  enableMotionDetection: true,
  confidenceThreshold: 70
})

const snapshots = ref<Array<{ url: string, time: Date }>>([])

let timeInterval: number | null = null

function updateTime() {
  currentTime.value = dayjs().format('HH:mm:ss')
}

function toggleFullscreen() {
  if (!document.fullscreenElement) {
    videoContainer.value?.requestFullscreen()
    isFullscreen.value = true
  } else {
    document.exitFullscreen()
    isFullscreen.value = false
  }
}

function takeSnapshot() {
  snapshots.value.push({
    url: cameraUrl.value,
    time: new Date()
  })
  store.addNotification('已保存快照', 'success')
}

function toggleRecording() {
  isRecording.value = !isRecording.value
  store.addNotification(
    isRecording.value ? '开始录制' : '停止录制',
    isRecording.value ? 'info' : 'success'
  )
}

function clearDetections() {
  detections.value = []
}

function getDetectionIcon(label: string): string {
  const icons: Record<string, string> = {
    person: '👤',
    face: '👤',
    car: '🚗',
    dog: '🐕',
    cat: '🐱',
    chair: '🪑',
    bottle: '🍾'
  }
  return icons[label] || '📦'
}

function formatTime(time: Date): string {
  return dayjs(time).format('HH:mm:ss')
}

function viewSnapshot(snapshot: any) {
  window.open(snapshot.url, '_blank')
}

onMounted(() => {
  updateTime()
  timeInterval = setInterval(updateTime, 1000) as unknown as number
  
  document.addEventListener('fullscreenchange', () => {
    isFullscreen.value = !!document.fullscreenElement
  })

  cameraUrl.value = '/api/camera/stream'
  
  detections.value = [
    { label: 'person', confidence: 0.95, x: 10, y: 20, width: 30, height: 50 },
    { label: 'chair', confidence: 0.87, x: 50, y: 40, width: 25, height: 35 }
  ]
})

onUnmounted(() => {
  if (timeInterval) {
    clearInterval(timeInterval)
  }
})
</script>

<style scoped>
.vision-view {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-title {
  font-size: var(--font-size-xl);
  color: var(--text-color);
}

.header-actions {
  display: flex;
  gap: 12px;
}

.vision-grid {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 24px;
}

.video-container {
  position: relative;
  background-color: #000;
  border-radius: var(--radius-md);
  overflow: hidden;
  aspect-ratio: 16/9;
}

.camera-feed {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.camera-feed.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 1000;
}

.camera-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-secondary);
}

.placeholder-icon {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.video-overlay {
  position: absolute;
  top: 16px;
  left: 16px;
  right: 16px;
  display: flex;
  justify-content: space-between;
  pointer-events: none;
}

.timestamp {
  background-color: rgba(0, 0, 0, 0.6);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-family: monospace;
  font-size: 14px;
}

.recording-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  background-color: rgba(239, 68, 68, 0.9);
  color: white;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.recording-dot {
  width: 8px;
  height: 8px;
  background-color: white;
  border-radius: 50%;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.detection-boxes {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  pointer-events: none;
}

.detection-box {
  position: absolute;
  border: 2px solid var(--primary-color);
  background-color: rgba(99, 102, 241, 0.1);
}

.detection-label {
  position: absolute;
  top: -20px;
  left: 0;
  background-color: var(--primary-color);
  color: white;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 11px;
  white-space: nowrap;
}

.vision-sidebar {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.sidebar-section {
  background-color: var(--card-bg);
  border-radius: var(--radius-md);
  padding: 20px;
  box-shadow: var(--shadow);
}

.sidebar-section h3 {
  font-size: var(--font-size-md);
  color: var(--text-color);
  margin-bottom: 16px;
}

.setting-item {
  margin-bottom: 16px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-size: var(--font-size-sm);
  color: var(--text-color);
}

.range-input {
  width: 100%;
  margin-right: 8px;
}

.detections-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.detection-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  background-color: var(--bg-color);
  border-radius: var(--radius);
}

.detection-icon {
  font-size: 24px;
}

.detection-info {
  flex: 1;
}

.detection-name {
  font-size: var(--font-size-sm);
  font-weight: 500;
  color: var(--text-color);
}

.detection-confidence {
  font-size: 11px;
  color: var(--text-secondary);
}

.empty-detections {
  text-align: center;
  padding: 20px;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}

.sidebar-section .btn {
  width: 100%;
  margin-bottom: 8px;
}

.snapshots-section {
  margin-top: 24px;
}

.snapshots-section h3 {
  font-size: var(--font-size-md);
  color: var(--text-color);
  margin-bottom: 16px;
}

.snapshots-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 16px;
}

.snapshot-item {
  position: relative;
  border-radius: var(--radius);
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.2s;
}

.snapshot-item:hover {
  transform: scale(1.05);
}

.snapshot-item img {
  width: 100%;
  aspect-ratio: 16/9;
  object-fit: cover;
}

.snapshot-time {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background-color: rgba(0, 0, 0, 0.7);
  color: white;
  padding: 4px 8px;
  font-size: 11px;
}
</style>
