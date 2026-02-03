<template>
  <div class="dashboard-view">
    <h1 class="page-title">仪表盘</h1>
    
    <div class="stats-row">
      <StatCard v-for="stat in stats" :key="stat.label" :stat="stat" />
    </div>

    <div class="dashboard-grid">
      <div class="card section">
        <h2 class="section-title">快速控制</h2>
        <div class="quick-controls">
          <button v-for="control in quickControls" :key="control.id" class="control-btn" @click="control.action">
            <span class="control-icon">{{ control.icon }}</span>
            <span class="control-label">{{ control.label }}</span>
          </button>
        </div>
      </div>

      <div class="card section">
        <h2 class="section-title">最近活动</h2>
        <div class="activity-list">
          <div v-for="activity in activities" :key="activity.id" class="activity-item">
            <span class="activity-icon">{{ activity.icon }}</span>
            <div class="activity-content">
              <div class="activity-title">{{ activity.title }}</div>
              <div class="activity-time">{{ activity.time }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="card section">
        <h2 class="section-title">在线设备</h2>
        <div class="device-list">
          <div v-for="device in onlineDevices" :key="device.id" class="device-item">
            <span class="device-status online"></span>
            <span class="device-name">{{ device.name }}</span>
            <span class="device-type">{{ device.type }}</span>
          </div>
        </div>
      </div>

      <div class="card section">
        <h2 class="section-title">活跃自动化</h2>
        <div class="automation-list">
          <div v-for="automation in enabledAutomations" :key="automation.id" class="automation-item">
            <span class="automation-name">{{ automation.name }}</span>
            <span class="automation-status badge badge-success">启用</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import StatCard from '@/components/dashboard/StatCard.vue'

const store = useAppStore()

const stats = ref([
  { label: '设备', value: 0, icon: '🏠' },
  { label: '自动化', value: 0, icon: '⚡' },
  { label: '场景', value: 0, icon: '🎭' },
  { label: '集成', value: 0, icon: '🔌' }
])

const quickControls = ref([
  { id: 'all_off', label: '全部关闭', icon: '🌙', action: () => store.addNotification('已关闭所有设备', 'success') },
  { id: 'home_mode', label: '回家模式', icon: '🏡', action: () => store.addNotification('已激活回家模式', 'success') },
  { id: 'away_mode', label: '离家模式', icon: '🚪', action: () => store.addNotification('已激活离家模式', 'success') },
  { id: 'night_mode', label: '睡眠模式', icon: '😴', action: () => store.addNotification('已激活睡眠模式', 'success') }
])

const activities = ref([
  { id: 1, title: '客厅灯光已打开', time: '5分钟前', icon: '💡' },
  { id: 2, title: '温度传感器更新: 23°C', time: '10分钟前', icon: '🌡️' },
  { id: 3, title: '回家模式已激活', time: '1小时前', icon: '🏡' },
  { id: 4, title: '门锁已解锁', time: '2小时前', icon: '🔓' }
])

const onlineDevices = computed(() => store.onlineDevices.slice(0, 5))
const enabledAutomations = computed(() => store.enabledAutomations.slice(0, 5))

onMounted(() => {
  stats.value[0].value = store.devices.length
  stats.value[1].value = store.automations.length
  stats.value[2].value = store.scenarios.length
  stats.value[3].value = store.integrations.length
})
</script>

<style scoped>
.dashboard-view {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.page-title {
  font-size: var(--font-size-xl);
  margin-bottom: 24px;
  color: var(--text-color);
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
}

.section {
  padding: 24px;
}

.section-title {
  font-size: var(--font-size-lg);
  margin-bottom: 20px;
  color: var(--text-color);
}

.quick-controls {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.control-btn {
  background-color: var(--bg-color);
  border: 2px solid var(--border-color);
  border-radius: var(--radius);
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.control-btn:hover {
  border-color: var(--primary-color);
  background-color: var(--primary-color);
  color: white;
}

.control-icon {
  font-size: 28px;
}

.control-label {
  font-size: var(--font-size-sm);
  font-weight: 500;
}

.activity-list,
.device-list,
.automation-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.activity-item,
.device-item,
.automation-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background-color: var(--bg-color);
  border-radius: var(--radius);
}

.activity-icon {
  font-size: 20px;
}

.activity-content {
  flex: 1;
}

.activity-title {
  font-size: var(--font-size-sm);
  color: var(--text-color);
}

.activity-time {
  font-size: 12px;
  color: var(--text-secondary);
}

.device-status {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.device-status.online {
  background-color: var(--success-color);
}

.device-name {
  flex: 1;
  font-size: var(--font-size-sm);
  color: var(--text-color);
}

.device-type {
  font-size: 12px;
  color: var(--text-secondary);
}

.automation-name {
  flex: 1;
  font-size: var(--font-size-sm);
  color: var(--text-color);
}
</style>
