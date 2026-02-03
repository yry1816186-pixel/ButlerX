<template>
  <div class="devices-view">
    <div class="page-header">
      <h1 class="page-title">设备管理</h1>
      <button class="btn btn-primary" @click="refreshDevices">
        刷新
      </button>
    </div>

    <div class="filters">
      <select v-model="selectedType" class="filter-select" @change="filterDevices">
        <option value="">全部类型</option>
        <option v-for="type in deviceTypes" :key="type" :value="type">{{ type }}</option>
      </select>
      <select v-model="selectedLocation" class="filter-select" @change="filterDevices">
        <option value="">全部位置</option>
        <option v-for="location in locations" :key="location" :value="location">{{ location }}</option>
      </select>
    </div>

    <div class="devices-grid" v-if="!loading">
      <DeviceCard
        v-for="device in filteredDevices"
        :key="device.id"
        :device="device"
        @control="handleControl"
        @toggle="handleToggle"
      />
    </div>

    <div class="loading" v-else>
      <div class="skeleton" v-for="i in 6" :key="i" style="height: 200px; border-radius: 12px;"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import DeviceCard from '@/components/devices/DeviceCard.vue'
import type { Device } from '@/stores/app'

const store = useAppStore()

const loading = ref(false)
const selectedType = ref('')
const selectedLocation = ref('')

const devices = computed(() => store.devices)
const filteredDevices = computed(() => {
  let result = devices.value
  if (selectedType.value) {
    result = result.filter(d => d.type === selectedType.value)
  }
  if (selectedLocation.value) {
    result = result.filter(d => d.location === selectedLocation.value)
  }
  return result
})

const deviceTypes = computed(() => [...new Set(devices.value.map(d => d.type))])
const locations = computed(() => [...new Set(devices.value.map(d => d.location))])

async function refreshDevices() {
  loading.value = true
  try {
    await new Promise(resolve => setTimeout(resolve, 500))
    store.addNotification('设备列表已刷新', 'success')
  } catch (error) {
    store.addNotification('刷新失败', 'error')
  } finally {
    loading.value = false
  }
}

function filterDevices() {
}

function handleControl(device: Device, command: string) {
  store.addNotification(`已控制设备: ${device.name} - ${command}`, 'success')
}

function handleToggle(device: Device) {
  store.addNotification(`已切换设备: ${device.name}`, 'success')
}

onMounted(() => {
  refreshDevices()
})
</script>

<style scoped>
.devices-view {
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

.filters {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.filter-select {
  padding: 10px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background-color: var(--card-bg);
  color: var(--text-color);
  font-size: var(--font-size-sm);
}

.devices-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}

.loading {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
}
</style>
