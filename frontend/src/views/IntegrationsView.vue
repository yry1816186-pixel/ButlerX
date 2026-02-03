<template>
  <div class="integrations-view">
    <div class="page-header">
      <h1 class="page-title">第三方集成</h1>
    </div>

    <div class="integrations-grid">
      <IntegrationCard
        v-for="integration in integrations"
        :key="integration.id"
        :integration="integration"
        @connect="handleConnect"
        @disconnect="handleDisconnect"
        @configure="handleConfigure"
      />
    </div>

    <div class="add-integration">
      <button class="btn btn-primary" @click="showAddDialog = true">
        + 添加集成
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useAppStore } from '@/stores/app'
import IntegrationCard from '@/components/integrations/IntegrationCard.vue'
import type { Integration } from '@/stores/app'

const store = useAppStore()
const showAddDialog = ref(false)

const integrations = computed(() => store.integrations)

function handleConnect(integration: Integration) {
  store.addNotification(`正在连接: ${integration.name}`, 'info')
}

function handleDisconnect(integration: Integration) {
  store.addNotification(`已断开: ${integration.name}`, 'success')
}

function handleConfigure(integration: Integration) {
  store.addNotification(`配置功能开发中: ${integration.name}`, 'info')
}
</script>

<style scoped>
.integrations-view {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.page-header {
  margin-bottom: 24px;
}

.page-title {
  font-size: var(--font-size-xl);
  color: var(--text-color);
}

.integrations-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  margin-bottom: 24px;
}

.add-integration {
  text-align: center;
  padding: 40px;
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-md);
}

.add-integration .btn {
  min-width: 200px;
}
</style>
