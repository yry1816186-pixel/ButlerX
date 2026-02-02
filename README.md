# 智慧管家核心 MVP

基于事件驱动的智能家居中枢 MVP，包含 MQTT、Python 核心服务、SQLite 以及简洁的 Web UI。

## 核心创新功能

### 1. 智慧管家AI系统
- 基于GLM-4.7大语言模型的自然语言理解
- 事件驱动的自动化规则引擎
- 支持视觉识别和语音交互
- 完整的API和Web UI控制界面

### 2. DaShan桌面宠机器人
- 固定式桌面宠物机器人
- 双向MQTT通信集成
- 实时状态监控和远程控制
- 表情、语音、动作控制

### 3. 可移动摄像头系统
- 2米轨道全覆盖监控
- 滚珠丝杠静音驱动(25-35dB)
- 横向左右移动+垂直上下倾斜
- 天花板嵌入式美观设计

## 快速开始

1) 构建并启动服务：
```
docker-compose up --build
```

2) 打开界面：
- 仪表盘：http://localhost:8000/dashboard
- 控制台：http://localhost:8000/controls

3) 在控制台触发一条命令（例如“模拟入侵”）。

控制台页面现在包含“AI 中枢控制台”和“规则编辑器”，位于：
```
http://localhost:8000/controls
```

## 你会看到什么

- 事件会发布到 `butler/in/event` 或 `butler/in/command`。
- 智慧管家核心会规范化事件、写入 SQLite、应用策略规则，并输出行动计划/执行结果。
- 仪表盘显示最近 10 条事件、计划和结果。

## 配置

默认配置在 `butler/config.json`。你可以用以下方式覆盖任意配置：
- 环境变量（最高优先级）。
- 直接编辑 `butler/config.json`。

示例：
```
set MQTT_TOPIC_IN_EVENT=butler/in/event,butler/in/event_compat
set R1_COOLDOWN_SEC=120
set UI_POLL_INTERVAL_MS=2000
docker-compose up --build
```

## AI 中枢 API（GLM 4.7）

核心服务现在暴露了用于语言 + 视觉规划的 AI 中枢接口：

- `POST /api/brain/plan` -> 返回行动计划（不执行）
- `POST /api/brain/act` -> 规划 + 执行
- `GET /api/brain/capabilities` -> 动作能力清单

示例：
```
curl -X POST http://localhost:8000/api/brain/plan ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"打开客厅灯并通知我\"}"
```

视觉示例（base64 图像）：
```
curl -X POST http://localhost:8000/api/brain/plan ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"这张图里有什么异常？\",\"images\":[\"<BASE64>\"]}"
```

关闭缓存（适合读取实时信息）：
```
curl -X POST http://localhost:8000/api/brain/plan ^
  -H "Content-Type: application/json" ^
  -d "{\"text\":\"检查最新消息\",\"cache\":false}"
```

### LLM 环境变量

```
set GLM_API_KEY=your_key
set GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
set GLM_MODEL_TEXT=glm-4.7
set GLM_MODEL_VISION=glm-4.6v
```

### AI 中枢参数（节省成本/稳定性）

```
set BRAIN_CACHE_TTL_SEC=30
set BRAIN_CACHE_SIZE=128
set BRAIN_MAX_ACTIONS=6
set BRAIN_RETRY_ATTEMPTS=1
```

### 规则优先（不走 LLM）

你可以在 `butler/config.json` 的 `brain.rules` 配置规则（默认示例是关闭的）。
也可以用环境变量直接传 JSON：
```
set BRAIN_RULES=[{"id":"notify_rule","any":["提醒"],"actions":[{"action_type":"notify","params":{"title":"提醒","message":"规则触发","level":"info"}}]}]
```

如果你需要在有图片时也走规则：
```
set BRAIN_RULES_ALLOW_IMAGES=1
```

### 本地电脑控制

允许的命令白名单，用于启用 `system_exec` 动作：
```
set SYSTEM_EXEC_ALLOWLIST=python,powershell
```

### 脚本执行（更安全）

把脚本放到 `scripts` 目录，通过 `script_run` 动作调用：
```
set SCRIPT_DIR=/app/butler/scripts
set SCRIPT_ALLOWLIST=my_task.sh,backup.sh
```

### 邮件能力（可选）

```
set EMAIL_IMAP_HOST=imap.example.com
set EMAIL_IMAP_PORT=993
set EMAIL_IMAP_SSL=1
set EMAIL_SMTP_HOST=smtp.example.com
set EMAIL_SMTP_PORT=587
set EMAIL_SMTP_SSL=0
set EMAIL_SMTP_STARTTLS=1
set EMAIL_USERNAME=you@example.com
set EMAIL_PASSWORD=your_password
set EMAIL_FROM=you@example.com
```

动作示例：
```
{"action_type":"email_read","params":{"limit":5,"folder":"INBOX","unread_only":true}}
{"action_type":"email_send","params":{"to":"a@b.com","subject":"Hi","body":"Hello"}}
```

### 图片生成（可选）

```
set IMAGE_API_URL=https://your-image-api/endpoint
set IMAGE_API_KEY=your_key
set IMAGE_MODEL=your_model
```

动作示例：
```
{"action_type":"image_generate","params":{"prompt":"a cozy home","size":"1024x1024","n":1}}
```

### 语音识别（免费，本地）

项目已内置本地 ASR（`faster-whisper`），无需付费接口即可进行语音转文字。默认在 Docker 内运行：
```
set ASR_PROVIDER=faster-whisper
set ASR_MODEL_LOCAL=small
set ASR_LANGUAGE=zh
set ASR_DEVICE=cpu
set ASR_COMPUTE_TYPE=int8
set ASR_DOWNLOAD_DIR=/app/butler/models/whisper
```

说明：
- 首次启动会下载模型，时间较久（模型越大越准也越慢）。
- 想要更高精度可将 `ASR_MODEL_LOCAL` 改为 `medium` 或 `large-v3`（需要更强算力，建议 GPU）。
- 如需云端 ASR，可改为 `ASR_PROVIDER=remote` 并配置 `ASR_API_URL`/`ASR_API_KEY`。

### ASR 语音识别（免费本地）

你可以在本地免费运行 ASR，无需按次付费。支持的提供方：
- `faster-whisper`（推荐，高准确率）
- `whisper`（OpenAI Whisper）
- `vosk`（更轻量，准确率较低）

环境变量示例：
```
set ASR_PROVIDER=faster-whisper
set ASR_MODEL_LOCAL=large-v3
set ASR_LANGUAGE=zh
set ASR_DEVICE=cpu
set ASR_COMPUTE_TYPE=int8
set ASR_DOWNLOAD_DIR=/app/butler/models
```

其它提供方：
```
set ASR_PROVIDER=whisper
set ASR_MODEL_LOCAL=base
```

```
set ASR_PROVIDER=vosk
set ASR_VOSK_MODEL_PATH=/path/to/vosk-model
```

在宿主机上安装本地依赖（不要在精简版 Docker 镜像内安装）：
```
pip install faster-whisper
pip install openai-whisper
pip install vosk
```

### 任务调度（可选）

```
set SCHEDULER_ENABLED=1
set SCHEDULER_INTERVAL_SEC=5
```

动作示例：
```
{"action_type":"schedule_task","params":{"delay_sec":60,"actions":[{"action_type":"notify","params":{"title":"提醒","message":"1分钟到了","level":"info"}}]}}
```

### OpenClaw 消息桥接（可选）

如果已安装 `openclaw` CLI，规划器可以调用：
`openclaw_message_send` 并传入 `target` + `message`。
按需设置 CLI 路径或环境变量：
```
set OPENCLAW_CLI_PATH=openclaw
set OPENCLAW_ENV={"OPENCLAW_GATEWAY_TOKEN":"..."}
```

## 本地视觉（YOLO + 人脸识别）

你可以通过向 API 发送图片来运行本地目标检测 + 人脸识别，无需摄像头。该流水线使用 YOLO 检测器（物体或人脸）以及可选的人脸特征向量用于身份匹配。

### 安装视觉依赖

```
pip install -r requirements-vision.txt
```

### 配置模型

编辑 `butler/config.json` 或设置环境变量：

```
set VISION_FACE_MODEL_PATH=yolov11m-face.pt
set VISION_OBJECT_MODEL_PATH=yolov8n.pt
set VISION_FACE_BACKEND=auto
set VISION_FACE_MATCH_THRESHOLD=0.35
set VISION_FACE_MIN_CONFIDENCE=0.5
set VISION_OBJECT_MIN_CONFIDENCE=0.25
```

### API 示例

检测物体：
```
curl -X POST http://localhost:8000/api/vision/detect ^
  -H "Content-Type: application/json" ^
  -d "{\"image\":\"<BASE64>\",\"model\":\"object\"}"
```

检测并识别人脸：
```
curl -X POST http://localhost:8000/api/vision/detect ^
  -H "Content-Type: application/json" ^
  -d "{\"image\":\"<BASE64>\",\"model\":\"face\",\"match_faces\":true}"
```

录入人脸（记住身份）：
```
curl -X POST http://localhost:8000/api/face/enroll ^
  -H "Content-Type: application/json" ^
  -d "{\"label\":\"Alice\",\"image\":\"<BASE64>\"}"
```

按标签验证：
```
curl -X POST http://localhost:8000/api/face/verify ^
  -H "Content-Type: application/json" ^
  -d "{\"label\":\"Alice\",\"image\":\"<BASE64>\"}"
```

## Frigate 适配器调试模式

运行适配器以观察配置主题的原始载荷：
```
set FRIGATE_TOPIC=your/frigate/topic
set FRIGATE_DEBUG_RAW=1
python -m butler.adapters.frigate_adapter
```

你可以通过 `FRIGATE_PAYLOAD_MAP`（JSON）或 `butler/config.json` 中的 `frigate.payload_map` 来映射载荷字段。
`payload_map` 的路径格式使用点号表示法，并可带数组下标，例如：
```
{
  "payload_map": {
    "field_a": "data.value",
    "field_b": "items[0].name"
  }
}
```

如果你要从原始载荷中映射告警等级，请设置 `frigate.severity_path`：
```
{
  "severity_default": 1,
  "severity_path": "meta.level"
}
```

## 模拟器

模拟器容器默认每 30 秒发布一次示例事件。

你可以覆盖发布间隔：
```
set SIM_INTERVAL_SEC=10
docker-compose up --build
```

或只发送一次事件：
```
set SIM_ONCE=1
docker-compose up --build
```

## MQTT 主题

- 输入：`butler/in/event`、`butler/in/command`
- 输出：`butler/out/event`、`butler/out/action_plan`、`butler/out/action_result`

## 可移动摄像头系统

### 硬件方案

采用**滚珠丝杠+齿轮齿条**系统,实现静音、高精度、美观的全屋监控。

**核心组件:**
- NEMA17步进电机 + TMC2209静音驱动器
- 1605滚珠丝杠(16mm直径,5mm导程)
- 2米行程直线导轨
- SG90垂直倾斜舵机
- ESP32-S3 + OV2640摄像头

**技术参数:**
- 噪音: 25-35dB
- 精度: ±0.1mm
- 速度: 0-50mm/s
- 总成本: ~¥280

### 安装方式

天花板嵌入式安装,所有机械结构完全隐藏,外观仅可见白色轨道条,适合住宅/办公环境。

详细方案说明见: [可移动摄像头方案总结](./MOBILE_CAMERA_SUMMARY.md)

### MQTT Topics (摄像头)

| Topic | 方向 | 说明 |
|-------|------|------|
| camera/position | 发布 | 当前摄像头位置 |
| camera/image | 发布 | 实时图像 |
| camera/command | 订阅 | 移动指令 |

### 控制示例

```json
{
  "command": "move_to",
  "x": 500,
  "y": 90,
  "speed": 30
}
```

## DaShan桌面宠机器人

### 集成方式

DaShan通过MQTT协议与Butler系统双向通信,作为智能家居的控制中心。

### MQTT Topics (DaShan)

| Topic | 方向 | 说明 |
|-------|------|------|
| daShan/status | 发布 | 机器人状态 |
| daShan/log | 发布 | 运行日志 |
| daShan/image | 发布 | 摄像头图像 |
| daShan/command | 订阅 | 控制指令 |

### 控制API

```python
from butler.devices import DaShanAdapter, DaShanConfig

config = DaShanConfig(mqtt_host="localhost", mqtt_port=1883)
adapter = DaShanAdapter(config)

adapter.set_expression(1, brightness=255)
adapter.speak("你好,我是大善")
```

详细集成指南见: [DaShan集成文档](./DASHAN_INTEGRATION_GUIDE.md)
