<template>
  <div class="settings-view">
    <h1 class="page-title">设置</h1>

    <div class="settings-container">
      <div class="settings-sidebar">
        <button
          v-for="section in sections"
          :key="section.id"
          class="section-btn"
          :class="{ active: activeSection === section.id }"
          @click="activeSection = section.id"
        >
          {{ section.label }}
        </button>
      </div>

      <div class="settings-content">
        <div v-if="activeSection === 'general'" class="settings-section">
          <h2>通用设置</h2>
          <div class="setting-item">
            <label>系统名称</label>
            <input v-model="settings.general.name" type="text" class="setting-input" />
          </div>
          <div class="setting-item">
            <label>语言</label>
            <select v-model="settings.general.language" class="setting-input">
              <option value="zh-CN">简体中文</option>
              <option value="en-US">English</option>
            </select>
          </div>
          <div class="setting-item">
            <label>时区</label>
            <select v-model="settings.general.timezone" class="setting-input">
              <option value="Asia/Shanghai">Asia/Shanghai</option>
              <option value="America/New_York">America/New_York</option>
            </select>
          </div>
        </div>

        <div v-if="activeSection === 'voice'" class="settings-section">
          <h2>语音设置</h2>
          <div class="setting-item">
            <label>唤醒词</label>
            <input v-model="settings.voice.wakeWord" type="text" class="setting-input" />
          </div>
          <div class="setting-item">
            <label>语音识别引擎</label>
            <select v-model="settings.voice.engine" class="setting-input">
              <option value="openai-whisper">OpenAI Whisper</option>
              <option value="google-speech">Google Speech</option>
            </select>
          </div>
          <div class="setting-item">
            <label>语音合成引擎</label>
            <select v-model="settings.voice.ttsEngine" class="setting-input">
              <option value="azure-tts">Azure TTS</option>
              <option value="google-tts">Google TTS</option>
            </select>
          </div>
        </div>

        <div v-if="activeSection === 'notifications'" class="settings-section">
          <h2>通知设置</h2>
          <div class="setting-item">
            <label class="setting-checkbox">
              <input v-model="settings.notifications.pushEnabled" type="checkbox" />
              <span>启用推送通知</span>
            </label>
          </div>
          <div class="setting-item">
            <label class="setting-checkbox">
              <input v-model="settings.notifications.emailEnabled" type="checkbox" />
              <span>启用邮件通知</span>
            </label>
          </div>
          <div class="setting-item">
            <label>邮件地址</label>
            <input v-model="settings.notifications.email" type="email" class="setting-input" />
          </div>
        </div>

        <div class="settings-actions">
          <button class="btn btn-primary" @click="saveSettings">
            保存设置
          </button>
          <button class="btn btn-secondary" @click="resetSettings">
            重置默认
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useAppStore } from '@/stores/app'

const store = useAppStore()

const activeSection = ref('general')

const sections = [
  { id: 'general', label: '通用' },
  { id: 'voice', label: '语音' },
  { id: 'notifications', label: '通知' },
  { id: 'security', label: '安全' },
  { id: 'advanced', label: '高级' }
]

const settings = ref({
  general: {
    name: '智慧管家',
    language: 'zh-CN',
    timezone: 'Asia/Shanghai'
  },
  voice: {
    wakeWord: '管家',
    engine: 'openai-whisper',
    ttsEngine: 'azure-tts'
  },
  notifications: {
    pushEnabled: true,
    emailEnabled: false,
    email: ''
  }
})

function saveSettings() {
  store.addNotification('设置已保存', 'success')
}

function resetSettings() {
  if (confirm('确定要重置所有设置为默认值吗?')) {
    store.addNotification('设置已重置', 'info')
  }
}
</script>

<style scoped>
.settings-view {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.page-title {
  font-size: var(--font-size-xl);
  margin-bottom: 24px;
  color: var(--text-color);
}

.settings-container {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 24px;
}

.settings-sidebar {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-btn {
  padding: 12px 16px;
  border: none;
  background: none;
  text-align: left;
  border-radius: var(--radius);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.section-btn:hover {
  background-color: var(--bg-color);
  color: var(--text-color);
}

.section-btn.active {
  background-color: var(--primary-color);
  color: white;
}

.settings-content {
  background-color: var(--card-bg);
  border-radius: var(--radius-md);
  padding: 24px;
  box-shadow: var(--shadow);
}

.settings-section {
  margin-bottom: 24px;
}

.settings-section h2 {
  font-size: var(--font-size-lg);
  color: var(--text-color);
  margin-bottom: 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-color);
}

.setting-item {
  margin-bottom: 20px;
}

.setting-item label {
  display: block;
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.setting-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius);
  background-color: var(--bg-color);
  color: var(--text-color);
  font-size: var(--font-size-sm);
  transition: border-color 0.2s;
}

.setting-input:focus {
  outline: none;
  border-color: var(--primary-color);
}

.setting-checkbox {
  display: flex;
  align-items: center;
  gap: 12px;
  cursor: pointer;
}

.setting-checkbox input {
  width: 18px;
  height: 18px;
}

.setting-checkbox span {
  font-size: var(--font-size-sm);
  color: var(--text-color);
}

.settings-actions {
  display: flex;
  gap: 12px;
  padding-top: 24px;
  border-top: 1px solid var(--border-color);
}
</style>
