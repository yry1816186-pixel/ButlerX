# DaShan与智慧管家集成指南

## 概述

本集成方案将DaShan桌面宠物机器人完全接入智慧管家系统，使智慧管家成为统一的智能中枢，可以监控、管理和控制DaShan机器人。

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    用户交互层                            │
│  Web UI + 语音 + 移动端 + DaShan实体交互            │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│              智慧管家系统                   │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  设备控制层                │     │
│  │  - HomeAssistant (HA设备)                   │     │
│  │  - 虚拟设备                                  │     │
│  │  - IR遥控器                                  │     │
│  │  - DaShan适配器 ← 新增                    │     │
│  └─────────────────────────────────────────────────────┘     │
│                         │ MQTT (1883)                   │
│  ┌────────────────▼─────────────────────────────────────┐     │
│  │  消息总线 (MQTT Broker)                      │     │
│  │  Topics:                                         │     │
│  │  - daShan/status       ← DaShan状态上报           │     │
│  │  - daShan/log          ← DaShan日志上报           │     │
│  │  - daShan/command      → 智慧管家控制DaShan       │     │
│  │  - daShan/image         → DaShan摄像头图像           │     │
│  └─────────────────────────────────────────────────────┘     │
└────────────────────┬────────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────────┐
│              DaShan系统 (主机端)                      │
│  ┌─────────────────────────────────────────────────────┐     │
│  │  MQTT客户端 ← 新增模块                          │     │
│  │  - 连接到智慧管家的MQTT                      │     │
│  │  - 状态上报 (实时)                             │     │
│  │  - 日志上报 (异步)                             │     │
│  │  - 命令订阅                                 │     │
│  └─────────────────────────────────────────────────────┘     │
│                         │ UART (115200)                   │
│  ┌────────────────▼─────────────────────────────────────┐     │
│  │  DaShan机器人端 (ESP32-S3)                   │     │
│  │  - LED矩阵眼睛                                 │     │
│  │  - 舵机控制                                   │     │
│  │  - 摄像头 + 传感器                           │     │
│  └─────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

## 新增文件清单

### 智慧管家端

1. **butler/devices/__init__.py** - 设备适配器包初始化
2. **butler/devices/dashan_adapter.py** - DaShan适配器实现
   - `DaShanConfig` - 配置数据类
   - `DaShanState` - 状态数据类
   - `DaShanLogEntry` - 日志条目数据类
   - `DaShanAdapter` - 主适配器类

### DaShan端

1. **DaShan/host/modules/protocol/mqtt_client.py** - MQTT客户端实现
   - `MQTTClientConfig` - MQTT配置数据类
   - `LogEntry` - 日志条目数据类
   - `DaShanMQTTClient` - MQTT客户端类

### 修改的文件

1. **butler/core/config.py** - 添加DaShan配置选项
2. **butler/core/service.py** - 集成DaShan适配器
3. **DaShan/host/main.py** - 添加MQTT客户端支持

## MQTT通信协议

### 1. 状态上报 (DaShan → 智慧管家)

**Topic**: `daShan/status`

**Payload**:
```json
{
  "timestamp": 1738467200,
  "state": "WAKE|LISTEN|THINK|TALK|SLEEP",
  "expression": 1,
  "emotion": {
    "type": "happy|sad|angry|surprised",
    "intensity": 0.85,
    "confidence": 0.92
  },
  "servo": {
    "horizontal": 45,
    "vertical": 30
  },
  "battery": 85,
  "proximity": true,
  "distance": 25.5,
  "light": 150
}
```

### 2. 日志上报 (DaShan → 智慧管家)

**Topic**: `daShan/log`

**Payload**:
```json
{
  "timestamp": 1738467200,
  "type": "interaction|behavior|system|error",
  "level": "INFO|WARNING|ERROR",
  "message": "用户说: '你好'",
  "context": {
    "user_input": "你好",
    "llm_response": "你好！有什么可以帮助你的吗？",
    "state_before": "SLEEP",
    "state_after": "TALK"
  }
}
```

### 3. 控制命令 (智慧管家 → DaShan)

**Topic**: `daShan/command`

**Payload**:
```json
{
  "command": "set_expression|set_servo|play_animation|speak|set_state",
  "params": {
    "expression_id": 5,
    "brightness": 255,
    "servo_h": 90,
    "servo_v": 45,
    "animation": "happy",
    "text": "欢迎回家！",
    "state": "WAKE"
  },
  "priority": "normal|high|urgent"
}
```

### 4. 图像数据 (DaShan → 智慧管家)

**Topic**: `daShan/image`

**Payload**:
```json
{
  "timestamp": 1738467200,
  "image": "base64_encoded_jpeg",
  "face_detected": true,
  "face_location": {"x": 320, "y": 240}
}
```

## 配置说明

### 智慧管家配置 (butler/config.json)

```json
{
  "dashan": {
    "enabled": true,
    "mqtt_host": "localhost",
    "mqtt_port": 1883,
    "mqtt_username": null,
    "mqtt_password": null
  }
}
```

### 环境变量配置

```bash
# DaShan集成开关
DASHAN_ENABLED=true

# DaShan MQTT连接配置
DASHAN_MQTT_HOST=localhost
DASHAN_MQTT_PORT=1883
DASHAN_MQTT_USERNAME=
DASHAN_MQTT_PASSWORD=
```

### DaShan主机配置 (命令行参数)

```bash
# 启动DaShan并连接到智慧管家MQTT
python host/main.py \
  --port COM3 \
  --api-key YOUR_GLM_API_KEY \
  --mqtt-host localhost \
  --mqtt-port 1883
```

## 使用场景

### 场景1: 状态监控

智慧管家可以实时监控DaShan的状态：
- 当前状态 (睡眠/唤醒/聆听/思考/对话)
- 表情ID和表情名称
- 情绪类型和强度
- 舵机位置 (水平/垂直)
- 电池电量
- 传感器数据 (距离/光线)

**事件流**:
```
DaShan状态变化 → MQTT上报 → 智慧管家接收 → 转换为事件 → 存储数据库 → 推送到UI
```

### 场景2: 日志追踪

所有DaShan的交互都会被记录：
- 用户输入的语音
- LLM的回复
- 状态转换
- 动画播放
- 错误信息

**事件流**:
```
DaShan交互 → 生成日志 → MQTT上报 → 智慧管家接收 → 存储数据库
```

### 场景3: 远程控制

智慧管家可以远程控制DaShan：
- 设置表情
- 控制舵机
- 播放动画
- 语音播放
- 设置状态

**事件流**:
```
智慧管家发送命令 → MQTT发布 → DaShan接收 → 执行命令 → 记录日志
```

### 场景4: 智能联动

DaShan与智慧管家的其他功能联动：
- **回家场景**: 智慧管家激活回家场景 → 控制灯光/温度 → 让DaShan播放欢迎动画和语音
- **睡眠场景**: 智慧管家激活睡眠场景 → 关闭所有设备 → 让DaShan进入睡眠模式
- **异常检测**: 智慧管家检测到异常 → 通知DaShan显示担忧表情
- **访客识别**: 摄像头识别到访客 → DaShan显示好奇表情并播放欢迎语音

## DaShan适配器API

### 状态管理

```python
# 获取当前状态
state = adapter.get_current_state()

# 获取状态摘要
summary = adapter.get_state_summary()
```

### 日志管理

```python
# 获取最近的日志
logs = adapter.get_recent_logs(limit=50)

# 按类型获取日志
interaction_logs = adapter.get_logs_by_type("interaction", limit=20)
error_logs = adapter.get_logs_by_level("ERROR", limit=10)

# 清空日志队列
adapter.clear_logs()
```

### 控制命令

```python
# 设置表情
adapter.set_expression(expression_id=5, brightness=255)

# 控制舵机
adapter.set_servo(horizontal=90, vertical=45)

# 播放动画
adapter.play_animation("happy")

# 语音播放
adapter.speak("欢迎回家！")

# 设置状态
adapter.set_state("WAKE")
```

### 事件回调

```python
# 状态更新回调
def on_status_update(state):
    print(f"State changed to: {state.state}")

adapter.on_status_update(on_status_update)

# 日志条目回调
def on_log_entry(log):
    print(f"New log: {log.message}")

adapter.on_log_entry(on_log_entry)

# 图像数据回调
def on_image_data(image_base64):
    print(f"Received image: {len(image_base64)} bytes")

adapter.on_image_data(on_image_data)
```

## MQTT客户端API (DaShan端)

### 状态上报

```python
# 更新状态
mqtt_client.update_state("WAKE", expression=1)

# 更新表情
mqtt_client.update_expression(expression_id=5, brightness=255)

# 更新情绪
mqtt_client.update_emotion("happy", intensity=0.85, confidence=0.92)

# 更新舵机
mqtt_client.update_servo(horizontal=90, vertical=45)

# 更新传感器
mqtt_client.update_sensors(proximity=True, distance=25.5, light=150)
```

### 日志上报

```python
# 添加日志
mqtt_client.add_log(
    log_type="interaction",
    level="INFO",
    message="用户说: 你好",
    context={"user_input": "你好"}
)
```

### 图像上报

```python
# 发布图像
mqtt_client.publish_image(
    image_base64="base64_encoded_jpeg",
    face_detected=True,
    face_location={"x": 320, "y": 240}
)
```

## 智慧管家事件类型

### DaShan相关事件

| 事件类型 | 描述 | 严重性 |
|---------|------|---------|
| `dashan_status` | DaShan状态更新 | 0 |
| `dashan_interaction` | 用户交互记录 | 0-2 |
| `dashan_behavior` | 行为记录 | 0-2 |
| `dashan_system` | 系统日志 | 0-2 |
| `dashan_error` | 错误日志 | 2 |
| `dashan_image` | 摄像头图像 | 0 |

## 启动步骤

### 1. 启动MQTT Broker

如果使用本地MQTT：
```bash
# 使用Docker运行Mosquitto
docker run -d -p 1883:1883 eclipse-mosquitto
```

### 2. 启动智慧管家

```bash
cd c:\Users\RichardYuan\Desktop\智慧管家
python -m butler.core.main
```

### 3. 启动DaShan

```bash
cd c:\Users\RichardYuan\Desktop\智慧管家\DaShan
python host/main.py \
  --port COM3 \
  --api-key YOUR_GLM_API_KEY \
  --mqtt-host localhost \
  --mqtt-port 1883
```

### 4. 验证连接

检查智慧管家日志：
```
INFO - DaShan adapter initialized
INFO - DaShan adapter connected to MQTT broker
```

检查DaShan日志：
```
INFO - DaShan MQTT connected to broker
INFO - Subscribed to command topic: daShan/command
```

## 高级功能

### 智能场景联动

智慧管家可以创建包含DaShan动作的场景：

```json
{
  "scene_id": "welcome_home",
  "name": "回家欢迎",
  "actions": [
    {
      "action_type": "device_turn_on",
      "params": {"device_id": "light_living_room"}
    },
    {
      "action_type": "set_temperature",
      "params": {"value": 25}
    },
    {
      "action_type": "dashan_speak",
      "params": {"text": "欢迎回家！"}
    },
    {
      "action_type": "dashan_play_animation",
      "params": {"animation": "happy"}
    }
  ]
}
```

### 主动服务集成

DaShan的状态可以触发智慧管家的主动服务：

- **异常检测**: DaShan检测到异常 → 智慧管家通知用户
- **能量优化**: DaShan进入睡眠 → 智慧管家优化设备能耗
- **预测服务**: DaShan活跃时间段 → 智慧管家预测用户行为

### 多DaShan支持

系统设计支持多个DaShan机器人：
- 每个DaShan使用不同的MQTT client_id
- 智慧管家可以创建多个适配器实例
- 通过不同的topic前缀区分多个机器人

## 故障排查

### 问题: DaShan无法连接MQTT

**检查**:
1. MQTT broker是否运行
2. 网络连接是否正常
3. 防火墙是否阻止1883端口

**解决**:
```bash
# 测试MQTT连接
mosquitto_sub -h localhost -p 1883 -t "test"
```

### 问题: 智慧管家收不到DaShan状态

**检查**:
1. DaShan是否连接到MQTT
2. topic配置是否正确
3. 智慧管家是否订阅了正确的topic

**解决**:
```python
# 在智慧管家中检查订阅的topics
print(adapter.config.topic_status)
```

### 问题: 控制命令无效

**检查**:
1. 命令格式是否正确
2. DaShan是否订阅了command topic
3. 命令处理器是否正确实现

**解决**:
```python
# 在DaShan中添加调试日志
logger.info(f"Received command: {command}")
```

## 性能优化

### MQTT优化

1. **批量日志上报**: 每2秒批量上报10条日志
2. **状态节流**: 每5秒上报一次状态
3. **QoS设置**: 使用QoS 0保证实时性

### 资源优化

1. **日志队列**: 限制最大100条日志
2. **图像截断**: 仅发送图像前100个字符
3. **异步处理**: 所有MQTT操作异步执行

## 安全建议

1. **MQTT认证**: 使用用户名/密码保护MQTT broker
2. **TLS加密**: 生产环境使用TLS加密MQTT通信
3. **访问控制**: 限制哪些设备可以发送命令
4. **日志脱敏**: 敏感信息不记录在日志中

## 下一步开发

### Web UI集成

待实现功能：
- [ ] DaShan状态实时显示面板
- [ ] DaShan日志查看器
- [ ] DaShan控制面板
- [ ] 摄像头图像预览
- [ ] 多DaShan管理

### 高级功能

待开发功能：
- [ ] DaShan语音识别集成到智慧管家
- [ ] 智能场景自动学习DaShan行为
- [ ] DaShan与HomeAssistant设备深度联动
- [ ] DaShan行为分析和情感建模

## 总结

通过本次集成，DaShan桌面宠物机器人已完全接入智慧管家系统，实现了：

✅ 实时状态同步
✅ 完整日志追踪
✅ 双向远程控制
✅ 智能场景联动
✅ 事件统一管理
✅ 可扩展的架构设计

智慧管家现在可以作为统一的智能中枢，管理所有设备，包括DaShan这样的智能实体机器人！
