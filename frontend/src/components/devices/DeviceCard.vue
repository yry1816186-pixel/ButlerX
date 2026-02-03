<template>
  <div class="device-card" :class="{ offline: device.status === 'offline' }">
    <div class="device-header">
      <div class="device-info">
        <span class="device-icon">{{ getDeviceIcon(device.type) }}</span>
        <div>
          <h3 class="device-name">{{ device.name }}</h3>
          <p class="device-type">{{ device.type }}</p>
        </div>
      </div>
      <div class="device-status" :class="device.status">
        {{ device.status === 'online' ? '在线' : '离线' }}
      </div>
    </div>

    <div class="device-state" v-if="device.state">
      <div v-for="(value, key) in displayState" :key="key" class="state-item">
        <span class="state-key">{{ formatKey(key) }}:</span>
        <span class="state-value">{{ formatValue(value) }}</span>
      </div>
    </div>

    <div class="device-actions">
      <button class="btn btn-primary btn-sm" @click="$emit('toggle', device)">
        切换
      </button>
      <button class="btn btn-secondary btn-sm" @click="$emit('control', device, 'refresh')">
        刷新
      </button>
    </div>

    <div class="device-location">
      <span>📍 {{ device.location }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Device } from '@/stores/app'

defineProps<{
  device: Device
}>()

defineEmits<{
  control: [device: Device, command: string]
  toggle: [device: Device]
}>()

function getDeviceIcon(type: string): string {
  const icons: Record<string, string> = {
    light: '💡',
    switch: '🔌',
    sensor: '📡',
    camera: '📹',
    thermostat: '🌡️',
    lock: '🔒',
    cover: '🪟',
    fan: '🌀',
    vacuum: '🧹',
    speaker: '🔊',
    tv: '📺'
  }
  return icons[type] || '📱'
}

function formatKey(key: string): string {
  const translations: Record<string, string> = {
    state: '状态',
    brightness: '亮度',
    color: '颜色',
    temperature: '温度',
    humidity: '湿度',
    power: '电源',
    volume: '音量',
    position: '位置'
  }
  return translations[key] || key
}

function formatValue(value: any): string {
  if (typeof value === 'boolean') {
    return value ? '开' : '关'
  }
  if (typeof value === 'number') {
    return value.toString()
  }
  return String(value)
}

const displayState = computed(() => {
  if (!props.device?.state) return {}
  const state: Record<string, any> = {}
  for (const [key, value] of Object.entries(props.device.state)) {
    if (value !== null && value !== undefined) {
      state[key] = value
    }
  }
  return state
})
</script>

<style scoped>
.device-card {
  background-color: var(--card-bg);
  border-radius: var(--radius-md);
  padding: 20px;
  box-shadow: var(--shadow);
  transition: transform 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.device-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
}

.device-card.offline {
  opacity: 0.6;
}

.device-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.device-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.device-icon {
  font-size: 32px;
}

.device-name {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--text-color);
  margin: 0;
}

.device-type {
  font-size: 12px;
  color: var(--text-secondary);
  margin: 4px 0 0 0;
}

.device-status {
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 12px;
  font-weight: 500;
}

.device-status.online {
  background-color: rgba(16, 185, 129, 0.1);
  color: var(--success-color);
}

.device-status.offline {
  background-color: rgba(239, 68, 68, 0.1);
  color: var(--danger-color);
}

.device-state {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background-color: var(--bg-color);
  border-radius: var(--radius);
}

.state-item {
  display: flex;
  justify-content: space-between;
  font-size: var(--font-size-sm);
}

.state-key {
  color: var(--text-secondary);
}

.state-value {
  color: var(--text-color);
  font-weight: 500;
}

.device-actions {
  display: flex;
  gap: 8px;
}

.btn-sm {
  flex: 1;
  padding: 8px 12px;
  font-size: 13px;
}

.device-location {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
