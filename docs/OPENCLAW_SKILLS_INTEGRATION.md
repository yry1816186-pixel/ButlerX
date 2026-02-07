# OpenClaw Skills Integration Guide

This document explains how to integrate and reuse OpenClaw Skills in the Smart Butler system.

## Overview

OpenClaw Skills is a reusable toolkit collection with 50+ pre-built skills. Smart Butler can integrate these skills in the following ways:

1. **Directly call OpenClaw CLI** - Use `openclaw exec <skill>` command
2. **Call local services** - For skills running local services (like local-places)
3. **Wrap as tool actions** - Wrap common functions as Smart Butler action types

## 可用的有用技能

### 1. Weather（天气查询）🌤️

**功能**：获取当前天气和预报，无需 API 密钥

**使用方式**：
```bash
curl -s "wttr.in/Beijing?format=3"
```

**Smart Butler Integration Example**:
```python
import requests

def get_weather(city: str = "Beijing") -> str:
    """获取城市天气"""
    url = f"http://wttr.in/{city}?format=%l:+%c+%t+%h+%w"
    response = requests.get(url)
    return response.text
```

**动作定义**：
```json
{
  "action_type": "get_weather",
  "params": {
    "city": "Beijing"
  }
}
```

### 2. Camsnap（摄像头截图）📸

**功能**：从 RTSP/ONVIF 摄像头捕获帧或剪辑

**前置条件**：
- 安装 camsnap：`brew install steipete/tap/camsnap`
- 配置摄像头：`camsnap add --name kitchen --host 192.168.0.10`

**使用方式**：
```bash
# 截图
camsnap snap kitchen --out /tmp/shot.jpg

# 录制片段
camsnap clip kitchen --dur 5s --out /tmp/clip.mp4
```

**Smart Butler Integration Example**:
```python
import subprocess

def camera_snapshot(camera_name: str, output_path: str) -> bool:
    """Capture snapshot from camera"""
    cmd = ["camsnap", "snap", camera_name, "--out", output_path]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0
```

**Action Definition**:
```json
{
  "action_type": "camera_snapshot",
  "params": {
    "camera_name": "kitchen",
    "output_path": "/tmp/snapshot.jpg"
  }
}
```

### 3. Local-Places（本地地点查询）📍

**功能**：通过 Google Places API 代理搜索附近地点

**前置条件**：
- 安装依赖：`cd local-places && uv venv && uv pip install -e ".[dev]"`
- 设置环境变量：`GOOGLE_PLACES_API_KEY=your-key`
- 启动服务：`uvicorn local_places.main:app --host 127.0.0.1 --port 8000`

**使用方式**：
```bash
# 解析位置
curl -X POST http://127.0.0.1:8000/locations/resolve \
  -H "Content-Type: application/json" \
  -d '{"location_text": "朝阳区, 北京", "limit": 5}'

# 搜索地点
curl -X POST http://127.0.0.1:8000/places/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "咖啡店",
    "location_bias": {"lat": 39.9, "lng": 116.4, "radius_m": 1000},
    "filters": {"open_now": true, "min_rating": 4.0}
  }'
```

**Smart Butler Integration Example**:
```python
import requests

class LocalPlacesClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url

    def search_nearby(self, query: str, lat: float, lng: float, radius_m: int = 1000) -> dict:
        """Search nearby places"""
        url = f"{self.base_url}/places/search"
        data = {
            "query": query,
            "location_bias": {"lat": lat, "lng": lng, "radius_m": radius_m},
            "filters": {"open_now": True},
            "limit": 10
        }
        response = requests.post(url, json=data)
        return response.json()
```

**Action Definition**:
```json
{
  "action_type": "search_nearby_places",
  "params": {
    "query": "coffee shop",
    "lat": 39.9,
    "lng": 116.4,
    "radius_m": 1000
  }
}
```

### 4. Session-Logs（会话日志）📝

**功能**：查询 OpenClaw 会话历史日志

**使用方式**：
```bash
openclaw logs session --id <session_id> --limit 10
```

**Smart Butler Integration Example**:
```python
from ..tools.openclaw_cli import OpenClawCLI

def get_session_logs(session_id: str, limit: int = 10) -> dict:
    """Get session logs"""
    openclaw = OpenClawCLI()
    cmd = [openclaw.cli_path, "logs", "session", "--id", session_id, "--limit", str(limit)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {"stdout": result.stdout, "stderr": result.stderr}
```

### 5. Voice-Call（语音通话）📞

**功能**：Make voice calls

**使用方式**：
```bash
openclaw call <contact>
```

**Smart Butler Integration Example**:
```python
def make_voice_call(contact: str) -> dict:
    """Make voice call"""
    cmd = ["openclaw", "call", contact]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {"returncode": result.returncode, "stdout": result.stdout}
```

## 其他可用技能

| 技能 | 描述 | 需要配置 |
|-----|------|---------|
| `summarize` | 内容摘要 | 无 |
| `gifgrep` | 搜索 GIF | 无 |
| `github` | GitHub 操作 | GitHub Token |
| `trello` | Trello 操作 | API Key |
| `notion` | Notion 操作 | API Key |
| `slack` | Slack 操作 | API Token |
| `discord` | Discord 操作 | Bot Token |
| `spotify-player` | Spotify 控制 | Spotify API |
| `sonoscli` | Sonos 控制 | Sonos API |
| `food-order` | 食物订购 | 第三方 API |
| `1password` | 1Password 操作 | API Token |
| `apple-notes` | Apple Notes | macOS 权限 |
| `apple-reminders` | Apple Reminders | macOS 权限 |
| `bear-notes` | Bear Notes | macOS 权限 |
| `obsidian` | Obsidian 操作 | 文件路径 |
| `tmux` | Tmux 会话管理 | 无 |

## 集成方法

### 方法 1：直接 CLI 调用

最简单的方式是直接调用 OpenClaw CLI：

```python
import subprocess

def execute_openclaw_skill(skill: str, args: list) -> dict:
    """执行 OpenClaw 技能"""
    cmd = ["openclaw", skill] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
```

在 [`tool_runner.py`](file:///c:\Users\RichardYuan\Desktop\智慧管家\butler\core\tool_runner.py) 中添加：

```python
elif action_type == "openclaw_skill_weather":
    city = params.get("city", "Beijing")
    output = execute_openclaw_skill("weather", [city])

elif action_type == "openclaw_skill_camsnap":
    camera = params.get("camera")
    output = execute_openclaw_skill("camsnap", ["snap", camera, "--out", "/tmp/snap.jpg"])
```

### 方法 2：封装为工具类

对于复杂的技能，可以创建专门的工具类：

**创建 `butler/tools/camsnap_client.py`**：
```python
import subprocess
from typing import Optional

class CamsnapClient:
    def __init__(self, cli_path: str = "camsnap"):
        self.cli_path = cli_path

    def snapshot(self, camera: str, output_path: str) -> dict:
        """捕获截图"""
        cmd = [self.cli_path, "snap", camera, "--out", output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    def clip(self, camera: str, duration: str, output_path: str) -> dict:
        """录制视频片段"""
        cmd = [self.cli_path, "clip", camera, "--dur", duration, "--out", output_path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
```

**创建 `butler/tools/weather_client.py`**：
```python
import requests

class WeatherClient:
    def __init__(self, api_base: str = "http://wttr.in"):
        self.api_base = api_base

    def get_current(self, city: str = "Beijing") -> str:
        """获取当前天气"""
        url = f"{self.api_base}/{city}?format=%l:+%c+%t+%h+%w"
        response = requests.get(url)
        return response.text

    def get_forecast(self, city: str = "Beijing", days: int = 3) -> str:
        """获取天气预报"""
        url = f"{self.api_base}/{city}?{days}"
        response = requests.get(url)
        return response.text
```

### 方法 3：通过 OpenClaw Gateway

如果启用了 Gateway 模式，可以通过 WebSocket 调用技能：

```python
async def call_skill_via_gateway(gateway: OpenClawGatewayClient, skill: str, params: dict) -> dict:
    """通过 Gateway 调用技能"""
    return await gateway.call("skills.execute", {
        "skill": skill,
        "params": params
    })
```

## 配置示例

### 添加到配置文件

在 [`config.json`](file:///c:\Users\RichardYuan\Desktop\智慧管家\butler\core\config.py) 中添加技能配置：

```json
{
  "skills": {
    "weather": {
      "enabled": true,
      "default_city": "Beijing"
    },
    "camsnap": {
      "enabled": true,
      "cli_path": "camsnap"
    },
    "local_places": {
      "enabled": true,
      "base_url": "http://127.0.0.1:8000",
      "api_key": "your-google-places-api-key"
    }
  }
}
```

### 添加到配置类

在 [`ButlerConfig`](file:///c:\Users\RichardYuan\Desktop\智慧管家\butler\core\config.py) 中添加：

```python
@dataclass
class ButlerConfig:
    # ... 现有字段 ...

    skills_enabled: bool = True
    skills_weather_enabled: bool = True
    skills_weather_default_city: str = "Beijing"
    skills_camsnap_enabled: bool = True
    skills_camsnap_cli_path: str = "camsnap"
    skills_local_places_enabled: bool = False
    skills_local_places_base_url: str = "http://127.0.0.1:8000"
    skills_local_places_api_key: str = ""
```

## 完整集成示例

### 在 tool_runner.py 中集成

```python
from ..tools.camsnap_client import CamsnapClient
from ..tools.weather_client import WeatherClient

class ToolRunner:
    def __init__(self, config: ButlerConfig, ...):
        # ... 现有初始化 ...
        self.weather = WeatherClient()
        self.camsnap = CamsnapClient(config.skills_camsnap_cli_path)

    def run_action(self, action: Dict[str, Any]) -> ActionResult:
        action_type = action.get("action_type")
        params = action.get("params", {})
        status = "ok"
        output = None

        # ... 现有动作处理 ...

        elif action_type == "get_weather":
            city = params.get("city", self.config.skills_weather_default_city)
            output = {"weather": self.weather.get_current(city)}

        elif action_type == "camera_snapshot":
            camera = params.get("camera")
            output_path = params.get("output_path", "/tmp/snapshot.jpg")
            output = self.camsnap.snapshot(camera, output_path)

        # ... 其他动作处理 ...
```

## 最佳实践

1. **检查技能可用性**：在调用前检查技能是否已安装和配置
2. **错误处理**：妥善处理技能执行失败的情况
3. **缓存结果**：对于天气等不常变化的数据，考虑缓存
4. **权限管理**：确保技能有足够的权限执行操作
5. **性能优化**：对于频繁调用的技能，考虑使用 Gateway 模式

## 参考资料

- [OpenClaw Skills 文档](https://docs.openclaw.ai/tools/skills)
- [OpenClaw Skills 配置](https://docs.openclaw.ai/tools/skills-config)
- [OpenClaw 创建自定义技能](https://docs.openclaw.ai/tools/creating-skills)
