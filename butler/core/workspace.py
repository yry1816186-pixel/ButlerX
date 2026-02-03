from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceTemplate:
    name: str
    filename: str
    content: str
    description: str = ""
    required: bool = False


class WorkspaceTemplates:
    DEFAULT_AGENTS = """# 智能助手配置

## 当前可用的助手

### 主助手
- **名称**: 小管家
- **角色**: 智能家居管家
- **能力**: 设备控制、对话、日程管理、生活助手

### 技能助手
- **视觉助手**: 物体检测、人脸识别
- **语音助手**: 语音识别、语音合成
- **监控助手**: 摄像头控制、异常检测
"""

    DEFAULT_SOUL = """# 助手灵魂 (SOUL)

## 个性设定

你是一个智能家居管家助手，名字叫"小管家"。

### 核心价值观
- **服务至上**: 以用户需求为中心，主动提供帮助
- **温和友善**: 语气亲切自然，像朋友一样交流
- **值得信赖**: 保护用户隐私，准确执行任务
- **持续学习**: 记住用户偏好，不断优化服务

### 交流风格
- 使用简洁、自然的中文
- 适当使用表情符号增加亲和力
- 避免机械化的回复
- 主动关心用户的生活状态

### 决策原则
1. 优先理解用户真实意图
2. 优先使用已有的自动化规则
3. 对于不确定的操作，先询问用户确认
4. 执行后主动反馈结果
"""

    DEFAULT_TOOLS = """# 可用工具清单

## 设备控制工具
- `device_turn_on`: 打开设备
- `device_turn_off`: 关闭设备
- `device_toggle`: 切换设备状态
- `device_set_brightness`: 设置亮度
- `device_set_temperature`: 设置温度

## 通信工具
- `notify`: 发送通知
- `openclaw_message_send`: 发送消息到多平台
- `email_send`: 发送邮件

## 生活助手工具
- `calendar_add`: 添加日历事件
- `calendar_list`: 查看日程
- `shopping_add`: 添加购物项
- `shopping_list`: 查看购物清单

## 视觉工具
- `vision_detect`: 图像检测
- `face_enroll`: 录入人脸
- `face_verify`: 验证人脸

## 语音工具
- `voice_transcribe`: 语音转文字
- `voice_enroll`: 录入声纹

## 媒体工具
- `image_generate`: 生成图片
- `ptz_goto_preset`: 摄像头移动到预设位
- `snapshot`: 拍照
"""

    DEFAULT_IDENTITY = """# 助手身份配置

## 基本信息
- **名称**: 小管家
- **版本**: 2.0
- **创建日期**: 2026年

## 功能定位
专注于智能家居管理，为用户提供便捷的语音和自然语言交互体验。

## 技术架构
- **LLM**: GLM-4.7
- **视觉**: YOLO + Face Recognition
- **语音**: Faster-Whisper + Piper-TTS
- **内存**: 向量搜索 + 全文搜索
- **通信**: OpenClaw 多平台支持

## 集成能力
- Home Assistant
- MQTT 设备
- DaShan 机器人
- 可移动摄像头
"""

    DEFAULT_USER = """# 用户配置

## 用户偏好

### 设备命名
- `light_living_room`: 客厅灯
- `light_bedroom`: 卧室灯
- `climate_living_room`: 客厅空调

### 场景偏好
- 回家场景: 开灯、开空调、播放音乐
- 离家场景: 关灯、关空调、启动安防
- 睡眠场景: 关灯、调暗、静音模式

### 时间偏好
- 起床时间: 07:00
- 睡眠时间: 23:00
- 工作时间: 09:00-18:00

## 个性化设置
请在此添加您的个性化偏好设置，让小管家更好地为您服务。
"""

    DEFAULT_MEMORY = """# 助手记忆

## 重要记忆
- 用户名字: 请在对话中记录
- 家庭成员: 请在对话中记录
- 常用指令: 请在对话中学习

## 学习内容
- 用户习惯: 通过对话逐步学习
- 偏好设置: 记住用户的偏好
- 常用场景: 优化常用场景的响应

## 注意事项
- 保护用户隐私
- 不记录敏感信息
- 定期清理过期记忆
"""

    DEFAULT_BOOTSTRAP = """# 工作区引导

## 欢迎使用智慧管家

本工作区包含智慧管家系统的所有配置和自定义文件。

## 目录结构
- `AGENTS.md`: 助手配置
- `SOUL.md`: 助手个性
- `TOOLS.md`: 工具清单
- `IDENTITY.md`: 身份配置
- `USER.md`: 用户偏好
- `MEMORY.md`: 记忆管理
- `BOOTSTRAP.md`: 本文件

## 自定义指南

1. 修改 `USER.md` 添加您的个人偏好
2. 在 `SOUL.md` 中调整助手的个性
3. 在 `TOOLS.md` 中添加自定义工具
4. 在 `MEMORY.md` 中记录重要信息

## 开始使用

运行以下命令启动服务：
```bash
python -m butler.core.main
```

访问 Web UI: http://localhost:8000
"""


class WorkspaceManager:
    def __init__(self, workspace_dir: Optional[str] = None):
        if workspace_dir:
            self.workspace_dir = Path(workspace_dir)
        else:
            self.workspace_dir = Path.cwd() / "workspace"

        self.templates: Dict[str, WorkspaceTemplate] = {}
        self._initialize_templates()

    def _initialize_templates(self):
        self.templates = {
            "AGENTS.md": WorkspaceTemplate(
                name="Agents配置",
                filename="AGENTS.md",
                content=WorkspaceTemplates.DEFAULT_AGENTS,
                description="智能助手配置",
                required=True,
            ),
            "SOUL.md": WorkspaceTemplate(
                name="助手灵魂",
                filename="SOUL.md",
                content=WorkspaceTemplates.DEFAULT_SOUL,
                description="助手的个性和价值观",
                required=True,
            ),
            "TOOLS.md": WorkspaceTemplate(
                name="工具清单",
                filename="TOOLS.md",
                content=WorkspaceTemplates.DEFAULT_TOOLS,
                description="可用工具清单",
                required=True,
            ),
            "IDENTITY.md": WorkspaceTemplate(
                name="身份配置",
                filename="IDENTITY.md",
                content=WorkspaceTemplates.DEFAULT_IDENTITY,
                description="助手身份信息",
                required=True,
            ),
            "USER.md": WorkspaceTemplate(
                name="用户配置",
                filename="USER.md",
                content=WorkspaceTemplates.DEFAULT_USER,
                description="用户偏好设置",
                required=True,
            ),
            "MEMORY.md": WorkspaceTemplate(
                name="记忆管理",
                filename="MEMORY.md",
                content=WorkspaceTemplates.DEFAULT_MEMORY,
                description="助手记忆内容",
                required=False,
            ),
            "BOOTSTRAP.md": WorkspaceTemplate(
                name="工作区引导",
                filename="BOOTSTRAP.md",
                content=WorkspaceTemplates.DEFAULT_BOOTSTRAP,
                description="工作区使用指南",
                required=True,
            ),
        }

    def ensure_workspace(
        self, create_missing: bool = True, overwrite: bool = False
    ) -> Dict[str, Any]:
        results = {
            "workspace_dir": str(self.workspace_dir),
            "created": False,
            "files": {},
            "errors": [],
        }

        try:
            self.workspace_dir.mkdir(parents=True, exist_ok=True)

            if not self.workspace_dir.exists():
                raise ValueError(f"Failed to create workspace: {self.workspace_dir}")

            results["created"] = True

            for filename, template in self.templates.items():
                file_path = self.workspace_dir / filename

                if file_path.exists() and not overwrite:
                    results["files"][filename] = {"status": "exists", "path": str(file_path)}
                    continue

                if create_missing or overwrite:
                    try:
                        file_path.write_text(
                            template.content, encoding="utf-8"
                        )
                        results["files"][filename] = {
                            "status": "created" if overwrite or not file_path.exists() else "updated",
                            "path": str(file_path),
                        }
                        logger.info(f"Created workspace file: {filename}")

                    except Exception as e:
                        error = f"Failed to create {filename}: {e}"
                        results["errors"].append(error)
                        logger.error(error)

            self._ensure_git_repo()

            logger.info(f"Workspace initialized: {self.workspace_dir}")
            return results

        except Exception as e:
            error = f"Failed to initialize workspace: {e}"
            results["errors"].append(error)
            logger.error(error)
            return results

    def _ensure_git_repo(self):
        try:
            if (self.workspace_dir / ".git").exists():
                return

            import subprocess

            subprocess.run(
                ["git", "init"],
                cwd=self.workspace_dir,
                capture_output=True,
                check=False,
            )

            gitignore_path = self.workspace_dir / ".gitignore"
            if not gitignore_path.exists():
                gitignore_path.write_text(
                    "# Butler workspace\n*.db\n*.db-shm\n*.db-wal\n__pycache__/\n",
                    encoding="utf-8",
                )

            logger.info("Git repository initialized")

        except FileNotFoundError:
            logger.warning("Git not found, skipping repository initialization")
        except Exception as e:
            logger.warning(f"Failed to initialize git repo: {e}")

    def get_template(self, filename: str) -> Optional[WorkspaceTemplate]:
        return self.templates.get(filename)

    def get_all_templates(self) -> Dict[str, WorkspaceTemplate]:
        return self.templates.copy()

    def get_file_content(self, filename: str) -> Optional[str]:
        file_path = self.workspace_dir / filename
        if not file_path.exists():
            return None

        try:
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read {filename}: {e}")
            return None

    def update_file(
        self, filename: str, content: str, create_if_missing: bool = True
    ) -> bool:
        file_path = self.workspace_dir / filename

        if not file_path.exists():
            if create_if_missing:
                logger.info(f"Creating new file: {filename}")
            else:
                logger.warning(f"File not found: {filename}")
                return False

        try:
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"Updated file: {filename}")
            return True

        except Exception as e:
            logger.error(f"Failed to update {filename}: {e}")
            return False

    def get_workspace_status(self) -> Dict[str, Any]:
        status = {
            "workspace_dir": str(self.workspace_dir),
            "exists": self.workspace_dir.exists(),
            "files": {},
            "missing_required": [],
        }

        if not status["exists"]:
            return status

        for filename, template in self.templates.items():
            file_path = self.workspace_dir / filename
            exists = file_path.exists()

            status["files"][filename] = {
                "exists": exists,
                "path": str(file_path),
                "required": template.required,
            }

            if template.required and not exists:
                status["missing_required"].append(filename)

        return status

    def validate_workspace(self) -> Dict[str, Any]:
        status = self.get_workspace_status()
        errors = []
        warnings = []

        if not status["exists"]:
            errors.append("工作区目录不存在")
            return {"valid": False, "errors": errors, "warnings": warnings}

        if status["missing_required"]:
            errors.append(
                f"缺少必需文件: {', '.join(status['missing_required'])}"
            )

        for filename, file_status in status["files"].items():
            if file_status["exists"]:
                content = self.get_file_content(filename)
                if not content or len(content.strip()) == 0:
                    warnings.append(f"{filename} 文件为空")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def create_custom_file(
        self, filename: str, content: str, description: str = ""
    ) -> bool:
        template = WorkspaceTemplate(
            name=filename,
            filename=filename,
            content=content,
            description=description,
            required=False,
        )

        self.templates[filename] = template

        return self.update_file(filename, content, create_if_missing=True)

    def delete_file(self, filename: str) -> bool:
        file_path = self.workspace_dir / filename

        if not file_path.exists():
            logger.warning(f"File not found: {filename}")
            return False

        try:
            file_path.unlink()
            logger.info(f"Deleted file: {filename}")

            if filename in self.templates and not self.templates[filename].required:
                del self.templates[filename]

            return True

        except Exception as e:
            logger.error(f"Failed to delete {filename}: {e}")
            return False

    def list_files(self) -> List[Dict[str, Any]]:
        if not self.workspace_dir.exists():
            return []

        files = []
        for path in self.workspace_dir.iterdir():
            if path.is_file():
                files.append(
                    {
                        "name": path.name,
                        "path": str(path),
                        "size": path.stat().st_size,
                        "modified": path.stat().st_mtime,
                    }
                )

        return sorted(files, key=lambda x: x["name"])

    def backup_workspace(self, backup_dir: Optional[str] = None) -> str:
        import shutil
        from datetime import datetime

        if not self.workspace_dir.exists():
            raise ValueError("工作区不存在，无法备份")

        if backup_dir:
            backup_path = Path(backup_dir)
        else:
            backup_path = self.workspace_dir.parent / "backups"

        backup_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"workspace_backup_{timestamp}"
        backup_dest = backup_path / backup_name

        shutil.copytree(self.workspace_dir, backup_dest)

        logger.info(f"Workspace backed up to: {backup_dest}")
        return str(backup_dest)

    def restore_workspace(self, backup_path: str) -> bool:
        import shutil

        backup_dir = Path(backup_path)

        if not backup_dir.exists():
            logger.error(f"Backup not found: {backup_path}")
            return False

        try:
            if self.workspace_dir.exists():
                shutil.rmtree(self.workspace_dir)

            shutil.copytree(backup_dir, self.workspace_dir)

            logger.info(f"Workspace restored from: {backup_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to restore workspace: {e}")
            return False


def create_workspace_manager(workspace_dir: Optional[str] = None) -> WorkspaceManager:
    return WorkspaceManager(workspace_dir)
