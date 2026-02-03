<template>
  <div class="home-view">
    <section class="hero">
      <h1 class="hero-title">欢迎使用智慧管家</h1>
      <p class="hero-subtitle">您的智能家居控制中心</p>
      <div class="hero-actions">
        <RouterLink to="/dashboard" class="btn btn-primary">进入仪表盘</RouterLink>
        <RouterLink to="/devices" class="btn btn-secondary">管理设备</RouterLink>
      </div>
    </section>

    <section class="features">
      <div class="feature-grid">
        <div class="feature-card" v-for="feature in features" :key="feature.title">
          <div class="feature-icon">{{ feature.icon }}</div>
          <h3 class="feature-title">{{ feature.title }}</h3>
          <p class="feature-description">{{ feature.description }}</p>
        </div>
      </div>
    </section>

    <section class="stats">
      <div class="stat-grid">
        <div class="stat-item">
          <div class="stat-value">{{ stats.devices }}</div>
          <div class="stat-label">设备</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ stats.automations }}</div>
          <div class="stat-label">自动化</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ stats.scenarios }}</div>
          <div class="stat-label">场景</div>
        </div>
        <div class="stat-item">
          <div class="stat-value">{{ stats.integrations }}</div>
          <div class="stat-label">集成</div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { RouterLink } from 'vue-router'

const features = [
  {
    icon: '🏠',
    title: '智能设备控制',
    description: '统一管理所有智能家居设备，随时随地控制'
  },
  {
    icon: '⚡',
    title: '自动化规则',
    description: '设置自动化规则，让智能设备自动响应'
  },
  {
    icon: '🎭',
    title: '场景模式',
    description: '一键切换不同场景，享受定制化体验'
  },
  {
    icon: '🔌',
    title: '第三方集成',
    description: '支持多种智能平台，扩展无限可能'
  },
  {
    icon: '👁️',
    title: '视觉识别',
    description: '基于AI的视觉系统，智能感知环境'
  },
  {
    icon: '🤖',
    title: '语音交互',
    description: '自然语言对话，智能助手随时待命'
  }
]

const stats = ref({
  devices: 0,
  automations: 0,
  scenarios: 0,
  integrations: 0
})
</script>

<style scoped>
.home-view {
  padding: 40px 0;
}

.hero {
  text-align: center;
  padding: 80px 20px;
  background: linear-gradient(135deg, var(--primary-color) 0%, var(--secondary-color) 100%);
  color: white;
  border-radius: var(--radius-lg);
  margin-bottom: 60px;
}

.hero-title {
  font-size: var(--font-size-2xl);
  margin-bottom: 16px;
}

.hero-subtitle {
  font-size: var(--font-size-lg);
  opacity: 0.9;
  margin-bottom: 32px;
}

.hero-actions {
  display: flex;
  gap: 16px;
  justify-content: center;
}

.hero-actions .btn {
  color: white;
  text-decoration: none;
}

.features {
  margin-bottom: 60px;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 24px;
}

.feature-card {
  background-color: var(--card-bg);
  padding: 32px;
  border-radius: var(--radius-md);
  text-align: center;
  transition: transform 0.2s, box-shadow 0.2s;
}

.feature-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg);
}

.feature-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.feature-title {
  font-size: var(--font-size-lg);
  margin-bottom: 12px;
  color: var(--text-color);
}

.feature-description {
  color: var(--text-secondary);
  font-size: var(--font-size);
}

.stats {
  background-color: var(--card-bg);
  padding: 40px;
  border-radius: var(--radius-md);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 32px;
  text-align: center;
}

.stat-item {
  padding: 20px;
}

.stat-value {
  font-size: var(--font-size-2xl);
  font-weight: 700;
  color: var(--primary-color);
  margin-bottom: 8px;
}

.stat-label {
  font-size: var(--font-size);
  color: var(--text-secondary);
}
</style>
