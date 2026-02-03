<template>
  <div class="automation-card" :class="{ disabled: !automation.enabled }">
    <div class="automation-header">
      <div class="automation-info">
        <h3 class="automation-name">{{ automation.name }}</h3>
        <p class="automation-description" v-if="automation.description">
          {{ automation.description }}
        </p>
      </div>
      <div class="automation-status">
        <span class="status-badge" :class="{ active: automation.enabled }">
          {{ automation.enabled ? '已启用' : '已禁用' }}
        </span>
      </div>
    </div>

    <div class="automation-details">
      <div class="detail-section">
        <h4>触发条件 ({{ automation.triggers.length }})</h4>
        <div class="triggers-list">
          <div v-for="(trigger, index) in automation.triggers" :key="index" class="trigger-item">
            {{ getTriggerDescription(trigger) }}
          </div>
        </div>
      </div>

      <div class="detail-section">
        <h4>执行动作 ({{ automation.actions.length }})</h4>
        <div class="actions-list">
          <div v-for="(action, index) in automation.actions" :key="index" class="action-item">
            {{ getActionDescription(action) }}
          </div>
        </div>
      </div>

      <div class="detail-section" v-if="automation.lastTriggered">
        <h4>最后触发</h4>
        <span class="last-triggered">{{ formatTime(automation.lastTriggered) }}</span>
      </div>
    </div>

    <div class="automation-actions">
      <button class="btn btn-secondary btn-sm" @click="$emit('toggle', automation)">
        {{ automation.enabled ? '禁用' : '启用' }}
      </button>
      <button class="btn btn-primary btn-sm" @click="$emit('trigger', automation)" :disabled="!automation.enabled">
        手动触发
      </button>
      <button class="btn btn-secondary btn-sm" @click="$emit('edit', automation)">
        编辑
      </button>
      <button class="btn btn-danger btn-sm" @click="$emit('delete', automation)">
        删除
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Automation } from '@/stores/app'
import dayjs from 'dayjs'
import 'dayjs/locale/zh-cn'

defineProps<{
  automation: Automation
}>()

defineEmits<{
  toggle: [automation: Automation]
  trigger: [automation: Automation]
  edit: [automation: Automation]
  delete: [automation: Automation]
}>()

function getTriggerDescription(trigger: any): string {
  if (trigger.trigger_type === 'state') {
    return `当 ${trigger.entity_id} 从 ${trigger.from_state} 变为 ${trigger.to_state}`
  } else if (trigger.trigger_type === 'time') {
    return `在 ${trigger.trigger_time}`
  } else if (trigger.trigger_type === 'event') {
    return `当事件 ${trigger.event_type} 发生`
  }
  return JSON.stringify(trigger)
}

function getActionDescription(action: any): string {
  if (action.action_type === 'service') {
    return `执行 ${action.service} 在 ${action.entity_id}`
  } else if (action.action_type === 'delay') {
    return `延迟 ${action.delay_seconds} 秒`
  } else if (action.action_type === 'notify') {
    return `发送通知: ${action.message}`
  }
  return JSON.stringify(action)
}

function formatTime(time: string): string {
  return dayjs(time).locale('zh-cn').fromNow()
}
</script>

<style scoped>
.automation-card {
  background-color: var(--card-bg);
  border-radius: var(--radius-md);
  padding: 20px;
  box-shadow: var(--shadow);
  transition: all 0.2s;
}

.automation-card:hover {
  box-shadow: var(--shadow-md);
}

.automation-card.disabled {
  opacity: 0.6;
}

.automation-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.automation-name {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--text-color);
  margin: 0 0 8px 0;
}

.automation-description {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: 0;
}

.status-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  background-color: var(--border-color);
  color: var(--text-secondary);
}

.status-badge.active {
  background-color: rgba(16, 185, 129, 0.1);
  color: var(--success-color);
}

.automation-details {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.detail-section h4 {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  margin-bottom: 12px;
}

.triggers-list,
.actions-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.trigger-item,
.action-item {
  padding: 8px 12px;
  background-color: var(--bg-color);
  border-radius: var(--radius-sm);
  font-size: 13px;
  color: var(--text-color);
}

.last-triggered {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}

.automation-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.btn-sm {
  padding: 8px 16px;
  font-size: 13px;
}

.btn-sm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
