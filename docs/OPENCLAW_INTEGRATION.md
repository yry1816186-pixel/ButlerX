# OpenClaw Integration Guide

This document explains how to integrate and configure OpenClaw multi-messaging platform in the Smart Butler system.

## Overview

Smart Butler supports two OpenClaw integration modes:

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
    "gateway_password": ""
  }
}
```

### 通道配置

为每个消息平台单独配置功能开关：

```json
{
  "openclaw": {
    "cli_path": "openclaw",
    "env": {},
    "channels": {
      "discord": {
        "enabled": false,
        "polls": true,
        "threads": true,
        "stickers": true,
        "emojiUploads": true,
        "stickerUploads": true
      },
      "slack": {
        "enabled": false,
        "emojiList": true
      },
      "telegram": {
        "enabled": false,
        "sticker": true,
        "inlineButtons": false
      },
      "whatsapp": {
        "enabled": false,
        "polls": true
      },
      "googlechat": {
        "enabled": false
      },
      "signal": {
        "enabled": false
      },
      "imessage": {
        "enabled": false
      },
      "msteams": {
        "enabled": false,
        "polls": true
      }
    }
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

### 创建投票

支持平台：WhatsApp, Discord, MS Teams

```json
{
  "action_type": "openclaw_message_poll",
  "params": {
    "target": "channel_id",
    "question": "今天吃什么？",
    "options": ["披萨", "寿司", "火锅", "烧烤"],
    "multi": false,
    "duration_hours": 24,
    "message": "请大家投票选择今天吃什么",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 表情反应

支持平台：Discord, Google Chat, Slack, Telegram, WhatsApp, Signal

```json
{
  "action_type": "openclaw_message_react",
  "params": {
    "target": "channel_id",
    "message_id": "message_id",
    "emoji": "✅",
    "remove": false,
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 获取反应列表

支持平台：Discord, Google Chat, Slack

```json
{
  "action_type": "openclaw_message_reactions",
  "params": {
    "target": "channel_id",
    "message_id": "message_id",
    "limit": 50,
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 读取历史消息

支持平台：Discord, Slack

```json
{
  "action_type": "openclaw_message_read",
  "params": {
    "target": "channel_id",
    "limit": 50,
    "before": "message_id",
    "after": "message_id",
    "around": "message_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 编辑消息

支持平台：Discord, Slack

```json
{
  "action_type": "openclaw_message_edit",
  "params": {
    "target": "channel_id",
    "message_id": "message_id",
    "message": "Updated message content",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 删除消息

支持平台：Discord, Slack, Telegram

```json
{
  "action_type": "openclaw_message_delete",
  "params": {
    "target": "channel_id",
    "message_id": "message_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 固定消息

支持平台：Discord, Slack

```json
{
  "action_type": "openclaw_message_pin",
  "params": {
    "target": "channel_id",
    "message_id": "message_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 取消固定消息

支持平台：Discord, Slack

```json
{
  "action_type": "openclaw_message_unpin",
  "params": {
    "target": "channel_id",
    "message_id": "message_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 列出固定消息

支持平台：Discord, Slack

```json
{
  "action_type": "openclaw_message_list_pins",
  "params": {
    "target": "channel_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 创建主题线程

支持平台：Discord

```json
{
  "action_type": "openclaw_thread_create",
  "params": {
    "target": "channel_id",
    "thread_name": "讨论主题",
    "message_id": "parent_message_id",
    "auto_archive_min": 1440,
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 列出主题线程

支持平台：Discord

```json
{
  "action_type": "openclaw_thread_list",
  "params": {
    "guild_id": "guild_id",
    "channel_id": "channel_id",
    "include_archived": false,
    "before": "thread_id",
    "limit": 50,
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 回复主题线程

支持平台：Discord

```json
{
  "action_type": "openclaw_thread_reply",
  "params": {
    "target": "thread_id",
    "message": "This is a thread reply",
    "media": "/path/to/image.jpg",
    "reply_to": "message_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 列出表情符号

支持平台：Discord, Slack

```json
{
  "action_type": "openclaw_emoji_list",
  "params": {
    "guild_id": "guild_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 上传表情符号

支持平台：Discord

```json
{
  "action_type": "openclaw_emoji_upload",
  "params": {
    "guild_id": "guild_id",
    "emoji_name": "custom_emoji",
    "media": "/path/to/emoji.png",
    "role_ids": ["role_id_1", "role_id_2"],
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 发送贴纸

支持平台：Discord

```json
{
  "action_type": "openclaw_sticker_send",
  "params": {
    "target": "channel_id",
    "sticker_ids": ["sticker_id_1", "sticker_id_2"],
    "message": "Sticker message",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 上传贴纸

支持平台：Discord

```json
{
  "action_type": "openclaw_sticker_upload",
  "params": {
    "guild_id": "guild_id",
    "sticker_name": "funny_sticker",
    "sticker_desc": "A funny sticker",
    "sticker_tags": "fun, meme",
    "media": "/path/to/sticker.png",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 广播消息

支持平台：所有配置的通道

```json
{
  "action_type": "openclaw_broadcast",
  "params": {
    "targets": [
      "telegram:user123",
      "whatsapp:+1234567890",
      "discord:channel:456"
    ],
    "message": "Broadcast message to all channels",
    "media": "/path/to/image.jpg",
    "channel": "all",
    "account": "account_id",
    "dry_run": false
  }
}
```

### 搜索消息

支持平台：Discord

```json
{
  "action_type": "openclaw_search",
  "params": {
    "guild_id": "guild_id",
    "query": "search keywords",
    "channel_id": "channel_id",
    "channel_ids": ["channel_id_1", "channel_id_2"],
    "author_id": "user_id",
    "author_ids": ["user_id_1", "user_id_2"],
    "limit": 50,
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 获取成员信息

支持平台：Discord, Slack

```json
{
  "action_type": "openclaw_member_info",
  "params": {
    "user_id": "user_id",
    "guild_id": "guild_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 获取角色信息

支持平台：Discord

```json
{
  "action_type": "openclaw_role_info",
  "params": {
    "guild_id": "guild_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 添加角色

支持平台：Discord

```json
{
  "action_type": "openclaw_role_add",
  "params": {
    "guild_id": "guild_id",
    "user_id": "user_id",
    "role_id": "role_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 移除角色

支持平台：Discord

```json
{
  "action_type": "openclaw_role_remove",
  "params": {
    "guild_id": "guild_id",
    "user_id": "user_id",
    "role_id": "role_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 获取频道信息

支持平台：Discord

```json
{
  "action_type": "openclaw_channel_info",
  "params": {
    "target": "channel_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 列出频道

支持平台：Discord

```json
{
  "action_type": "openclaw_channel_list",
  "params": {
    "guild_id": "guild_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 创建频道

支持平台：Discord

```json
{
  "action_type": "openclaw_channel_create",
  "params": {
    "guild_id": "guild_id",
    "name": "new-channel",
    "type": "text",
    "parent_id": "category_id",
    "position": 1,
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 编辑频道

支持平台：Discord

```json
{
  "action_type": "openclaw_channel_edit",
  "params": {
    "target": "channel_id",
    "name": "updated-name",
    "type": "text",
    "parent_id": "category_id",
    "position": 2,
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 删除频道

支持平台：Discord

```json
{
  "action_type": "openclaw_channel_delete",
  "params": {
    "target": "channel_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 语音状态

支持平台：Discord

```json
{
  "action_type": "openclaw_voice_status",
  "params": {
    "guild_id": "guild_id",
    "user_id": "user_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 列出事件

支持平台：Discord

```json
{
  "action_type": "openclaw_event_list",
  "params": {
    "guild_id": "guild_id",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 创建事件

支持平台：Discord

```json
{
  "action_type": "openclaw_event_create",
  "params": {
    "guild_id": "guild_id",
    "event_name": "Team Meeting",
    "start_time": "2024-12-01T14:00:00Z",
    "end_time": "2024-12-01T15:00:00Z",
    "description": "Weekly team sync",
    "channel_id": "channel_id",
    "location": "Online",
    "event_type": "voice",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 超时用户

支持平台：Discord

```json
{
  "action_type": "openclaw_timeout",
  "params": {
    "guild_id": "guild_id",
    "user_id": "user_id",
    "duration_min": 60,
    "until": "2024-12-01T15:00:00Z",
    "reason": "Spamming",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 踢出用户

支持平台：Discord

```json
{
  "action_type": "openclaw_kick",
  "params": {
    "guild_id": "guild_id",
    "user_id": "user_id",
    "reason": "Violating rules",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 封禁用户

支持平台：Discord

```json
{
  "action_type": "openclaw_ban",
  "params": {
    "guild_id": "guild_id",
    "user_id": "user_id",
    "delete_days": 7,
    "reason": "Serious violation",
    "channel": "discord",
    "account": "account_id"
  }
}
```

### 设置状态

支持平台：Discord

```json
{
  "action_type": "openclaw_set_presence",
  "params": {
    "presence": "online",
    "status": "Working on something",
    "channel": "discord",
    "account": "account_id"
  }
}
```

## 支持的消息参数

### 基础参数

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

### 投票参数

| 参数 | 类型 | 说明 | 必需 |
|-----|------|------|------|
| `--poll-question` | string | 投票问题 | 是 |
| `--poll-option` | string | 投票选项 (可重复) | 是 |
| `--poll-multi` | flag | 允许多选 | 否 |
| `--poll-duration-hours` | number | 投票持续时间（小时） | 否 |

### 反应参数

| 参数 | 类型 | 说明 | 必需 |
|-----|------|------|------|
| `--message-id` | string | 消息 ID | 是 |
| `--emoji` | string | 表情符号 | 否 |
| `--remove` | flag | 移除反应 | 否 |
| `--participant` | string | 参与者 (WhatsApp) | 否 |
| `--from-me` | flag | 来自我 (WhatsApp) | 否 |
| `--target-author` | string | 目标作者 (Signal) | 否 |
| `--target-author-uuid` | string | 目标作者 UUID (Signal) | 否 |

### 读取历史参数

| 参数 | 类型 | 说明 | 必需 |
|-----|------|------|------|
| `--limit` | number | 消息数量限制 | 否 |
| `--before` | string | 之前的消息 ID | 否 |
| `--after` | string | 之后的消息 ID | 否 |
| `--around` | string | 附近的消息 ID (仅 Discord) | 否 |

### 主题线程参数

| 参数 | 类型 | 说明 | 必需 |
|-----|------|------|------|
| `--thread-name` | string | 主题名称 | 是 |
| `--message-id` | string | 父消息 ID | 否 |
| `--auto-archive-min` | number | 自动归档时间（分钟） | 否 |
| `--include-archived` | flag | 包含已归档 | 否 |

### 表情/贴纸参数

| 参数 | 类型 | 说明 | 必需 |
|-----|------|------|------|
| `--emoji-name` | string | 表情名称 | 是 |
| `--sticker-name` | string | 贴纸名称 | 是 |
| `--sticker-desc` | string | 贴纸描述 | 是 |
| `--sticker-tags` | string | 贴纸标签 | 是 |
| `--sticker-id` | string | 贴纸 ID (可重复) | 是 |
| `--role-ids` | string | 角色 ID (可重复) | 否 |

### 广播参数

| 参数 | 类型 | 说明 | 必需 |
|-----|------|------|------|
| `--targets` | string | 目标列表 (可重复) | 是 |
| `--dry-run` | flag | 测试运行不发送 | 否 |

### 搜索参数

| 参数 | 类型 | 说明 | 必需 |
|-----|------|------|------|
| `--guild-id` | string | 服务器 ID | 是 |
| `--query` | string | 搜索关键词 | 是 |
| `--channel-id` | string | 频道 ID | 否 |
| `--channel-ids` | string | 频道 ID 列表 (可重复) | 否 |
| `--author-id` | string | 作者 ID | 否 |
| `--author-ids` | string | 作者 ID 列表 (可重复) | 否 |
| `--limit` | number | 结果限制 | 否 |

### Discord 管理参数

| 参数 | 类型 | 说明 | 必需 |
|-----|------|------|------|
| `--user-id` | string | 用户 ID | 是 |
| `--role-id` | string | 角色 ID | 是 |
| `--name` | string | 名称 | 是 |
| `--type` | string | 类型 | 否 |
| `--parent-id` | string | 父分类 ID | 否 |
| `--position` | number | 位置 | 否 |
| `--event-name` | string | 事件名称 | 是 |
| `--start-time` | string | 开始时间 (ISO 8601) | 是 |
| `--end-time` | string | 结束时间 (ISO 8601) | 否 |
| `--duration-min` | number | 持续时间（分钟） | 否 |
| `--until` | string | 直到时间 (ISO 8601) | 否 |
| `--delete-days` | number | 删除消息天数 | 否 |
| `--reason` | string | 原因 | 否 |
| `--presence` | string | 在线状态 | 是 |
| `--status` | string | 状态文本 | 否 |

## WebSocket 客户端使用

### 同步 HTTP 请求

```python
from butler.tools.gateway_client import GatewayClient

client = GatewayClient(
    base_url="http://127.0.0.1:18789",
    token="your_token",
    token_header="Authorization",
    timeout_sec=20
)

result = client.get("/v1/health")
print(result)
```

### WebSocket 事件监听

```python
import asyncio
from butler.tools.gateway_client import GatewayWebSocketClient

async def on_message(data):
    print(f"Received: {data}")

async def on_error(error):
    print(f"Error: {error}")

async def on_close(info):
    print(f"Closed: {info}")

async def main():
    client = GatewayWebSocketClient(
        ws_url="ws://127.0.0.1:18789/v1/gateway",
        token="your_token"
    )
    
    client.on_message(on_message)
    client.on_error(on_error)
    client.on_close(on_close)
    
    await client.listen()

asyncio.run(main())
```

### 事件类型订阅

```python
client = GatewayWebSocketClient(
    ws_url="ws://127.0.0.1:18789/v1/gateway",
    token="your_token"
)

@client.on_event("channel.message")
async def handle_message(data):
    print(f"New message: {data}")

@client.on_event("channel.presence")
async def handle_presence(data):
    print(f"Presence update: {data}")
```

### 统一客户端

```python
from butler.tools.gateway_client import GatewayClientV2

client = GatewayClientV2(
    base_url="http://127.0.0.1:18789",
    token="your_token",
    token_header="Authorization",
    timeout_sec=20
)

# HTTP 请求
result = client.post("/v1/chat/completions", {...})

# WebSocket 连接
async with await client.connect_websocket() as ws:
    await ws.send({"action": "subscribe", "events": ["channel.message"]})
```

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

### 7. 使用 WebSocket 重连机制

WebSocket 客户端内置自动重连：
- 默认最多重试 3 次
- 重试间隔 5 秒
- 可配置 `max_retries` 和 `retry_delay`

### 8. 事件驱动架构

利用 WebSocket 事件监听实现实时响应：

```python
@client.on_event("channel.message")
async def handle_new_message(data):
    if data.get("type") == "text":
        await process_message(data)
    elif data.get("type") == "image":
        await process_image(data)
```

## 通道支持

OpenClaw 支持以下消息通道：

| 通道 | channel 值 | 特性 |
|-----|-----------|------|
| Telegram | `telegram` | 完整支持，包括按钮、主题线程、贴纸 |
| WhatsApp | `whatsapp` | 媒体支持，GIF 播放，投票 |
| Slack | `slack` | 按钮支持，Adaptive Cards，表情列表 |
| Discord | `discord` | 投票，主题线程，表情，贴纸，频道管理，事件，管理操作 |
| Google Chat | `googlechat` | 基础消息支持，反应 |
| Signal | `signal` | 基础消息支持，反应 |
| Microsoft Teams | `msteams` | Adaptive Cards 支持，投票 |
| WebChat | `webchat` | 基础消息支持 |

### Discord 特有功能

- **投票**：创建多选项投票，支持多选和时长
- **主题线程**：创建和管理讨论线程
- **表情管理**：列出和上传自定义表情
- **贴纸管理**：发送和上传贴纸
- **频道管理**：创建、编辑、删除频道和分类
- **角色管理**：添加/移除用户角色
- **成员管理**：查询成员信息
- **事件管理**：创建和列出服务器事件
- **管理操作**：超时、踢出、封禁用户
- **搜索功能**：搜索服务器内消息
- **语音状态**：查询用户语音状态
- **在线状态**：设置机器人在线状态

### Telegram 特有功能

- **主题线程**：论坛主题支持
- **贴纸**：发送贴纸（需要配置）
- **内联按钮**：交互式按钮（需要配置）

### WhatsApp 特有功能

- **投票**：创建投票
- **GIF 播放**：视频作为 GIF 播放

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
5. 确认 WebSocket URL 正确（ws:// 或 wss://）

### WebSocket 连接断开

错误：`Connection closed`

解决方案：
1. 检查网络连接
2. 检查 Gateway 服务器日志
3. 调整重连参数（max_retries, retry_delay）
4. 检查 TLS 证书（如使用 wss://）

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

### 通道功能未启用

错误：`feature_not_enabled`

解决方案：
1. 检查通道配置中的功能开关
2. 例如 Discord 需要启用 `polls`, `threads` 等
3. 使用 `openclaw doctor` 检查配置

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

### 4. 创建团队投票

```json
{
  "action_type": "openclaw_message_poll",
  "params": {
    "target": "channel:123",
    "question": "本周团建去哪里？",
    "options": ["KTV", "烧烤", "桌游", "电影"],
    "multi": false,
    "duration_hours": 48,
    "message": "请大家投票选择本周团建活动",
    "channel": "discord"
  }
}
```

### 5. 自动反应新消息

```python
@client.on_event("channel.message")
async def auto_react(data):
    if "help" in data.get("text", "").lower():
        await client.react(
            target=data["channel_id"],
            message_id=data["message_id"],
            emoji="✅",
            channel=data["channel"]
        )
```

### 6. Discord 频道管理

```json
{
  "action_type": "openclaw_channel_create",
  "params": {
    "guild_id": "guild_id",
    "name": "announcements",
    "type": "text",
    "parent_id": "category_id",
    "position": 1,
    "channel": "discord"
  }
}
```

### 7. 广播重要通知

```json
{
  "action_type": "openclaw_broadcast",
  "params": {
    "targets": [
      "telegram:admin1",
      "slack:admin2",
      "discord:channel:alerts"
    ],
    "message": "系统将于今晚 23:00 进行维护",
    "channel": "all"
  }
}
```

## 参考资料

- [OpenClaw 官方文档](https://docs.openclaw.ai/)
- [OpenClaw 安全指南](https://docs.openclaw.ai/gateway/security)
- [OpenClaw 通道配置](https://docs.openclaw.ai/channels)
- [OpenClaw Gateway 协议](https://docs.openclaw.ai/gateway)
- [OpenClaw CLI 参考](https://docs.openclaw.ai/cli)
