import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('@/views/HomeView.vue')
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('@/views/DashboardView.vue')
    },
    {
      path: '/devices',
      name: 'devices',
      component: () => import('@/views/DevicesView.vue')
    },
    {
      path: '/automations',
      name: 'automations',
      component: () => import('@/views/AutomationsView.vue')
    },
    {
      path: '/scenarios',
      name: 'scenarios',
      component: () => import('@/views/ScenariosView.vue')
    },
    {
      path: '/integrations',
      name: 'integrations',
      component: () => import('@/views/IntegrationsView.vue')
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('@/views/SettingsView.vue')
    },
    {
      path: '/vision',
      name: 'vision',
      component: () => import('@/views/VisionView.vue')
    }
  ]
})

export default router
