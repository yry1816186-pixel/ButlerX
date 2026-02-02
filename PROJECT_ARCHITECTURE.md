# 智慧管家 - 项目整体架构

## 系统概述

智慧管家是一个事件驱动的智能家居控制系统,由三个核心模块组成:

1. **智慧管家AI系统** - 基于大语言模型的中央控制大脑
2. **DaShan桌面宠机器人** - 固定式桌面控制中心
3. **可移动摄像头系统** - 全屋智能监控设备

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户交互层                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Web UI     │  │   语音控制   │  │   自然语言   │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼───────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│                    Butler Core (Python)                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              事件驱动引擎 (Event Engine)                   │  │
│  └────────────────────────┬─────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              规则引擎 (Rule Engine)                        │  │
│  └────────────────────────┬─────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Brain AI (GLM-4.7)                           │  │
│  └────────────────────────┬─────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              数据存储 (SQLite)                            │  │
│  └────────────────────────┬─────────────────────────────────┘  │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            │ MQTT Broker
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
┌─────────▼──────────┐  ┌───▼──────────┐  ┌───▼──────────────────┐
│   DaShan Robot     │  │ Mobile Camera│  │   其他智能家居设备      │
│  (桌面控制中心)     │  │ (可移动监控)   │  │  (灯光/传感器/家电)    │
│                    │  │              │  │                      │
│ - ESP32-S3         │  │ - ESP32-S3   │  │ - Zigbee/WiFi       │
│ - LED Eyes         │  │ - OV2640     │  │ - BLE               │
│ - Servo            │  │ - Stepper    │  │ - RS485             │
│ - Camera           │  │ - SG90       │  │                      │
└────────────────────┘  └──────────────┘  └──────────────────────┘
```

## 核心组件说明

### 1. Butler Core (Python)

#### 事件驱动引擎

负责接收、处理、分发所有事件流:

```python
# 事件流示例
用户指令 → 事件队列 → 规则引擎 → 动作计划 → 执行 → 结果反馈
```

**主要功能:**
- MQTT事件订阅/发布
- 事件标准化和路由
- 状态机管理
- 异常处理

#### 规则引擎

基于规则的自动化执行:

```python
# 规则示例
{
  "id": "door_open_notify",
  "trigger": {"source": "sensor", "type": "door_open"},
  "actions": [
    {"action_type": "notify", "params": {"message": "门已打开"}},
    {"action_type": "camera_move", "params": {"position": "door"}}
  ]
}
```

#### Brain AI (GLM-4.7)

自然语言理解和决策:

```python
# Brain API示例
POST /api/brain/plan
{
  "text": "把摄像头移到客厅并拍照"
}

# 返回动作计划
{
  "actions": [
    {"action_type": "camera_move", "params": {"x": 500, "y": 90}},
    {"action_type": "camera_capture", "params": {}}
  ]
}
```

**能力:**
- 自然语言理解
- 视觉识别(YOLO + Face Recognition)
- 语音识别(本地ASR)
- 动作规划

### 2. DaShan桌面宠机器人

#### 硬件架构

```
DaShan Robot
├── ESP32-S3 (主控)
│   ├── WiFi模块
│   ├── MQTT客户端
│   └── 串口通信
├── LED Eyes (表情显示)
├── Servo (摇头动作)
├── OV2640 Camera (视觉)
└── Sensors (传感器)
```

#### 软件架构

```python
# DaShan协议层
class DaShanProtocol:
    def set_expression(expression_id, brightness)
    def speak(text)
    def move_head(angle)
    def capture_image()

# MQTT通信层
class DaShanMQTTClient:
    def publish_status(state)
    def publish_log(log_entry)
    def on_command(callback)
```

#### 集成方式

```python
# Butler端
from butler.devices import DaShanAdapter

adapter = DaShanAdapter(mqtt_host="localhost")
adapter.on_status_update(lambda state: print(state))
adapter.set_expression(1)  # 控制DaShan表情
```

### 3. 可移动摄像头系统

#### 硬件架构

```
Mobile Camera
├── ESP32-S3 (主控)
│   ├── WiFi模块
│   ├── MQTT客户端
│   ├── TMC2209驱动 (步进电机)
│   └── PWM输出 (舵机)
├── 运动系统
│   ├── NEMA17步进电机 (左右)
│   ├── 1605滚珠丝杠 (2m行程)
│   └── SG90舵机 (上下倾斜)
└── OV2640摄像头
```

#### 运动控制

```python
# 步进电机控制 (TMC2209)
class StepperController:
    def move_to_position(target_mm, speed_mm_s)
    def home()
    def stop()

# 舵机控制
class ServoController:
    def set_angle(angle)
    def calibrate()
```

#### 摄像头控制

```python
# 图像捕获
class CameraController:
    def capture_frame()
    def stream_to_mqtt(topic)
    def face_detect()
    def object_detect()
```

#### MQTT协议

```
# 发布Topic
camera/position → {"x": 500, "y": 90}
camera/image → (base64 image data)

# 订阅Topic
camera/command → {"command": "move_to", "x": 500, "y": 90}
```

## 数据流

### 用户指令流程

```
用户输入 → Web UI/语音 → Butler Core → Brain AI解析 → 动作计划
  → MQTT发布 → 设备执行 → 结果反馈 → 用户界面显示
```

### 事件驱动流程

```
传感器/设备 → MQTT事件 → Butler Core → 规则匹配 → 动作执行
  → 设备控制 → 状态更新 → 数据存储
```

### 摄像头控制流程

```
用户指令 → Brain AI解析 → camera/command (MQTT) → ESP32接收
  → TMC2209驱动步进电机 → 摄像头移动 → camera/image (MQTT)
  → Butler Core → Web UI显示
```

## 部署架构

### 开发环境

```
本地机器
├── Docker Compose
│   ├── Butler Core (Python)
│   ├── MQTT Broker (Eclipse Mosquitto)
│   ├── Web UI (FastAPI + React)
│   └── Database (SQLite)
├── DaShan Robot (USB串口)
└── Mobile Camera (WiFi连接)
```

### 生产环境

```
服务器
├── Butler Core Service
├── MQTT Broker
├── Web UI (Nginx)
└── Database (PostgreSQL)

住宅环境
├── DaShan Robot (桌面)
├── Mobile Camera (天花板)
└── 智能家居设备 (分布式)
```

## 技术栈

### 后端
- Python 3.11+
- FastAPI (Web API)
- MQTT (通信协议)
- SQLite (数据存储)
- GLM-4.7 (大语言模型)

### 前端
- React 18
- Tailwind CSS
- WebSocket (实时通信)

### 嵌入式
- ESP32-S3 (DaShan + 摄像头)
- TMC2209 (步进驱动)
- OV2640 (摄像头)
- Arduino (兼容层)

### AI/ML
- YOLOv8/v11 (目标检测)
- Face Recognition (人脸识别)
- Faster-Whisper (语音识别)

## 扩展性

### 设备扩展

通过设备适配器模式添加新设备:

```python
# 自定义设备适配器
class CustomDeviceAdapter:
    def __init__(self, config):
        self.mqtt_client = MQTTClient(config)
    
    def send_command(self, command, params):
        self.mqtt_client.publish("custom/command", {...})
```

### 功能扩展

通过插件系统扩展功能:

```python
# 插件接口
class ButlerPlugin:
    def on_event(self, event):
        pass
    
    def on_command(self, command):
        pass
```

## 安全性

### 通信安全
- MQTT TLS加密
- 设备认证
- 访问控制列表

### 数据安全
- 敏感数据加密
- 定期备份
- 访问日志

### 设备安全
- 固件签名验证
- 安全启动
- 远程更新机制

## 性能优化

### 事件处理
- 异步事件队列
- 批量处理
- 优先级队列

### 数据存储
- 索引优化
- 分区表
- 缓存策略

### 网络通信
- 消息压缩
- 批量传输
- 连接池

## 监控和日志

### 系统监控
- 设备在线状态
- 事件处理延迟
- 资源使用情况

### 日志记录
- 结构化日志
- 日志分级
- 日志轮转

### 告警机制
- 异常告警
- 阈值告警
- 多渠道通知

## 项目文件结构

```
智慧管家/
├── butler/              # Butler Core
│   ├── core/           # 核心引擎
│   ├── adapters/       # 设备适配器
│   ├── devices/        # 设备驱动
│   ├── goal_engine/    # 目标引擎
│   ├── brain/          # AI大脑
│   └── ui/             # Web界面
├── DaShan/             # DaShan机器人
│   ├── host/           # 主控代码
│   └── firmware/       # 固件
├── mobile_camera/      # 可移动摄像头
│   ├── hardware/       # 硬件设计
│   ├── firmware/       # ESP32固件
│   └── 3d_models/      # 3D打印文件
├── docker/             # Docker配置
├── scripts/            # 脚本工具
├── docs/               # 文档
└── README.md           # 项目说明
```

## 相关文档

- [DaShan集成指南](./DASHAN_INTEGRATION_GUIDE.md)
- [可移动摄像头方案总结](./MOBILE_CAMERA_SUMMARY.md)
- [Brain API文档](./docs/BRAIN_API.md)
- [MQTT协议规范](./docs/MQTT_PROTOCOL.md)
