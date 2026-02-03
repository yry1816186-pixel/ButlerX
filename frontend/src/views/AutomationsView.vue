<template>
  <div class="automations-view">
    <div class="page-header">
      <h1 class="page-title">自动化</h1>
      <button class="btn btn-primary" @click="showCreateDialog = true">
        新建自动化
      </button>
    </div>

    <div class="automations-list">
      <AutomationCard
        v-for="automation in automations"
        :key="automation.id"
        :automation="automation"
        @toggle="handleToggle"
        @trigger="handleTrigger"
        @edit="handleEdit"
        @delete="handleDelete"
      />
    </div>

    <div class="empty-state" v-if="automations.length === 0">
      <div class="empty-icon">⚡</div>
      <h2>暂无自动化</h2>
      <p>点击"新建自动化"开始创建您的第一个自动化规则</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import AutomationCard from '@/components/automations/AutomationCard.vue'
import type { Automation } from '@/stores/app'

const store = useAppStore()
const showCreateDialog = ref(false)

const automations = computed(() => store.automations)

function handleToggle(automation: Automation) {
  store.updateAutomation(automation.id, { enabled: !automation.enabled })
  store.addNotification(
    `自动化 "${automation.name}" 已${automation.enabled ? '禁用' : '启用'}`,
    'success'
  )
}

function handleTrigger(automation: Automation) {
  store.addNotification(`正在触发自动化: ${automation.name}`, 'info')
}

function handleEdit(automation: Automation) {
  store.addNotification(`编辑功能开发中: ${automation.name}`, 'info')
}

function handleDelete(automation: Automation) {
  if (confirm(`确定要删除自动化 "${automation.name}" 吗?`)) {
    store.addNotification(`自动化已删除: ${automation.name}`, 'success')
  }
}

onMounted(() => {
})
</script>

<style scoped>
.automations-view {
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

.automations-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
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
