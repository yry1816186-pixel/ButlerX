from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class PowerMode(Enum):
    POWER_SAVING = "power_saving"
    BALANCED = "balanced"
    PERFORMANCE = "performance"
    ULTRA_LOW_POWER = "ultra_low_power"


class QualityMode(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    ADAPTIVE = "adaptive"


class FrameRate(Enum):
    FPS_1 = 1
    FPS_5 = 5
    FPS_10 = 10
    FPS_15 = 15
    FPS_24 = 24
    FPS_30 = 30


@dataclass
class CameraConfig:
    camera_id: int = 0
    width: int = 640
    height: int = 480
    fps: FrameRate = FrameRate.FPS_15
    power_mode: PowerMode = PowerMode.BALANCED
    quality_mode: QualityMode = QualityMode.MEDIUM
    enable_adaptive: bool = True
    enable_motion_detection: bool = True
    motion_threshold: float = 0.05
    idle_timeout: float = 30.0
    buffer_size: int = 5


@dataclass
class FrameStats:
    timestamp: float
    frame_count: int
    frame_size_bytes: int
    encoding_time_ms: float
    bandwidth_bytes_per_second: float
    cpu_usage_percent: float
    power_consumption_mw: float
    motion_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "frame_count": self.frame_count,
            "frame_size_bytes": self.frame_size_bytes,
            "encoding_time_ms": self.encoding_time_ms,
            "bandwidth_bytes_per_second": self.bandwidth_bytes_per_second,
            "cpu_usage_percent": self.cpu_usage_percent,
            "power_consumption_mw": self.power_consumption_mw,
            "motion_score": self.motion_score,
        }


class MotionDetector:
    def __init__(self, threshold: float = 0.05, history_size: int = 5):
        self.threshold = threshold
        self.history_size = history_size
        self._frame_history: List[np.ndarray] = []
        self._last_motion_score = 0.0

    def add_frame(self, frame: np.ndarray) -> float:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (160, 120))

        self._frame_history.append(gray)
        if len(self._frame_history) > self.history_size:
            self._frame_history.pop(0)

        if len(self._frame_history) < 2:
            return 0.0

        motion_score = self._calculate_motion()
        self._last_motion_score = motion_score
        return motion_score

    def _calculate_motion(self) -> float:
        if len(self._frame_history) < 2:
            return 0.0

        diff = cv2.absdiff(self._frame_history[-2], self._frame_history[-1])
        motion_pixels = np.sum(diff > 30)
        total_pixels = diff.shape[0] * diff.shape[1]
        motion_ratio = motion_pixels / total_pixels

        return motion_ratio

    def is_motion_detected(self) -> bool:
        return self._last_motion_score > self.threshold

    def get_last_motion_score(self) -> float:
        return self._last_motion_score


class FrameBuffer:
    def __init__(self, max_size: int = 10):
        self.max_size = max_size
        self._buffer: List[Tuple[np.ndarray, float]] = []

    def add_frame(self, frame: np.ndarray, timestamp: float = None) -> None:
        if timestamp is None:
            timestamp = time.time()

        self._buffer.append((frame.copy(), timestamp))

        if len(self._buffer) > self.max_size:
            self._buffer.pop(0)

    def get_latest(self) -> Optional[Tuple[np.ndarray, float]]:
        return self._buffer[-1] if self._buffer else None

    def get_frame(self, index: int) -> Optional[Tuple[np.ndarray, float]]:
        if 0 <= index < len(self._buffer):
            return self._buffer[index]
        return None

    def clear(self) -> None:
        self._buffer.clear()

    def size(self) -> int:
        return len(self._buffer)


class FrameEncoder(ABC):
    @abstractmethod
    def encode(self, frame: np.ndarray, quality: int = 75) -> Tuple[bytes, float]:
        pass

    @abstractmethod
    def decode(self, data: bytes) -> np.ndarray:
        pass


class JPEGEncoder(FrameEncoder):
    def __init__(self, quality: int = 75):
        self.quality = quality

    def encode(self, frame: np.ndarray, quality: int = 75) -> Tuple[bytes, float]:
        encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), quality or self.quality]
        start_time = time.time()
        _, encoded = cv2.imencode(".jpg", frame, encode_params)
        encoding_time = (time.time() - start_time) * 1000
        return (encoded.tobytes(), encoding_time)

    def decode(self, data: bytes) -> np.ndarray:
        return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)


class H264Encoder(FrameEncoder):
    def __init__(self, width: int = 640, height: int = 480, fps: int = 15):
        self.width = width
        self.height = height
        self.fps = fps
        self._fourcc = cv2.VideoWriter_fourcc(*"H264")

    def encode(self, frame: np.ndarray, quality: int = 75) -> Tuple[bytes, float]:
        resized = cv2.resize(frame, (self.width, self.height))
        start_time = time.time()

        _, encoded = cv2.imencode(".h264", resized)

        encoding_time = (time.time() - start_time) * 1000
        return (encoded.tobytes(), encoding_time)

    def decode(self, data: bytes) -> np.ndarray:
        return cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)


class OptimizedCamera:
    def __init__(self, config: CameraConfig):
        self.config = config
        self._camera: Optional[cv2.VideoCapture] = None
        self._encoder: Optional[FrameEncoder] = None
        self._motion_detector: Optional[MotionDetector] = None
        self._frame_buffer: Optional[FrameBuffer] = None

        self._running = False
        self._capture_task: Optional[asyncio.Task] = None
        self._idle_task: Optional[asyncio.Task] = None

        self._frame_count = 0
        self._last_frame_time = 0.0
        self._last_activity_time = time.time()

        self._stats: List[FrameStats] = []
        self._callback: Optional[Callable[[np.ndarray, float], None]] = None

    async def start(self) -> bool:
        if self._running:
            return True

        self._camera = cv2.VideoCapture(self.config.camera_id)
        if not self._camera.isOpened():
            logger.error(f"Failed to open camera {self.config.camera_id}")
            return False

        self._camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.width)
        self._camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.height)
        self._camera.set(cv2.CAP_PROP_FPS, self.config.fps.value)

        self._encoder = JPEGEncoder(quality=70)
        self._motion_detector = MotionDetector(
            threshold=self.config.motion_threshold,
            history_size=5
        )
        self._frame_buffer = FrameBuffer(max_size=self.config.buffer_size)

        self._running = True
        self._capture_task = asyncio.create_task(self._capture_loop())

        logger.info(f"Optimized camera started: {self.config.camera_id}")
        return True

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False

        if self._capture_task:
            self._capture_task.cancel()
            try:
                await self._capture_task
            except asyncio.CancelledError:
                pass

        if self._idle_task:
            self._idle_task.cancel()
            try:
                await self._idle_task
            except asyncio.CancelledError:
                pass

        if self._camera:
            self._camera.release()

        logger.info(f"Optimized camera stopped: {self.config.camera_id}")

    async def _capture_loop(self) -> None:
        target_fps = self.config.fps.value
        frame_interval = 1.0 / target_fps

        while self._running:
            start_time = time.time()

            success, frame = self._camera.read()
            if not success:
                logger.warning("Failed to read frame")
                await asyncio.sleep(0.1)
                continue

            motion_score = 0.0
            if self.config.enable_motion_detection:
                motion_score = self._motion_detector.add_frame(frame)

            has_motion = self._motion_detector.is_motion_detected() if self.config.enable_motion_detection else True

            if has_motion or self._should_send_frame():
                self._frame_buffer.add_frame(frame)

                if self._callback:
                    self._callback(frame, motion_score)

                self._last_activity_time = time.time()
                self._frame_count += 1

            elapsed = time.time() - start_time
            sleep_time = max(0, frame_interval - elapsed)
            await asyncio.sleep(sleep_time)

            self._monitor_power_mode()

    async def _idle_loop(self) -> None:
        while self._running:
            await asyncio.sleep(1.0)

            if self._should_enter_idle_mode():
                await self._enter_idle_mode()

    def _should_send_frame(self) -> bool:
        if self.config.power_mode == PowerMode.ULTRA_LOW_POWER:
            return self._motion_detector.is_motion_detected()
        elif self.config.power_mode == PowerMode.POWER_SAVING:
            idle_time = time.time() - self._last_activity_time
            return idle_time < self.config.idle_timeout
        else:
            return True

    def _should_enter_idle_mode(self) -> bool:
        idle_time = time.time() - self._last_activity_time
        return idle_time > self.config.idle_timeout

    async def _enter_idle_mode(self) -> None:
        if self.config.power_mode == PowerMode.BALANCED:
            self.config.power_mode = PowerMode.POWER_SAVING
            logger.info("Entered idle mode: POWER_SAVING")
        elif self.config.power_mode == PowerMode.PERFORMANCE:
            self.config.power_mode = PowerMode.BALANCED
            logger.info("Entered idle mode: BALANCED")

    def _monitor_power_mode(self) -> None:
        if self.config.enable_adaptive:
            motion_score = self._motion_detector.get_last_motion_score()

            if motion_score > 0.2:
                if self.config.power_mode != PowerMode.PERFORMANCE:
                    logger.info("High motion detected, switching to PERFORMANCE mode")
                    self.config.power_mode = PowerMode.PERFORMANCE
            elif motion_score < 0.02:
                if self.config.power_mode == PowerMode.PERFORMANCE:
                    logger.info("Low motion, switching to BALANCED mode")
                    self.config.power_mode = PowerMode.BALANCED

    def set_callback(self, callback: Callable[[np.ndarray, float], None]) -> None:
        self._callback = callback

    def get_latest_frame(self) -> Optional[np.ndarray]:
        latest = self._frame_buffer.get_latest()
        return latest[0] if latest else None

    def get_frame_encoded(self, quality: int = 75) -> Optional[Tuple[bytes, float]]:
        latest = self._frame_buffer.get_latest()
        if not latest:
            return None

        frame, _ = latest
        return self._encoder.encode(frame, quality)

    def get_frame_rate(self) -> float:
        if self._frame_count == 0:
            return 0.0

        elapsed = time.time() - self._last_frame_time
        return self._frame_count / elapsed if elapsed > 0 else 0.0

    def get_stats(self, limit: int = 100) -> List[FrameStats]:
        return self._stats[-limit:]

    def get_current_power_mode(self) -> PowerMode:
        return self.config.power_mode

    def get_current_fps(self) -> float:
        if self.config.power_mode == PowerMode.ULTRA_LOW_POWER:
            return 1.0
        elif self.config.power_mode == PowerMode.POWER_SAVING:
            return 5.0
        elif self.config.power_mode == PowerMode.BALANCED:
            return 10.0
        elif self.config.power_mode == PowerMode.PERFORMANCE:
            return 15.0
        return self.config.fps.value

    def set_power_mode(self, mode: PowerMode) -> None:
        self.config.power_mode = mode
        logger.info(f"Power mode set to: {mode.value}")

    def set_quality_mode(self, mode: QualityMode) -> None:
        self.config.quality_mode = mode
        logger.info(f"Quality mode set to: {mode.value}")

    def to_dict(self) -> Dict[str, Any]:
        latest_frame = self.get_latest_frame()

        return {
            "camera_id": self.config.camera_id,
            "resolution": f"{self.config.width}x{self.config.height}",
            "fps": self.get_current_fps(),
            "power_mode": self.config.power_mode.value,
            "quality_mode": self.config.quality_mode.value,
            "running": self._running,
            "frame_count": self._frame_count,
            "buffer_size": self._frame_buffer.size(),
            "motion_detected": self._motion_detector.is_motion_detected() if self._motion_detector else False,
            "has_frame": latest_frame is not None,
        }


class MultiCameraManager:
    def __init__(self):
        self._cameras: Dict[int, OptimizedCamera] = {}
        self._active_camera_id: Optional[int] = None

    async def add_camera(self, config: CameraConfig) -> bool:
        if config.camera_id in self._cameras:
            return False

        camera = OptimizedCamera(config)
        success = await camera.start()

        if success:
            self._cameras[config.camera_id] = camera

            if self._active_camera_id is None:
                self._active_camera_id = config.camera_id

            logger.info(f"Added camera: {config.camera_id}")

        return success

    async def remove_camera(self, camera_id: int) -> bool:
        if camera_id not in self._cameras:
            return False

        await self._cameras[camera_id].stop()
        del self._cameras[camera_id]

        if self._active_camera_id == camera_id:
            self._active_camera_id = next(
                (cid for cid in self._cameras.keys()),
                None
            )

        logger.info(f"Removed camera: {camera_id}")
        return True

    def get_camera(self, camera_id: int) -> Optional[OptimizedCamera]:
        return self._cameras.get(camera_id)

    def get_active_camera(self) -> Optional[OptimizedCamera]:
        if self._active_camera_id is not None:
            return self._cameras.get(self._active_camera_id)
        return None

    def set_active_camera(self, camera_id: int) -> bool:
        if camera_id in self._cameras:
            self._active_camera_id = camera_id
            logger.info(f"Active camera set to: {camera_id}")
            return True
        return False

    def get_all_cameras(self) -> List[OptimizedCamera]:
        return list(self._cameras.values())

    async def stop_all(self) -> None:
        for camera in self._cameras.values():
            await camera.stop()

        logger.info("All cameras stopped")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cameras": [camera.to_dict() for camera in self._cameras.values()],
            "camera_count": len(self._cameras),
            "active_camera_id": self._active_camera_id,
        }


if __name__ == "__main__":
    import sys

    async def main():
        config = CameraConfig(
            camera_id=0,
            width=640,
            height=480,
            fps=FrameRate.FPS_15,
            power_mode=PowerMode.BALANCED,
            quality_mode=QualityMode.MEDIUM,
            enable_adaptive=True,
            enable_motion_detection=True,
        )

        camera = OptimizedCamera(config)

        def frame_callback(frame, motion_score):
            print(f"Frame captured, motion score: {motion_score:.4f}")

        camera.set_callback(frame_callback)

        success = await camera.start()
        if not success:
            print("Failed to start camera")
            return

        print("Optimized Camera Test")
        print("Press 'q' to quit")

        try:
            while True:
                frame = camera.get_latest_frame()
                if frame is not None:
                    cv2.imshow("Optimized Camera", frame)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break

                await asyncio.sleep(0.01)

        except KeyboardInterrupt:
            pass

        await camera.stop()
        cv2.destroyAllWindows()

    asyncio.run(main())
