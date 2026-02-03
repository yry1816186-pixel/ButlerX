from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from .ptz_controller import PTZPosition

logger = logging.getLogger(__name__)


class ExpressionCategory(Enum):
    BASE = "base"
    EMOTIONAL = "emotional"
    REACTIVE = "reactive"
    COMMUNICATION = "communication"
    IDLE = "idle"


class ExpressionMood(Enum):
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    SURPRISED = "surprised"
    ANGRY = "angry"
    CURIOUS = "curious"
    SHY = "shy"
    TIRED = "tired"
    EXCITED = "excited"
    CONFUSED = "confused"
    THINKING = "thinking"
    LISTENING = "listening"
    SPEAKING = "speaking"


@dataclass
class ExpressionLayer:
    expression_id: int
    intensity: float = 1.0
    blend_mode: str = "normal"
    priority: int = 0
    duration: Optional[float] = None
    started_at: float = field(default_factory=time.time)

    def get_age(self) -> float:
        return time.time() - self.started_at

    def is_expired(self) -> bool:
        if self.duration is None:
            return False
        return self.get_age() >= self.duration


@dataclass
class MicroExpression:
    name: str
    expression_id: int
    duration: float = 0.2
    intensity: float = 0.5


@dataclass
class ExpressionPreset:
    name: str
    mood: ExpressionMood
    expression_id: int
    ptz_position: Optional[PTZPosition] = None
    brightness: int = 255
    animations: List[str] = field(default_factory=list)
    micro_expressions: List[MicroExpression] = field(default_factory=list)
    transition_duration: float = 0.3


class EnhancedExpressionEngine:
    def __init__(self):
        self.presets: Dict[str, ExpressionPreset] = {}
        self.layers: List[ExpressionLayer] = []
        self.current_mood = ExpressionMood.NEUTRAL
        self.target_mood = ExpressionMood.NEUTRAL
        self.mood_transition_speed = 0.1

        self._callback: Optional[Callable[[int, int, int, int], None]] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._idle_task: Optional[asyncio.Task] = None

        self._init_presets()

    def _init_presets(self) -> None:
        self.presets["neutral"] = ExpressionPreset(
            name="neutral",
            mood=ExpressionMood.NEUTRAL,
            expression_id=0x02,
            ptz_position=PTZPosition(pan=90, tilt=90),
        )

        self.presets["happy"] = ExpressionPreset(
            name="happy",
            mood=ExpressionMood.HAPPY,
            expression_id=0x05,
            ptz_position=PTZPosition(pan=90, tilt=88),
            animations=["nod"],
            micro_expressions=[
                MicroExpression("blink", 0x00, 0.2, 0.3),
            ],
        )

        self.presets["sad"] = ExpressionPreset(
            name="sad",
            mood=ExpressionMood.SAD,
            expression_id=0x06,
            ptz_position=PTZPosition(pan=90, tilt=95),
            brightness=200,
        )

        self.presets["surprised"] = ExpressionPreset(
            name="surprised",
            mood=ExpressionMood.SURPRISED,
            expression_id=0x07,
            ptz_position=PTZPosition(pan=90, tilt=85),
            transition_duration=0.1,
        )

        self.presets["angry"] = ExpressionPreset(
            name="angry",
            mood=ExpressionMood.ANGRY,
            expression_id=0x0B,
            ptz_position=PTZPosition(pan=90, tilt=92),
            brightness=255,
            animations=["shake"],
        )

        self.presets["curious"] = ExpressionPreset(
            name="curious",
            mood=ExpressionMood.CURIOUS,
            expression_id=0x09,
            ptz_position=PTZPosition(pan=90, tilt=87),
            animations=["tilt"],
        )

        self.presets["shy"] = ExpressionPreset(
            name="shy",
            mood=ExpressionMood.SHY,
            expression_id=0x0A,
            ptz_position=PTZPosition(pan=90, tilt=95),
            brightness=200,
            animations=["look_left", "look_right"],
        )

        self.presets["tired"] = ExpressionPreset(
            name="tired",
            mood=ExpressionMood.TIRED,
            expression_id=0x0D,
            ptz_position=PTZPosition(pan=90, tilt=95),
            brightness=180,
        )

        self.presets["excited"] = ExpressionPreset(
            name="excited",
            mood=ExpressionMood.EXCITED,
            expression_id=0x0E,
            ptz_position=PTZPosition(pan=90, tilt=88),
            brightness=255,
            animations=["nod", "nod"],
        )

        self.presets["confused"] = ExpressionPreset(
            name="confused",
            mood=ExpressionMood.CONFUSED,
            expression_id=0x08,
            ptz_position=PTZPosition(pan=90, tilt=93),
            animations=["tilt", "shake"],
        )

        self.presets["thinking"] = ExpressionPreset(
            name="thinking",
            mood=ExpressionMood.THINKING,
            expression_id=0x03,
            ptz_position=PTZPosition(pan=88, tilt=88),
            brightness=220,
            animations=["think"],
        )

        self.presets["listening"] = ExpressionPreset(
            name="listening",
            mood=ExpressionMood.LISTENING,
            expression_id=0x02,
            ptz_position=PTZPosition(pan=90, tilt=90),
            brightness=255,
            micro_expressions=[
                MicroExpression("blink", 0x00, 0.15, 0.2),
            ],
        )

        self.presets["speaking"] = ExpressionPreset(
            name="speaking",
            mood=ExpressionMood.SPEAKING,
            expression_id=0x04,
            ptz_position=PTZPosition(pan=90, tilt=90),
            brightness=255,
        )

    def set_callback(self, callback: Callable[[int, int, int, int], None]) -> None:
        self._callback = callback

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._update_loop())
        self._idle_task = asyncio.create_task(self._idle_behavior_loop())
        logger.info("Enhanced expression engine started")

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._idle_task:
            self._idle_task.cancel()
            try:
                await self._idle_task
            except asyncio.CancelledError:
                pass

        logger.info("Enhanced expression engine stopped")

    async def _update_loop(self) -> None:
        while self._running:
            await self._update()
            await asyncio.sleep(0.016)

    async def _update(self) -> None:
        self._update_mood_transition()
        self._cleanup_expired_layers()

        final_expression, brightness, pan, tilt = self._compose_expression()

        if self._callback:
            self._callback(final_expression, brightness, int(pan), int(tilt))

    def _update_mood_transition(self) -> None:
        if self.target_mood != self.current_mood:
            if random.random() < self.mood_transition_speed:
                self.current_mood = self.target_mood
                logger.debug(f"Mood transitioned to: {self.current_mood.value}")

    def _cleanup_expired_layers(self) -> None:
        self.layers = [layer for layer in self.layers if not layer.is_expired()]

    def _compose_expression(self) -> Tuple[int, int, float, float]:
        if not self.layers:
            preset = self.presets.get(self.current_mood.value)
            if preset:
                expression = preset.expression_id
                brightness = preset.brightness
                pan = preset.ptz_position.pan if preset.ptz_position else 90.0
                tilt = preset.ptz_position.tilt if preset.ptz_position else 90.0
            else:
                expression = 0x02
                brightness = 255
                pan = 90.0
                tilt = 90.0
        else:
            sorted_layers = sorted(self.layers, key=lambda l: l.priority, reverse=True)
            top_layer = sorted_layers[0]

            expression = top_layer.expression_id
            brightness = 255
            pan = 90.0
            tilt = 90.0

            for layer in sorted_layers[1:]:
                if layer.blend_mode == "multiply":
                    brightness = int(brightness * layer.intensity)
                elif layer.blend_mode == "add":
                    brightness = min(255, brightness + int(50 * layer.intensity))

        return expression, brightness, pan, tilt

    async def _idle_behavior_loop(self) -> None:
        idle_behaviors = [
            ("blink", 0.1),
            ("subtle_nod", 0.05),
            ("look_around", 0.03),
            ("yawn", 0.01),
        ]

        while self._running:
            await asyncio.sleep(1.0)

            if self.current_mood not in [ExpressionMood.SPEAKING, ExpressionMood.THINKING]:
                rand = random.random()
                cumulative = 0.0

                for behavior, probability in idle_behaviors:
                    cumulative += probability
                    if rand < cumulative:
                        await self._play_idle_behavior(behavior)
                        break

    async def _play_idle_behavior(self, behavior: str) -> None:
        if behavior == "blink":
            await self.add_layer(ExpressionLayer(
                expression_id=0x00,
                intensity=1.0,
                duration=0.15,
                priority=10,
            ))
            await asyncio.sleep(0.15)

        elif behavior == "subtle_nod":
            await self.add_layer(ExpressionLayer(
                expression_id=0x02,
                intensity=1.0,
                duration=0.5,
                priority=5,
            ))
            await asyncio.sleep(0.5)

        elif behavior == "look_around":
            directions = [(85, 90), (95, 90), (90, 85), (90, 95)]
            for pan, tilt in directions:
                if not self._running:
                    break
                await self.add_layer(ExpressionLayer(
                    expression_id=0x02,
                    intensity=1.0,
                    duration=0.3,
                    priority=3,
                ))
                await asyncio.sleep(0.3)

        elif behavior == "yawn":
            if self.current_mood == ExpressionMood.TIRED:
                await self.add_layer(ExpressionLayer(
                    expression_id=0x0D,
                    intensity=1.0,
                    duration=1.5,
                    priority=8,
                ))
                await asyncio.sleep(1.5)

    async def set_mood(self, mood: ExpressionMood, transition_speed: float = 0.1) -> None:
        self.target_mood = mood
        self.mood_transition_speed = transition_speed
        logger.info(f"Setting mood to: {mood.value}")

    async def play_preset(self, preset_name: str, duration: Optional[float] = None) -> None:
        preset = self.presets.get(preset_name)
        if not preset:
            logger.warning(f"Preset not found: {preset_name}")
            return

        await self.set_mood(preset.mood)

        await self.add_layer(ExpressionLayer(
            expression_id=preset.expression_id,
            intensity=1.0,
            duration=duration or preset.transition_duration,
            priority=5,
        ))

        for anim in preset.animations:
            await self._play_animation(anim)

        for micro in preset.micro_expressions:
            await self._play_micro_expression(micro)

    async def _play_animation(self, animation_name: str) -> None:
        logger.debug(f"Playing animation: {animation_name}")

    async def _play_micro_expression(self, micro: MicroExpression) -> None:
        await asyncio.sleep(random.uniform(0.1, 0.5))

        await self.add_layer(ExpressionLayer(
            expression_id=micro.expression_id,
            intensity=micro.intensity,
            duration=micro.duration,
            priority=15,
        ))

    async def add_layer(self, layer: ExpressionLayer) -> None:
        self.layers.append(layer)

    async def clear_layers(self, priority: Optional[int] = None) -> None:
        if priority is None:
            self.layers.clear()
        else:
            self.layers = [l for l in self.layers if l.priority != priority]

    def get_preset(self, name: str) -> Optional[ExpressionPreset]:
        return self.presets.get(name)

    def add_preset(self, preset: ExpressionPreset) -> None:
        self.presets[preset.name] = preset
        logger.info(f"Added expression preset: {preset.name}")

    def remove_preset(self, name: str) -> bool:
        if name in self.presets and name != "neutral":
            del self.presets[name]
            return True
        return False

    def get_current_mood(self) -> ExpressionMood:
        return self.current_mood

    def get_active_layers(self) -> List[ExpressionLayer]:
        return self.layers.copy()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_mood": self.current_mood.value,
            "target_mood": self.target_mood.value,
            "active_layers": len(self.layers),
            "presets": list(self.presets.keys()),
        }


class ExpressionBuilder:
    def __init__(self):
        self.base_expression = 0x02
        self.brightness = 255
        self.pan = 90.0
        self.tilt = 90.0
        self.animations: List[str] = []
        self.micro_expressions: List[MicroExpression] = []

    def with_expression(self, expression_id: int) -> "ExpressionBuilder":
        self.base_expression = expression_id
        return self

    def with_brightness(self, brightness: int) -> "ExpressionBuilder":
        self.brightness = max(0, min(255, brightness))
        return self

    def with_position(self, pan: float, tilt: float) -> "ExpressionBuilder":
        self.pan = max(0.0, min(180.0, pan))
        self.tilt = max(0.0, min(180.0, tilt))
        return self

    def with_animation(self, animation: str) -> "ExpressionBuilder":
        self.animations.append(animation)
        return self

    def with_micro_expression(self, micro: MicroExpression) -> "ExpressionBuilder":
        self.micro_expressions.append(micro)
        return self

    def build(self) -> ExpressionPreset:
        return ExpressionPreset(
            name=f"custom_{int(time.time())}",
            mood=ExpressionMood.NEUTRAL,
            expression_id=self.base_expression,
            ptz_position=PTZPosition(pan=self.pan, tilt=self.tilt),
            brightness=self.brightness,
            animations=self.animations,
            micro_expressions=self.micro_expressions,
        )


if __name__ == "__main__":
    import sys

    async def main():
        engine = EnhancedExpressionEngine()

        def callback(expression, brightness, pan, tilt):
            print(f"Expression: 0x{expression:02X}, Brightness: {brightness}, Pan: {pan}, Tilt: {tilt}")

        engine.set_callback(callback)

        await engine.start()

        print("Enhanced Expression Engine Test")
        print("Available presets:", list(engine.presets.keys()))

        try:
            while True:
                cmd = input("\nEnter preset name (or 'quit'): ").strip().lower()

                if cmd == "quit":
                    break

                if cmd in engine.presets:
                    await engine.play_preset(cmd)
                    await asyncio.sleep(2.0)
                else:
                    print(f"Unknown preset: {cmd}")

        except KeyboardInterrupt:
            pass

        await engine.stop()

    asyncio.run(main())
