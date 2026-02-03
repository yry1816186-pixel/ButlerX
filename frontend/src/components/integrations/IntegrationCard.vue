<template>
  <div class="integration-card" :class="{ connected: integration.connected }">
    <div class="integration-header">
      <div class="integration-logo">{{ getIntegrationLogo(integration.type) }}</div>
      <div class="integration-info">
        <h3 class="integration-name">{{ integration.name }}</h3>
        <span class="integration-type badge badge-info">
          {{ getIntegrationTypeLabel(integration.type) }}
        </span>
      </div>
      <div class="integration-status" :class="integration.connected ? 'connected' : 'disconnected'">
        {{ integration.connected ? '已连接' : '未连接' }}
      </div>
    </div>

    <div class="integration-actions">
      <button
        v-if="!integration.connected"
        class="btn btn-primary btn-sm"
        @click="$emit('connect', integration)"
      >
        连接
      </button>
      <button
        v-else
        class="btn btn-danger btn-sm"
        @click="$emit('disconnect', integration)"
      >
        断开
      </button>
      <button
        class="btn btn-secondary btn-sm"
        @click="$emit('configure', integration)"
        :disabled="!integration.connected"
      >
        配置
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Integration } from '@/stores/app'

defineProps<{
  integration: Integration
}>()

defineEmits<{
  connect: [integration: Integration]
  disconnect: [integration: Integration]
  configure: [integration: Integration]
}>()

function getIntegrationLogo(type: string): string {
  const logos: Record<string, string> = {
    home_assistant: '🏠',
    philips_hue: '💡',
    sonos: '🔊',
    ring: '🔔',
    nest: '🌡️',
    homekit: '🍎',
    spotify: '🎵',
    xiaomi_miio: '📱'
  }
  return logos[type] || '🔌'
}

function getIntegrationTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    home_assistant: 'Home Assistant',
    philips_hue: 'Philips Hue',
    sonos: 'Sonos',
    ring: 'Ring',
    nest: 'Nest',
    homekit: 'HomeKit',
    spotify: 'Spotify',
    xiaomi_miio: 'Xiaomi Miio'
  }
  return labels[type] || type
}
</script>

<style scoped>
.integration-card {
  background-color: var(--card-bg);
  border-radius: var(--radius-md);
  padding: 20px;
  box-shadow: var(--shadow);
  transition: all 0.2s;
}

.integration-card:hover {
  box-shadow: var(--shadow-md);
}

.integration-card.connected {
  border-left: 4px solid var(--success-color);
}

.integration-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.integration-logo {
  font-size: 40px;
  width: 60px;
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--bg-color);
  border-radius: var(--radius);
}

.integration-info {
  flex: 1;
}

.integration-name {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--text-color);
  margin: 0 0 8px 0;
}

.integration-type {
  font-size: 11px;
}

.integration-status {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 500;
}

.integration-status.connected {
  background-color: rgba(16, 185, 129, 0.1);
  color: var(--success-color);
}

.integration-status.disconnected {
  background-color: rgba(239, 68, 68, 0.1);
  color: var(--danger-color);
}

.integration-actions {
  display: flex;
  gap: 8px;
}

.btn-sm {
  flex: 1;
  padding: 8px 12px;
  font-size: 13px;
}

.btn-sm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
