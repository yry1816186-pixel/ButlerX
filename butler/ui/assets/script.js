class SmartButlerUI {
  constructor() {
    this.websocket = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectDelay = 3000;
    this.init();
  }

  init() {
    this.initParticles();
    this.initScanLine();
    this.initWebSocket();
    this.initDragAndDrop();
    this.initMagneticButtons();
    this.initTooltips();
    this.initRippleEffects();
    this.initSmoothScroll();
    this.initIntersectionObserver();
  }

  initParticles() {
    const particleContainer = document.createElement('div');
    particleContainer.className = 'particles';
    document.body.prepend(particleContainer);

    for (let i = 0; i < 30; i++) {
      const particle = document.createElement('div');
      particle.className = 'particle';
      particle.style.left = Math.random() * 100 + '%';
      particle.style.animationDelay = Math.random() * 15 + 's';
      particle.style.animationDuration = (15 + Math.random() * 10) + 's';
      particleContainer.appendChild(particle);
    }
  }

  initScanLine() {
    if (!document.querySelector('.scan-line')) {
      const scanLine = document.createElement('div');
      scanLine.className = 'scan-line';
      document.body.appendChild(scanLine);
    }
  }

  initWebSocket() {
    const wsUrl = 'ws://localhost:8765/ws';
    
    try {
      this.websocket = new WebSocket(wsUrl);
      
      this.websocket.onopen = () => {
        console.log('WebSocket connected');
        this.reconnectAttempts = 0;
        this.showNotification('WebSocket连接成功', 'success');
      };
      
      this.websocket.onmessage = (event) => {
        this.handleWebSocketMessage(JSON.parse(event.data));
      };
      
      this.websocket.onclose = () => {
        console.log('WebSocket disconnected');
        this.attemptReconnect();
      };
      
      this.websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        this.showNotification('WebSocket连接错误', 'error');
      };
    } catch (error) {
      console.error('Failed to create WebSocket:', error);
    }
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = this.reconnectDelay * this.reconnectAttempts;
      
      this.showNotification(`正在尝试重新连接... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`, 'warning');
      
      setTimeout(() => {
        this.initWebSocket();
      }, delay);
    } else {
      this.showNotification('WebSocket连接失败，请刷新页面', 'error');
    }
  }

  handleWebSocketMessage(data) {
    switch (data.type) {
      case 'device_update':
        this.updateDeviceState(data);
        break;
      case 'scene_activated':
        this.showNotification(`场景 "${data.scene}" 已激活`, 'success');
        break;
      case 'ai_response':
        this.displayAIResponse(data);
        break;
      case 'system_status':
        this.updateSystemStatus(data);
        break;
      case 'log_entry':
        this.addLogEntry(data);
        break;
      default:
        console.log('Unknown message type:', data.type);
    }
  }

  sendWebSocketMessage(message) {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      this.websocket.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected');
    }
  }

  initDragAndDrop() {
    const draggables = document.querySelectorAll('.drag-handle');
    
    draggables.forEach(handle => {
      let isDragging = false;
      let startX, startY, initialX, initialY;
      let element = handle.closest('.card');
      
      handle.addEventListener('mousedown', (e) => {
        isDragging = true;
        startX = e.clientX;
        startY = e.clientY;
        const rect = element.getBoundingClientRect();
        initialX = rect.left;
        initialY = rect.top;
        element.style.zIndex = '1000';
        element.style.cursor = 'grabbing';
      });
      
      document.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        
        const dx = e.clientX - startX;
        const dy = e.clientY - startY;
        
        element.style.position = 'relative';
        element.style.left = `${dx}px`;
        element.style.top = `${dy}px`;
      });
      
      document.addEventListener('mouseup', () => {
        if (!isDragging) return;
        
        isDragging = false;
        element.style.zIndex = '';
        element.style.cursor = '';
      });
    });

    this.initSortableLists();
  }

  initSortableLists() {
    const sortableLists = document.querySelectorAll('.device-grid, .scene-grid');
    
    sortableLists.forEach(list => {
      let draggedItem = null;
      
      list.addEventListener('dragstart', (e) => {
        if (e.target.classList.contains('device-card') || e.target.classList.contains('scene-card')) {
          draggedItem = e.target;
          e.target.style.opacity = '0.5';
        }
      });
      
      list.addEventListener('dragend', (e) => {
        if (e.target.classList.contains('device-card') || e.target.classList.contains('scene-card')) {
          e.target.style.opacity = '1';
          draggedItem = null;
        }
      });
      
      list.addEventListener('dragover', (e) => {
        e.preventDefault();
        const afterElement = this.getDragAfterElement(list, e.clientY);
        if (afterElement == null) {
          list.appendChild(draggedItem);
        } else {
          list.insertBefore(draggedItem, afterElement);
        }
      });
    });
  }

  getDragAfterElement(container, y) {
    const draggableElements = [...container.querySelectorAll('.device-card:not(.dragging), .scene-card:not(.dragging)')];
    
    return draggableElements.reduce((closest, child) => {
      const box = child.getBoundingClientRect();
      const offset = y - box.top - box.height / 2;
      
      if (offset < 0 && offset > closest.offset) {
        return { offset: offset, element: child };
      } else {
        return closest;
      }
    }, { offset: Number.NEGATIVE_INFINITY }).element;
  }

  initMagneticButtons() {
    const buttons = document.querySelectorAll('.btn-primary, .btn-secondary, .quick-btn');
    
    buttons.forEach(button => {
      button.addEventListener('mousemove', (e) => {
        const rect = button.getBoundingClientRect();
        const x = e.clientX - rect.left - rect.width / 2;
        const y = e.clientY - rect.top - rect.height / 2;
        
        button.style.transform = `translate(${x * 0.1}px, ${y * 0.1}px)`;
      });
      
      button.addEventListener('mouseleave', () => {
        button.style.transform = 'translate(0, 0)';
      });
    });
  }

  initTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    
    tooltips.forEach(tooltip => {
      tooltip.addEventListener('mouseenter', () => {
        const tip = document.createElement('div');
        tip.className = 'tooltip-popup';
        tip.textContent = tooltip.getAttribute('data-tooltip');
        tip.style.position = 'absolute';
        tip.style.background = 'var(--bg-card)';
        tip.style.border = '1px solid var(--border-glow)';
        tip.style.padding = '8px 16px';
        tip.style.borderRadius = '8px';
        tip.style.fontSize = '12px';
        tip.style.color = 'var(--text-primary)';
        tip.style.zIndex = '10000';
        tip.style.whiteSpace = 'nowrap';
        document.body.appendChild(tip);
        
        const rect = tooltip.getBoundingClientRect();
        tip.style.top = rect.bottom + 8 + 'px';
        tip.style.left = rect.left + rect.width / 2 - tip.offsetWidth / 2 + 'px';
        
        tooltip.dataset.tooltipElement = tip.outerHTML;
        setTimeout(() => tip.remove(), 0);
      });
    });
  }

  initRippleEffects() {
    const buttons = document.querySelectorAll('button');
    
    buttons.forEach(button => {
      button.addEventListener('click', (e) => {
        const ripple = document.createElement('span');
        ripple.style.position = 'absolute';
        ripple.style.borderRadius = '50%';
        ripple.style.background = 'rgba(255, 255, 255, 0.3)';
        ripple.style.transform = 'scale(0)';
        ripple.style.animation = 'ripple 0.6s linear';
        ripple.style.pointerEvents = 'none';
        
        const rect = button.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        ripple.style.width = ripple.style.height = size + 'px';
        ripple.style.left = e.clientX - rect.left - size / 2 + 'px';
        ripple.style.top = e.clientY - rect.top - size / 2 + 'px';
        
        button.appendChild(ripple);
        
        setTimeout(() => ripple.remove(), 600);
      });
    });

    if (!document.querySelector('#ripple-style')) {
      const style = document.createElement('style');
      style.id = 'ripple-style';
      style.textContent = `
        @keyframes ripple {
          to {
            transform: scale(4);
            opacity: 0;
          }
        }
      `;
      document.head.appendChild(style);
    }
  }

  initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
      anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
          target.scrollIntoView({
            behavior: 'smooth',
            block: 'start'
          });
        }
      });
    });
  }

  initIntersectionObserver() {
    const observerOptions = {
      threshold: 0.1,
      rootMargin: '0px 0px -50px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('animate-in');
          observer.unobserve(entry.target);
        }
      });
    }, observerOptions);
    
    document.querySelectorAll('.card, .device-card, .scene-card, .feature-card').forEach(el => {
      observer.observe(el);
    });
  }

  updateDeviceState(data) {
    const deviceCard = document.querySelector(`[data-device-id="${data.device_id}"]`);
    if (deviceCard) {
      const statusElement = deviceCard.querySelector('.device-status');
      if (statusElement) {
        statusElement.textContent = data.state ? '已开启' : '已关闭';
      }
      
      if (data.state) {
        deviceCard.classList.add('active');
      } else {
        deviceCard.classList.remove('active');
      }
    }
  }

  displayAIResponse(data) {
    const responseContainer = document.getElementById('ai-response-container');
    if (responseContainer) {
      responseContainer.innerHTML = data.response;
      responseContainer.classList.add('animate-in');
    }
  }

  updateSystemStatus(data) {
    Object.keys(data).forEach(key => {
      const element = document.getElementById(`stat-${key}`);
      if (element) {
        element.textContent = data[key];
      }
    });
  }

  addLogEntry(data) {
    const logContainer = document.getElementById('activity-log');
    if (logContainer) {
      const logEntry = document.createElement('div');
      logEntry.className = 'log-entry animate-in';
      
      const typeNames = {
        'ai': 'AI引擎',
        'vision': '视觉系统',
        'device': '设备控制',
        'security': '安全',
        'system': '系统'
      };
      
      logEntry.innerHTML = `
        <span class="log-time">刚刚</span>
        <span class="log-level ${data.level}">${data.level.toUpperCase()}</span>
        <span class="log-message">${data.message}</span>
      `;
      
      logContainer.insertBefore(logEntry, logContainer.firstChild);
      
      if (logContainer.children.length > 10) {
        logContainer.removeChild(logContainer.lastChild);
      }
    }
  }

  showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
      <span>${this.getNotificationIcon(type)}</span>
      <span>${message}</span>
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => notification.classList.add('show'), 10);
    
    setTimeout(() => {
      notification.classList.remove('show');
      setTimeout(() => notification.remove(), 400);
    }, 3000);
  }

  getNotificationIcon(type) {
    const icons = {
      'success': '✅',
      'error': '❌',
      'warning': '⚠️',
      'info': '💡'
    };
    return icons[type] || '💡';
  }

  simulateRealTimeData() {
    setInterval(() => {
      this.updateRandomStats();
    }, 5000);
  }

  updateRandomStats() {
    const statElements = document.querySelectorAll('.card-value');
    
    statElements.forEach(stat => {
      const text = stat.textContent;
      if (!text.includes('%')) {
        const currentValue = parseInt(text.replace(/,/g, ''));
        const change = Math.floor(Math.random() * 5) - 2;
        const newValue = Math.max(0, currentValue + change);
        stat.textContent = newValue.toLocaleString();
      }
    });
  }

  initVoiceCommands() {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognition = new SpeechRecognition();
      
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'zh-CN';
      
      recognition.onresult = (event) => {
        const transcript = Array.from(event.results)
          .map(result => result[0].transcript)
          .join('');
        
        this.displayVoiceTranscript(transcript);
        
        if (event.results[event.results.length - 1].isFinal) {
          this.processVoiceCommand(transcript);
        }
      };
      
      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        this.showNotification('语音识别错误', 'error');
      };
      
      this.recognition = recognition;
    } else {
      console.warn('Speech recognition not supported');
    }
  }

  startVoiceRecognition() {
    if (this.recognition) {
      this.recognition.start();
      this.showNotification('语音识别已启动', 'info');
    }
  }

  stopVoiceRecognition() {
    if (this.recognition) {
      this.recognition.stop();
      this.showNotification('语音识别已停止', 'info');
    }
  }

  displayVoiceTranscript(transcript) {
    const transcriptContainer = document.getElementById('voice-transcript');
    if (transcriptContainer) {
      transcriptContainer.textContent = transcript;
    }
  }

  processVoiceCommand(command) {
    this.showNotification(`正在处理语音指令: "${command}"`, 'info');
    
    setTimeout(() => {
      this.showNotification('语音指令已执行', 'success');
    }, 1500);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.smartButlerUI = new SmartButlerUI();
});

function showNotification(message, type = 'info') {
  if (window.smartButlerUI) {
    window.smartButlerUI.showNotification(message, type);
  }
}

function updateDeviceState(deviceId, state) {
  const deviceCard = document.querySelector(`[data-device-id="${deviceId}"]`);
  if (deviceCard) {
    const statusElement = deviceCard.querySelector('.device-status');
    if (statusElement) {
      statusElement.textContent = state ? '已开启' : '已关闭';
    }
    
    if (state) {
      deviceCard.classList.add('active');
    } else {
      deviceCard.classList.remove('active');
    }
  }
}

function activateScene(sceneId) {
  showNotification(`正在激活场景...`, 'info');
  
  setTimeout(() => {
    showNotification('场景已激活', 'success');
  }, 1500);
}

function toggleDevice(card) {
  card.classList.toggle('active');
  const name = card.querySelector('.device-name').textContent;
  const isActive = card.classList.contains('active');
  const statusText = card.querySelector('.device-status');
  
  if (isActive) {
    statusText.textContent = '已开启';
  } else {
    statusText.textContent = '已关闭';
  }
  
  showNotification(`${name} 已${isActive ? '开启' : '关闭'}`, 'success');
}