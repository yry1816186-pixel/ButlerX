from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

logger = logging.getLogger(__name__)


class SkillCategory(Enum):
    DEVICE = "device"
    COMMUNICATION = "communication"
    VISION = "vision"
    VOICE = "voice"
    LIFE_ASSISTANT = "life_assistant"
    AUTOMATION = "automation"
    INTEGRATION = "integration"
    CUSTOM = "custom"


@dataclass
class SkillCommandSpec:
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    examples: List[str] = field(default_factory=list)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "examples": self.examples,
            "enabled": self.enabled,
        }


@dataclass
class SkillMetadata:
    name: str
    version: str
    author: str
    description: str
    category: SkillCategory
    dependencies: List[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "author": self.author,
            "description": self.description,
            "category": self.category.value,
            "dependencies": self.dependencies,
            "config_schema": self.config_schema,
            "enabled": self.enabled,
        }


@dataclass
class SkillContext:
    conversation_id: str
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SkillResult:
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


class Skill(ABC):
    metadata: SkillMetadata
    commands: Dict[str, SkillCommandSpec]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = self.metadata.enabled

    @abstractmethod
    async def initialize(self) -> bool:
        pass

    @abstractmethod
    async def shutdown(self) -> bool:
        pass

    @abstractmethod
    async def execute(
        self, command: str, params: Dict[str, Any], context: SkillContext
    ) -> SkillResult:
        pass

    def get_commands(self) -> Dict[str, SkillCommandSpec]:
        return {
            name: spec
            for name, spec in self.commands.items()
            if spec.enabled and self.enabled
        }

    def get_command_spec(self, command: str) -> Optional[SkillCommandSpec]:
        return self.commands.get(command)

    def is_command_available(self, command: str) -> bool:
        spec = self.get_command_spec(command)
        return spec is not None and spec.enabled and self.enabled

    async def validate_config(self, config: Dict[str, Any]) -> bool:
        return True

    async def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.metadata.name,
            "version": self.metadata.version,
            "enabled": self.enabled,
            "initialized": True,
            "commands": list(self.get_commands().keys()),
        }


class SkillRegistry:
    def __init__(self):
        self._skills: Dict[str, Skill] = {}
        self._skill_classes: Dict[str, Type[Skill]] = {}
        self._command_map: Dict[str, str] = {}
        self._listeners: List[Callable] = []

    def register_class(self, skill_class: Type[Skill]):
        metadata = getattr(skill_class, "metadata", None)
        if not metadata:
            logger.warning(f"Skill class {skill_class.__name__} has no metadata")
            return

        self._skill_classes[metadata.name] = skill_class
        logger.info(f"Registered skill class: {metadata.name}")

    def register_skill(self, skill: Skill) -> bool:
        try:
            if not skill.enabled:
                logger.info(f"Skill disabled: {skill.metadata.name}")
                return False

            self._skills[skill.metadata.name] = skill

            for command_name in skill.commands.keys():
                self._command_map[command_name] = skill.metadata.name

            self._notify_listeners("skill_registered", skill)
            logger.info(f"Registered skill: {skill.metadata.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to register skill {skill.metadata.name}: {e}")
            return False

    def unregister_skill(self, skill_name: str) -> bool:
        if skill_name not in self._skills:
            logger.warning(f"Skill not found: {skill_name}")
            return False

        skill = self._skills[skill_name]

        for command_name, cmd_skill_name in list(self._command_map.items()):
            if cmd_skill_name == skill_name:
                del self._command_map[command_name]

        del self._skills[skill_name]

        self._notify_listeners("skill_unregistered", skill)
        logger.info(f"Unregistered skill: {skill_name}")
        return True

    async def initialize_skill(
        self, skill_class: Type[Skill], config: Optional[Dict[str, Any]] = None
    ) -> bool:
        try:
            metadata = getattr(skill_class, "metadata", None)
            if not metadata:
                logger.warning(f"Skill class has no metadata: {skill_class.__name__}")
                return False

            if not metadata.enabled:
                logger.info(f"Skill disabled: {metadata.name}")
                return False

            skill = skill_class(config or {})

            initialized = await skill.initialize()
            if not initialized:
                logger.error(f"Failed to initialize skill: {metadata.name}")
                return False

            return self.register_skill(skill)

        except Exception as e:
            logger.error(f"Failed to initialize skill {skill_class.__name__}: {e}")
            return False

    async def execute_command(
        self, command: str, params: Dict[str, Any], context: SkillContext
    ) -> SkillResult:
        skill_name = self._command_map.get(command)

        if not skill_name:
            logger.warning(f"Command not found: {command}")
            return SkillResult(
                success=False, error=f"Command not found: {command}"
            )

        skill = self._skills.get(skill_name)
        if not skill:
            logger.warning(f"Skill not loaded: {skill_name}")
            return SkillResult(
                success=False, error=f"Skill not loaded: {skill_name}"
            )

        if not skill.is_command_available(command):
            logger.warning(f"Command not available: {command}")
            return SkillResult(
                success=False, error=f"Command not available: {command}"
            )

        try:
            result = await skill.execute(command, params, context)
            return result

        except Exception as e:
            logger.error(f"Error executing command {command}: {e}")
            return SkillResult(
                success=False, error=f"Error executing command: {e}"
            )

    def get_skill(self, skill_name: str) -> Optional[Skill]:
        return self._skills.get(skill_name)

    def get_all_skills(self) -> Dict[str, Skill]:
        return self._skills.copy()

    def get_skill_metadata(self, skill_name: str) -> Optional[SkillMetadata]:
        skill = self._skills.get(skill_name)
        return skill.metadata if skill else None

    def get_all_metadata(self) -> List[SkillMetadata]:
        return [skill.metadata for skill in self._skills.values()]

    def get_all_commands(self) -> Dict[str, SkillCommandSpec]:
        all_commands = {}
        for skill in self._skills.values():
            all_commands.update(skill.get_commands())
        return all_commands

    def get_command_owner(self, command: str) -> Optional[str]:
        return self._command_map.get(command)

    def get_commands_by_skill(self, skill_name: str) -> Dict[str, SkillCommandSpec]:
        skill = self._skills.get(skill_name)
        return skill.get_commands() if skill else {}

    def get_commands_by_category(
        self, category: SkillCategory
    ) -> Dict[str, SkillCommandSpec]:
        commands = {}
        for skill in self._skills.values():
            if skill.metadata.category == category:
                commands.update(skill.get_commands())
        return commands

    async def shutdown_all(self):
        tasks = []
        for skill in self._skills.values():
            try:
                tasks.append(skill.shutdown())
            except Exception as e:
                logger.error(f"Error shutting down skill {skill.metadata.name}: {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._skills.clear()
        self._command_map.clear()

        logger.info("All skills shut down")

    def add_listener(self, listener: Callable):
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable):
        if listener in self._listeners:
            self._listeners.remove(listener)

    def _notify_listeners(self, event_type: str, data: Any):
        for listener in self._listeners:
            try:
                listener(event_type, data)
            except Exception as e:
                logger.error(f"Skill listener error: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        skills_by_category = {}
        for skill in self._skills.values():
            category = skill.metadata.category.value
            if category not in skills_by_category:
                skills_by_category[category] = 0
            skills_by_category[category] += 1

        return {
            "total_skills": len(self._skills),
            "total_commands": len(self._command_map),
            "skills_by_category": skills_by_category,
            "enabled_skills": sum(1 for s in self._skills.values() if s.enabled),
        }


def skill(
    name: str,
    version: str = "1.0.0",
    author: str = "",
    description: str = "",
    category: SkillCategory = SkillCategory.CUSTOM,
    dependencies: Optional[List[str]] = None,
    config_schema: Optional[Dict[str, Any]] = None,
):
    def decorator(cls: Type[Skill]) -> Type[Skill]:
        metadata = SkillMetadata(
            name=name,
            version=version,
            author=author,
            description=description,
            category=category,
            dependencies=dependencies or [],
            config_schema=config_schema,
        )

        cls.metadata = metadata
        return cls

    return decorator
