import api from './index'

export interface Automation {
  id: string
  name: string
  description?: string
  enabled: boolean
  triggers: any[]
  actions: any[]
  lastTriggered?: string
  triggerCount?: number
}

export const automationAPI = {
  async getAutomations(): Promise<Automation[]> {
    return api.get('/automations')
  },

  async getAutomation(id: string): Promise<Automation> {
    return api.get(`/automations/${id}`)
  },

  async createAutomation(automation: Partial<Automation>): Promise<Automation> {
    return api.post('/automations', automation)
  },

  async updateAutomation(id: string, automation: Partial<Automation>): Promise<Automation> {
    return api.put(`/automations/${id}`, automation)
  },

  async deleteAutomation(id: string): Promise<void> {
    return api.delete(`/automations/${id}`)
  },

  async triggerAutomation(id: string): Promise<any> {
    return api.post(`/automations/${id}/trigger`)
  },

  async toggleAutomation(id: string, enabled: boolean): Promise<Automation> {
    return api.put(`/automations/${id}`, { enabled })
  }
}
