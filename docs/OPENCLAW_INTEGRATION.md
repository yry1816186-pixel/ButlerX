# OpenClaw 集成指南

本文档说明如何在智慧管家系统中集成和配置 OpenClaw 多消息平台。

## 概述

智慧管家支持两种 OpenClaw 集成方式：

1. **CLI 模式** - 通过命令行调用 `openclaw message send` 命令
2. **Gateway 模式** - 通过 WebSocket Gateway 协议与 OpenClaw 实时通信

## 配置方式

### CLI 模式配置（默认）

在配置文件 `config.json` 中添加：

```json
{
  "openclaw": {
    "cli_path": "openclaw",
    "env": {
      "OPENCLAW_HOME": "/path/to/openclaw/config"
    }
  }
}
```

### Gateway 模式配置

在配置文件 `config.json` 中添加：

```json
{
  "openclaw": {
    "cli_path": "openclaw",
    "env": {},
    "gateway_enabled": true,
    "gateway_url": "ws://127.0.0.1:18789",
    "gateway_token": "",
    "gateway_password": "your_password"
  }
}
```

### 环境变量配置

也可以通过环境变量配置：

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `OPENCLAW_CLI_PATH` | OpenClaw CLI 可执行文件路径 | `openclaw` |
| `OPENCLAW_GATEWAY_URL` | Gateway WebSocket URL | `ws://127.0.0.1:18789` |
| `OPENCLAW_GATEWAY_TOKEN` | Gateway 认证令牌 | - |
| `OPENCLAW_GATEWAY_PASSWORD` | Gateway 认证密码 | - |
| `OPENCLAW_GATEWAY_ENABLED` | 是否启用 Gateway 模式 | `false` |

## 支持的动作类型

### 基础消息发送

```json
{
  "action_type": "openclaw_message_send",
  "params": {
    "target": "user_id or phone_number",
    "message": "Hello, world!",
    "channel": "telegram",
    "account": "account_id"
  }
}
```

### 发送媒体消息

```json
{
  "action_type": "openclaw_send_media",
  "params": {
    "target": "user_id or phone_number",
    "media": "/path/to/image.jpg or https://example.com/image.jpg",
    "message": "This is an image",
    "channel": "telegram",
    "account": "account_id"
  }
}
```

### 发送带按钮的消息

```json
{
  "action_type": "openclaw_send_buttons",
  "params": {
    "target": "user_id or phone_number",
    "message": "Choose an option:",
    "buttons": [
      {"label": "Option A", "action": "select_a"},
      {"label": "Option B", "action": "select_b"}
    ],
    "channel": "telegram",
    "account": "account_id"
  }
}
```

### 回复消息

```json
{
  "action_type": "openclaw_reply_message",
  "params": {
    "target": "user_id or phone_number",
    "message_id": "message_id_to_reply",
    "message": "This is a reply",
    "channel": "telegram",
    "account": "account_id"
  }
}
```

### 发送到主题线程

```json
{
  "action_type": "openclaw_send_to_thread",
  "params": {
    "target": "user_id or phone_number",
    "thread_id": "thread_id",
    "message": "This is a thread message",
    "channel": "telegram",
    "account": "account_id"
  }
}
```

## 支持的消息参数

OpenClaw CLI 支持以下参数：

| 参数 | 类型 | 说明 | 必需 |
|-----|------|------|------|
| `--target` | string | 目标用户 ID 或电话号码 | 是 |
| `--message` | string | 消息文本 | 至少一个 |
| `--media` | string | 媒体路径或 URL | 至少一个 |
| `--channel` | string | 消息渠道 (telegram/whatsapp/slack 等) | 否 |
| `--account` | string | 账户 ID | 否 |
| `--buttons` | JSON | 内联按钮配置 | 否 |
| `--card` | JSON | Adaptive Card 配置 | 否 |
| `--reply-to` | string | 要回复的消息 ID | 否 |
| `--thread-id` | string | 主题线程 ID | 否 |
| `--silent` | flag | 静默发送 (仅 Telegram) | 否 |
| `--gif-playback` | flag | WhatsApp 视频作为 GIF 播放 | 否 |

## 安全限制

### DM（私聊）配对模式

OpenClaw 默认对私聊启用配对模式 (`dmPolicy="pairing"`)：

- 未知发送者会收到一个配对码
- Bot 不会处理未知发送者的消息
- 需要使用 `openclaw pairing approve <channel> <code>` 批准配对

### 公开私聊访问

要允许公开的私聊访问，需要：

1. 设置 `dmPolicy="open"`
2. 将 `"*"` 添加到渠道允许列表

示例配置：

```json
{
  "channels": {
    "telegram": {
      "dm": {
        "policy": "open",
        "allowFrom": ["*"]
      }
    }
  }
}
```

### SSRF 防护

OpenClaw 包含 SSRF（服务器端请求伪造）保护：

- 阻止访问私有网络 IP（127.0.0.1, 192.168.x.x, 10.x.x.x）
- 阻止访问 localhost
- 阻止访问内部主机名

### 路径遍历防护

- 账户 ID 会经过 sanitize 处理
- 媒体路径会被限制在允许的目录内

### 环境变量覆盖保护

OpenClaw 会阻止通过环境变量覆盖敏感配置。

## 最佳实践

### 1. 使用环境变量存储敏感信息

```bash
export OPENCLAW_GATEWAY_TOKEN="your_token"
export OPENCLAW_GATEWAY_PASSWORD="your_password"
```

### 2. 启用 Gateway 模式获得更好的性能

Gateway 模式相比 CLI 模式：
- 更低的延迟（WebSocket vs subprocess）
- 持久连接，减少连接开销
- 支持实时事件监听
- 支持更多高级功能

### 3. 配置适当的 DM 策略

- **开发环境**：可以使用 `open` 策略方便测试
- **生产环境**：推荐使用 `pairing` 策略提高安全性

### 4. 使用允许列表限制访问

```json
{
  "channels": {
    "telegram": {
      "dm": {
        "policy": "pairing",
        "allowFrom": ["user123", "user456"]
      }
    }
  }
}
```

### 5. 配置 TLS 加密

在 OpenClaw 配置中启用 TLS：

```json
{
  "gateway": {
    "tls": {
      "enabled": true
    }
  }
}
```

然后使用 `wss://` 连接：

```json
{
  "openclaw": {
    "gateway_url": "wss://127.0.0.1:18789"
  }
}
```

### 6. 运行安全检查

定期运行 OpenClaw 的诊断命令：

```bash
openclaw doctor
```

这会检查：
- 风险的 DM 策略配置
- 未加密的连接
- 缺少认证配置
- 其他安全问题

## 通道支持

OpenClaw 支持以下消息通道：

| 通道 | channel 值 | 特性 |
|-----|-----------|------|
| Telegram | `telegram` | 完整支持，包括按钮、主题线程 |
| WhatsApp | `whatsapp` | 媒体支持，GIF 播放 |
| Slack | `slack` | 按钮支持，Adaptive Cards |
| Discord | `discord` | 基础消息支持 |
| Google Chat | `googlechat` | 基础消息支持 |
| Signal | `signal` | 基础消息支持 |
| Microsoft Teams | `msteams` | Adaptive Cards 支持 |
| WebChat | `webchat` | 基础消息支持 |

## 故障排查

### CLI 未找到

错误：`openclaw_cli_not_found`

解决方案：
1. 确保 OpenClaw 已安装：`npm install -g openclaw`
2. 检查 `openclaw_cli_path` 配置
3. 确保 OpenClaw 在系统 PATH 中

### Gateway 连接失败

错误：`not_connected`

解决方案：
1. 确保 OpenClaw Gateway 正在运行
2. 检查 `gateway_url` 配置
3. 验证认证令牌或密码
4. 检查防火墙设置

### 消息发送失败

错误：`missing_target` 或 `missing_message_or_media`

解决方案：
1. 确保提供 `target` 参数
2. 确保至少提供 `message` 或 `media` 参数

### SSRF 阻止

错误：`ssrf_blocked`

解决方案：
1. 使用公共 URL 而不是内部 URL
2. 或在 OpenClaw 配置中添加允许的内部 IP

## 示例用例

### 1. 发送监控告警

```json
{
  "action_type": "openclaw_message_send",
  "params": {
    "target": "+1234567890",
    "message": "警告：检测到异常活动！",
    "channel": "whatsapp"
  }
}
```

### 2. 发送截图

```json
{
  "action_type": "openclaw_send_media",
  "params": {
    "target": "user123",
    "media": "/tmp/snapshot.jpg",
    "message": "监控截图",
    "channel": "telegram"
  }
}
```

### 3. 确认操作

```json
{
  "action_type": "openclaw_send_buttons",
  "params": {
    "target": "user123",
    "message": "确认执行此操作？",
    "buttons": [
      {"label": "确认", "action": "confirm"},
      {"label": "取消", "action": "cancel"}
    ],
    "channel": "telegram"
  }
}
```

## 参考资料

- [OpenClaw 官方文档](https://docs.openclaw.ai/)
- [OpenClaw 安全指南](https://docs.openclaw.ai/gateway/security)
- [OpenClaw 通道配置](https://docs.openclaw.ai/channels)
- [OpenClaw Gateway 协议](https://docs.openclaw.ai/gateway)
