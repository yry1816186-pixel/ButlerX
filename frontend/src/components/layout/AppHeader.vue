<template>
  <header class="app-header">
    <div class="header-left">
      <button class="menu-btn" @click="toggleSidebar">
        <span class="hamburger"></span>
      </button>
      <h1 class="app-title">智慧管家</h1>
    </div>
    <nav class="header-nav">
      <RouterLink v-for="route in routes" :key="route.path" :to="route.path" class="nav-link">
        {{ route.meta?.title || route.name }}
      </RouterLink>
    </nav>
    <div class="header-right">
      <button class="icon-btn" @click="showNotifications">
        <span class="notification-badge" v-if="notifications.length > 0">{{ notifications.length }}</span>
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
        </svg>
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { useAppStore } from '@/stores/app'

const store = useAppStore()

const routes = [
  { path: '/dashboard', name: '仪表盘', meta: { title: 'Dashboard' } },
  { path: '/devices', name: '设备', meta: { title: 'Devices' } },
  { path: '/automations', name: '自动化', meta: { title: 'Automations' } },
  { path: '/scenarios', name: '场景', meta: { title: 'Scenarios' } },
  { path: '/integrations', name: '集成', meta: { title: 'Integrations' } }
]

const { notifications } = store

function toggleSidebar() {
  store.toggleSidebar()
}

function showNotifications() {
  store.addNotification('通知功能开发中', 'info')
}
</script>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px;
  background-color: var(--card-bg);
  border-bottom: 1px solid var(--border-color);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.menu-btn {
  background: none;
  border: none;
  padding: 8px;
  cursor: pointer;
}

.hamburger {
  display: block;
  width: 24px;
  height: 2px;
  background-color: var(--text-color);
  position: relative;
}

.hamburger::before,
.hamburger::after {
  content: '';
  position: absolute;
  width: 24px;
  height: 2px;
  background-color: var(--text-color);
  left: 0;
}

.hamburger::before {
  top: -8px;
}

.hamburger::after {
  top: 8px;
}

.app-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--primary-color);
}

.header-nav {
  display: flex;
  gap: 8px;
}

.nav-link {
  padding: 8px 16px;
  border-radius: var(--radius);
  color: var(--text-secondary);
  transition: all 0.2s;
}

.nav-link:hover {
  background-color: var(--bg-color);
  color: var(--text-color);
}

.nav-link.router-link-active {
  background-color: var(--primary-color);
  color: white;
}

.header-right {
  display: flex;
  gap: 8px;
}

.icon-btn {
  background: none;
  border: none;
  padding: 8px;
  cursor: pointer;
  position: relative;
  color: var(--text-secondary);
  transition: color 0.2s;
}

.icon-btn:hover {
  color: var(--text-color);
}

.notification-badge {
  position: absolute;
  top: 4px;
  right: 4px;
  background-color: var(--danger-color);
  color: white;
  font-size: 10px;
  padding: 2px 5px;
  border-radius: 10px;
  min-width: 16px;
  text-align: center;
}
</style>
