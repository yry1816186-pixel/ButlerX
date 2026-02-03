from __future__ import annotations

import asyncio
import logging
import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class PTZMode(Enum):
    MANUAL = "manual"
    AUTO_TRACK = "auto_track"
    GAZE_FOLLOW = "gaze_follow"
    RANDOM_IDLE = "random_idle"
    SCENE_SCAN = "scene_scan"


class MovementType(Enum):
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"
    EASE_OUT_IN = "ease_out_in"
    BOUNCE = "bounce"
    ELASTIC = "elastic"


@dataclass
class PTZPosition:
    pan: float
    tilt: float
    zoom: float = 1.0
    brightness: int = 255
    timestamp: float = field(default_factory=time.time)

    def distance_to(self, other: "PTZPosition") -> float:
        pan_diff = abs(self.pan - other.pan)
        tilt_diff = abs(self.tilt - other.tilt)
        zoom_diff = abs(self.zoom - other.zoom)
        return math.sqrt(pan_diff ** 2 + tilt_diff ** 2 + zoom_diff ** 2)

    def interpolate(self, other: "PTZPosition", t: float) -> "PTZPosition":
        clamped_t = max(0.0, min(1.0, t))
        return PTZPosition(
            pan=self.pan + (other.pan - self.pan) * clamped_t,
            tilt=self.tilt + (other.tilt - self.tilt) * clamped_t,
            zoom=self.zoom + (other.zoom - self.zoom) * clamped_t,
            brightness=self.brightness,
        )

    def to_tuple(self) -> Tuple[float, float, float, int]:
        return (self.pan, self.tilt, self.zoom, self.brightness)


@dataclass
class PTZMovement:
    start_position: PTZPosition
    target_position: PTZPosition
    movement_type: MovementType = MovementType.EASE_IN_OUT
    duration: float = 1.0
    started_at: float = field(default_factory=time.time)
    completed: bool = False

    def get_position_at(self, current_time: float) -> Optional[PTZPosition]:
        elapsed = current_time - self.started_at

        if elapsed >= self.duration:
            self.completed = True
            return self.target_position

        t = elapsed / self.duration
        t = self._apply_easing(t, self.movement_type)

        return self.start_position.interpolate(self.target_position, t)

    def _apply_easing(self, t: float, movement_type: MovementType) -> float:
        if movement_type == MovementType.LINEAR:
            return t
        elif movement_type == MovementType.EASE_IN:
            return t * t
        elif movement_type == MovementType.EASE_OUT:
            return 1 - (1 - t) * (1 - t)
        elif movement_type == MovementType.EASE_IN_OUT:
            if t < 0.5:
                return 2 * t * t
            else:
                return 1 - math.pow(-2 * t + 2, 2) / 2
        elif movement_type == MovementType.EASE_OUT_IN:
            return 1 - self._apply_easing(1 - t, MovementType.EASE_IN_OUT)
        elif movement_type == MovementType.BOUNCE:
            n1 = 7.5625
            d1 = 2.75
            if t < 1 / d1:
                return n1 * t * t
            elif t < 2 / d1:
                return n1 * (t -= 1.5 / d1) * t + 0.75
            elif t < 2.5 / d1:
                return n1 * (t -= 2.25 / d1) * t + 0.9375
            else:
                return n1 * (t -= 2.625 / d1) * t + 0.984375
        elif movement_type == MovementType.ELASTIC:
            c4 = (2 * math.pi) / 3
            if t == 0:
                return 0
            elif t == 1:
                return 1
            else:
                return -math.pow(2, 10 * t - 10) * math.sin((t * 10 - 10.75) * c4)
        else:
            return t


@dataclass
class TrackingTarget:
    target_id: str
    x: float
    y: float
    width: float
    height: float
    confidence: float
    last_seen: float = field(default_factory=time.time)

    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    def is_stale(self, max_age: float = 1.0) -> bool:
        return time.time() - self.last_seen > max_age


class PTZController:
    def __init__(
        self,
        min_pan: float = 0.0,
        max_pan: float = 180.0,
        min_tilt: float = 0.0,
        max_tilt: float = 180.0,
        min_zoom: float = 1.0,
        max_zoom: float = 10.0,
    ):
        self.min_pan = min_pan
        self.max_pan = max_pan
        self.min_tilt = min_tilt
        self.max_tilt = max_tilt
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom

        self.current_position = PTZPosition(pan=90.0, tilt=90.0, zoom=1.0, brightness=255)
        self.target_position = PTZPosition(pan=90.0, tilt=90.0, zoom=1.0, brightness=255)

        self.mode = PTZMode.MANUAL
        self.movements: List[PTZMovement] = []
        self.active_movement: Optional[PTZMovement] = None

        self.tracking_targets: Dict[str, TrackingTarget] = {}
        self.active_target_id: Optional[str] = None

        self._callback: Optional[Callable[[PTZPosition], None]] = None
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._idle_task: Optional[asyncio.Task] = None

        self._idle_positions = [
            PTZPosition(pan=90, tilt=90),
            PTZPosition(pan=70, tilt=85),
            PTZPosition(pan=110, tilt=95),
            PTZPosition(pan=90, tilt=80),
            PTZPosition(pan=90, tilt=100),
        ]
        self._idle_index = 0

        self.gaze_velocity = 0.5
        self.tracking_sensitivity = 0.3
        self.smoothing_factor = 0.2

    def set_callback(self, callback: Callable[[PTZPosition], None]) -> None:
        self._callback = callback

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._update_loop())
        logger.info("PTZ controller started")

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

        logger.info("PTZ controller stopped")

    async def _update_loop(self) -> None:
        while self._running:
            await self._update()
            await asyncio.sleep(0.016)

    async def _update(self) -> None:
        if self.mode == PTZMode.MANUAL:
            await self._execute_manual_movement()
        elif self.mode == PTZMode.AUTO_TRACK:
            await self._execute_tracking()
        elif self.mode == PTZMode.GAZE_FOLLOW:
            await self._execute_gaze_follow()
        elif self.mode == PTZMode.RANDOM_IDLE:
            await self._execute_idle_behavior()
        elif self.mode == PTZMode.SCENE_SCAN:
            await self._execute_scene_scan()

    async def _execute_manual_movement(self) -> None:
        if self.active_movement:
            position = self.active_movement.get_position_at(time.time())

            if self.active_movement.completed:
                self.active_movement = None

                if self.movements:
                    self.active_movement = self.movements.pop(0)
                    self.active_movement.started_at = time.time()

            if position:
                await self._move_to_position(position)

    async def _execute_tracking(self) -> None:
        if not self.active_target_id:
            return

        target = self.tracking_targets.get(self.active_target_id)
        if not target or target.is_stale():
            self.active_target_id = None
            return

        center_x, center_y = target.center()
        image_width = 640
        image_height = 480

        pan_offset = (center_x - image_width / 2) / (image_width / 2)
        tilt_offset = (center_y - image_height / 2) / (image_height / 2)

        if abs(pan_offset) > self.tracking_sensitivity:
            pan_adjustment = pan_offset * self.gaze_velocity * 5
            new_pan = max(self.min_pan, min(self.max_pan, self.current_position.pan + pan_adjustment))
            self.current_position.pan = new_pan

        if abs(tilt_offset) > self.tracking_sensitivity:
            tilt_adjustment = tilt_offset * self.gaze_velocity * 5
            new_tilt = max(self.min_tilt, min(self.max_tilt, self.current_position.tilt + tilt_adjustment))
            self.current_position.tilt = new_tilt

        await self._apply_current_position()

    async def _execute_gaze_follow(self) -> None:
        await self._execute_tracking()

    async def _execute_idle_behavior(self) -> None:
        if self._idle_task is None or self._idle_task.done():
            self._idle_task = asyncio.create_task(self _idle_animation())

    async def _idle_animation(self) -> None:
        while self._running and self.mode == PTZMode.RANDOM_IDLE:
            target = self._idle_positions[self._idle_index]
            self._idle_index = (self._idle_index + 1) % len(self._idle_positions)

            await self.move_to(
                pan=target.pan,
                tilt=target.tilt,
                zoom=target.zoom,
                movement_type=MovementType.EASE_IN_OUT,
                duration=2.0,
            )

            await asyncio.sleep(3.0)

    async def _execute_scene_scan(self) -> None:
        scan_positions = [
            PTZPosition(pan=60, tilt=80),
            PTZPosition(pan=90, tilt=70),
            PTZPosition(pan=120, tilt=80),
            PTZPosition(pan=120, tilt=100),
            PTZPosition(pan=90, tilt=110),
            PTZPosition(pan=60, tilt=100),
        ]

        for position in scan_positions:
            if not self._running or self.mode != PTZMode.SCENE_SCAN:
                break

            await self.move_to(
                pan=position.pan,
                tilt=position.tilt,
                zoom=position.zoom,
                movement_type=MovementType.LINEAR,
                duration=3.0,
            )
            await asyncio.sleep(1.0)

    async def _move_to_position(self, position: PTZPosition) -> None:
        clamped_position = PTZPosition(
            pan=max(self.min_pan, min(self.max_pan, position.pan)),
            tilt=max(self.min_tilt, min(self.max_tilt, position.tilt)),
            zoom=max(self.min_zoom, min(self.max_zoom, position.zoom)),
            brightness=max(0, min(255, position.brightness)),
        )

        self.current_position = clamped_position

        if self._callback:
            self._callback(clamped_position)

    async def _apply_current_position(self) -> None:
        if self._callback:
            self._callback(self.current_position)

    def set_mode(self, mode: PTZMode) -> None:
        self.mode = mode
        logger.info(f"PTZ mode set to: {mode.value}")

    def move_to(
        self,
        pan: float,
        tilt: float,
        zoom: float = 1.0,
        brightness: int = 255,
        movement_type: MovementType = MovementType.EASE_IN_OUT,
        duration: float = 1.0,
    ) -> asyncio.Task:
        target_position = PTZPosition(pan, tilt, zoom, brightness)

        movement = PTZMovement(
            start_position=self.current_position,
            target_position=target_position,
            movement_type=movement_type,
            duration=duration,
        )

        if self.mode == PTZMode.MANUAL:
            self.movements.append(movement)
            if not self.active_movement:
                self.active_movement = movement
                self.active_movement.started_at = time.time()
        else:
            self.active_movement = movement
            self.active_movement.started_at = time.time()

        return asyncio.create_task(self._wait_for_movement(movement))

    async def _wait_for_movement(self, movement: PTZMovement) -> None:
        while not movement.completed and self._running:
            await asyncio.sleep(0.05)

    def move_relative(
        self,
        pan_delta: float,
        tilt_delta: float,
        zoom_delta: float = 0.0,
        movement_type: MovementType = MovementType.EASE_IN_OUT,
        duration: float = 1.0,
    ) -> asyncio.Task:
        return self.move_to(
            pan=self.current_position.pan + pan_delta,
            tilt=self.current_position.tilt + tilt_delta,
            zoom=self.current_position.zoom + zoom_delta,
            movement_type=movement_type,
            duration=duration,
        )

    def set_pan_tilt(self, pan: float, tilt: float) -> None:
        self.current_position.pan = max(self.min_pan, min(self.max_pan, pan))
        self.current_position.tilt = max(self.min_tilt, min(self.max_tilt, tilt))

    def set_zoom(self, zoom: float) -> None:
        self.current_position.zoom = max(self.min_zoom, min(self.max_zoom, zoom))

    def set_brightness(self, brightness: int) -> None:
        self.current_position.brightness = max(0, min(255, brightness))

    def add_tracking_target(self, target: TrackingTarget) -> None:
        self.tracking_targets[target.target_id] = target

        if self.active_target_id is None:
            self.active_target_id = target.target_id

    def update_tracking_target(self, target: TrackingTarget) -> None:
        if target.target_id in self.tracking_targets:
            self.tracking_targets[target.target_id] = target

    def remove_tracking_target(self, target_id: str) -> None:
        if target_id in self.tracking_targets:
            del self.tracking_targets[target_id]

        if self.active_target_id == target_id:
            self.active_target_id = next(
                (tid for tid in self.tracking_targets.keys()),
                None,
            )

    def set_active_target(self, target_id: str) -> bool:
        if target_id in self.tracking_targets:
            self.active_target_id = target_id
            return True
        return False

    def get_current_position(self) -> PTZPosition:
        return self.current_position

    def get_tracking_targets(self) -> List[TrackingTarget]:
        return list(self.tracking_targets.values())

    def clear_stale_targets(self, max_age: float = 1.0) -> int:
        stale_ids = [
            tid for tid, target in self.tracking_targets.items()
            if target.is_stale(max_age)
        ]

        for tid in stale_ids:
            self.remove_tracking_target(tid)

        return len(stale_ids)

    def reset(self) -> None:
        self.current_position = PTZPosition(pan=90.0, tilt=90.0, zoom=1.0, brightness=255)
        self.target_position = PTZPosition(pan=90.0, tilt=90.0, zoom=1.0, brightness=255)
        self.movements.clear()
        self.active_movement = None
        self.tracking_targets.clear()
        self.active_target_id = None
        self.mode = PTZMode.MANUAL
        logger.info("PTZ controller reset")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "current_position": {
                "pan": self.current_position.pan,
                "tilt": self.current_position.tilt,
                "zoom": self.current_position.zoom,
                "brightness": self.current_position.brightness,
            },
            "active_target_id": self.active_target_id,
            "tracking_targets": len(self.tracking_targets),
            "is_moving": self.active_movement is not None,
        }
