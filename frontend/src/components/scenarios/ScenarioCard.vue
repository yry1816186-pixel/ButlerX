<template>
  <div class="scenario-card" :class="{ active: scenario.active }">
    <div class="scenario-icon">{{ getScenarioIcon(scenario.type) }}</div>
    <h3 class="scenario-name">{{ scenario.name }}</h3>
    <p class="scenario-description" v-if="scenario.description">
      {{ scenario.description }}
    </p>
    <div class="scenario-type badge badge-info">
      {{ getScenarioTypeLabel(scenario.type) }}
    </div>
    <button
      class="btn"
      :class="scenario.active ? 'btn-secondary' : 'btn-primary'"
      @click="handleAction"
    >
      {{ scenario.active ? '停用' : '激活' }}
    </button>
  </div>
</template>

<script setup lang="ts">
import type { Scenario } from '@/stores/app'

defineProps<{
  scenario: Scenario
}>()

const emit = defineEmits<{
  activate: [scenario: Scenario]
  deactivate: [scenario: Scenario]
}>()

function getScenarioIcon(type: string): string {
  const icons: Record<string, string> = {
    wake_up: '🌅',
    sleep: '🌙',
    away: '🚪',
    home: '🏡',
    relax: '🛋️',
    movie: '🎬',
    guest: '👋',
    work: '💼'
  }
  return icons[type] || '🎭'
}

function getScenarioTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    wake_up: '起床',
    sleep: '睡眠',
    away: '离家',
    home: '回家',
    relax: '放松',
    movie: '观影',
    guest: '客人',
    work: '工作'
  }
  return labels[type] || type
}

function handleAction() {
  if (props.scenario.active) {
    emit('deactivate', props.scenario)
  } else {
    emit('activate', props.scenario)
  }
}
</script>

<style scoped>
.scenario-card {
  background-color: var(--card-bg);
  border-radius: var(--radius-md);
  padding: 24px;
  box-shadow: var(--shadow);
  text-align: center;
  transition: all 0.2s;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.scenario-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-md);
}

.scenario-card.active {
  border: 2px solid var(--primary-color);
}

.scenario-icon {
  font-size: 48px;
}

.scenario-name {
  font-size: var(--font-size-md);
  font-weight: 600;
  color: var(--text-color);
  margin: 0;
}

.scenario-description {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin: 0;
  flex: 1;
}

.scenario-type {
  margin-bottom: 8px;
}

.scenario-card .btn {
  width: 100%;
  max-width: 200px;
}
</style>
