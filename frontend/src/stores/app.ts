import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Device {
  id: string
  name: string
  type: string
  domain: string
  location: string
  status: 'online' | 'offline'
  state?: Record<string, any>
  attributes?: Record<string, any>
}

export interface Automation {
  id: string
  name: string
  description?: string
  enabled: boolean
  triggers: any[]
  actions: any[]
  lastTriggered?: string
}

export interface Scenario {
  id: string
  name: string
  type: string
  description?: string
  active: boolean
}

export interface Integration {
  id: string
  name: string
  type: string
  enabled: boolean
  connected: boolean
  config?: Record<string, any>
}

export const useAppStore = defineStore('app', () => {
  const loading = ref(false)
  const error = ref<string | null>(null)
  const sidebarOpen = ref(true)
  const notifications = ref<Array<{id: string, message: string, type: 'success' | 'error' | 'warning' | 'info'}>>([])

  const devices = ref<Device[]>([])
  const automations = ref<Automation[]>([])
  const scenarios = ref<Scenario[]>([])
  const integrations = ref<Integration[]>([])

  const onlineDevices = computed(() => devices.value.filter(d => d.status === 'online'))
  const enabledAutomations = computed(() => automations.value.filter(a => a.enabled))
  const activeScenarios = computed(() => scenarios.value.filter(s => s.active))
  const connectedIntegrations = computed(() => integrations.value.filter(i => i.connected))

  function setLoading(value: boolean) {
    loading.value = value
  }

  function setError(message: string | null) {
    error.value = message
  }

  function clearError() {
    error.value = null
  }

  function toggleSidebar() {
    sidebarOpen.value = !sidebarOpen.value
  }

  function addNotification(message: string, type: 'success' | 'error' | 'warning' | 'info' = 'info') {
    const id = Date.now().toString()
    notifications.value.push({ id, message, type })
    setTimeout(() => {
      removeNotification(id)
    }, 5000)
  }

  function removeNotification(id: string) {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index > -1) {
      notifications.value.splice(index, 1)
    }
  }

  function setDevices(newDevices: Device[]) {
    devices.value = newDevices
  }

  function updateDevice(id: string, updates: Partial<Device>) {
    const index = devices.value.findIndex(d => d.id === id)
    if (index > -1) {
      devices.value[index] = { ...devices.value[index], ...updates }
    }
  }

  function setAutomations(newAutomations: Automation[]) {
    automations.value = newAutomations
  }

  function updateAutomation(id: string, updates: Partial<Automation>) {
    const index = automations.value.findIndex(a => a.id === id)
    if (index > -1) {
      automations.value[index] = { ...automations.value[index], ...updates }
    }
  }

  function setScenarios(newScenarios: Scenario[]) {
    scenarios.value = newScenarios
  }

  function setIntegrations(newIntegrations: Integration[]) {
    integrations.value = newIntegrations
  }

  return {
    loading,
    error,
    sidebarOpen,
    notifications,
    devices,
    automations,
    scenarios,
    integrations,
    onlineDevices,
    enabledAutomations,
    activeScenarios,
    connectedIntegrations,
    setLoading,
    setError,
    clearError,
    toggleSidebar,
    addNotification,
    removeNotification,
    setDevices,
    updateDevice,
    setAutomations,
    updateAutomation,
    setScenarios,
    setIntegrations
  }
})
