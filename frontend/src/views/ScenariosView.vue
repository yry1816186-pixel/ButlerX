<template>
  <div class="scenarios-view">
    <div class="page-header">
      <h1 class="page-title">场景模式</h1>
      <button class="btn btn-primary" @click="createScenario">
        新建场景
      </button>
    </div>

    <div class="scenarios-grid">
      <ScenarioCard
        v-for="scenario in scenarios"
        :key="scenario.id"
        :scenario="scenario"
        @activate="handleActivate"
        @deactivate="handleDeactivate"
      />
    </div>

    <div class="empty-state" v-if="scenarios.length === 0">
      <div class="empty-icon">🎭</div>
      <h2>暂无场景</h2>
      <p>点击"新建场景"开始创建您的第一个场景模式</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAppStore } from '@/stores/app'
import ScenarioCard from '@/components/scenarios/ScenarioCard.vue'
import type { Scenario } from '@/stores/app'

const store = useAppStore()

const scenarios = computed(() => store.scenarios)

function createScenario() {
  store.addNotification('场景创建功能开发中', 'info')
}

function handleActivate(scenario: Scenario) {
  store.addNotification(`已激活场景: ${scenario.name}`, 'success')
}

function handleDeactivate(scenario: Scenario) {
  store.addNotification(`已停用场景: ${scenario.name}`, 'info')
}
</script>

<style scoped>
.scenarios-view {
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

.scenarios-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.empty-state {
  text-align: center;
  padding: 80px 20px;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 24px;
  opacity: 0.5;
}

.empty-state h2 {
  font-size: var(--font-size-xl);
  color: var(--text-color);
  margin-bottom: 12px;
}

.empty-state p {
  color: var(--text-secondary);
  font-size: var(--font-size);
}
</style>
