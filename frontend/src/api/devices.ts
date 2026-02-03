import api from './index'

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

export const deviceAPI = {
  async getDevices(): Promise<Device[]> {
    return api.get('/devices')
  },

  async getDevice(id: string): Promise<Device> {
    return api.get(`/devices/${id}`)
  },

  async controlDevice(id: string, command: string, parameters?: Record<string, any>): Promise<any> {
    return api.post(`/devices/${id}/control`, { command, parameters })
  },

  async getDeviceState(id: string): Promise<Record<string, any>> {
    return api.get(`/devices/${id}/state`)
  },

  async setDeviceState(id: string, state: Record<string, any>): Promise<any> {
    return api.put(`/devices/${id}/state`, state)
  }
}
