import asyncio
import json
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np
import sounddevice as sd
import soundfile as sf

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class ButlerState(Enum):
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


@dataclass
class DetectionEvent:
    event_type: str
    confidence: float
    bbox: List[float]
    timestamp: float
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationTurn:
    role: str
    content: str
    timestamp: float


class SmartButler:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.state = ButlerState.IDLE
        
        self.wake_word_detector = None
        self.asr_engine = None
        self.tts_engine = None
        self.llm_client = None
        self.vision_detector = None
        
        self.audio_queue = queue.Queue()
        self.detection_queue = queue.Queue()
        self.command_queue = queue.Queue()
        
        self.conversation_history: List[ConversationTurn] = []
        self.detection_history: List[DetectionEvent] = []
        
        self.camera = None
        self.is_running = False
        self.silence_timeout = 3.0
        self.last_activity_time = 0
        
        self._init_components()
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return self._default_config()
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "wake_word": {
                "enabled": True,
                "word": "小管家",
                "threshold": 0.5
            },
            "asr": {
                "provider": "faster-whisper",
                "model": "small",
                "language": "zh"
            },
            "tts": {
                "enabled": True,
                "speaker_id": 0,
                "sample_rate": 22050
            },
            "llm": {
                "api_key": "",
                "base_url": "https://open.bigmodel.cn/api/paas/v4",
                "model": "glm-4",
                "temperature": 0.7,
                "max_tokens": 1024
            },
            "vision": {
                "enabled": True,
                "camera_index": 0,
                "detect_interval": 0.5,
                "action_detection": True
            },
            "proactive": {
                "enabled": True,
                "min_confidence": 0.7,
                "cooldown_sec": 60
            }
        }
    
    def _init_components(self):
        logger.info("Initializing Smart Butler components...")
        
        try:
            self._init_wake_word_detector()
            self._init_asr_engine()
            self._init_tts_engine()
            self._init_llm_client()
            self._init_vision_detector()
            
            logger.info("All components initialized successfully")
        except Exception as e:
            logger.error(f"Component initialization failed: {e}")
    
    def _init_wake_word_detector(self):
        try:
            from DaShan.host.modules.voice.wake_word import WakeWordDetector, WakeWordConfig
            
            config = WakeWordConfig(
                model_path="models/wakeword",
                threshold=self.config["wake_word"]["threshold"]
            )
            
            self.wake_word_detector = WakeWordDetector(config)
            self.wake_word_detector.set_callback(self._on_wake_word_detected)
            logger.info("Wake word detector initialized")
        except Exception as e:
            logger.warning(f"Failed to init wake word detector: {e}")
    
    def _init_asr_engine(self):
        try:
            from butler.tools.voice import VoiceClient
            
            asr_config = self.config["asr"]
            self.asr_engine = VoiceClient(
                api_url="",
                api_key="",
                model="base",
                timeout_sec=30,
                provider=asr_config["provider"],
                local_model=asr_config["model"],
                local_language=asr_config["language"]
            )
            logger.info("ASR engine initialized")
        except Exception as e:
            logger.warning(f"Failed to init ASR engine: {e}")
    
    def _init_tts_engine(self):
        try:
            from DaShan.host.modules.voice.tts import TextToSpeech, TTSConfig
            
            tts_config = self.config["tts"]
            config = TTSConfig(
                model_path="models/tts/zh_CN-xiaoyan-low",
                sample_rate=tts_config["sample_rate"],
                speaker_id=tts_config["speaker_id"]
            )
            
            self.tts_engine = TextToSpeech(config)
            logger.info("TTS engine initialized")
        except Exception as e:
            logger.warning(f"Failed to init TTS engine: {e}")
    
    def _init_llm_client(self):
        try:
            from butler.brain.glm_client import GLMClient, GLMConfig
            
            llm_config = self.config["llm"]
            if llm_config["api_key"]:
                config = GLMConfig(
                    api_key=llm_config["api_key"],
                    base_url=llm_config["base_url"],
                    model_text=llm_config["model"],
                    model_vision=None,
                    timeout_sec=60,
                    temperature=llm_config["temperature"],
                    max_tokens=llm_config["max_tokens"],
                    top_p=0.8
                )
                self.llm_client = GLMClient(config)
                logger.info("LLM client initialized")
            else:
                logger.warning("LLM API key not configured")
        except Exception as e:
            logger.warning(f"Failed to init LLM client: {e}")
    
    def _init_vision_detector(self):
        try:
            from butler.tools.vision import VisionClient, VisionConfig
            
            vision_config = self.config["vision"]
            config = VisionConfig(
                device="cpu",
                face_model_path="",
                object_model_path="yolov8n.pt",
                face_backend="auto",
                face_match_threshold=0.35,
                face_min_confidence=0.5,
                object_min_confidence=0.25,
                max_faces=5
            )
            
            self.vision_detector = VisionClient(config, db=None)
            logger.info("Vision detector initialized")
        except Exception as e:
            logger.warning(f"Failed to init vision detector: {e}")
    
    def _on_wake_word_detected(self):
        logger.info("Wake word detected!")
        self.state = ButlerState.LISTENING
        self.last_activity_time = time.time()
        
        if self.tts_engine:
            self._speak("我在听，请说")
    
    def _speak(self, text: str):
        try:
            logger.info(f"Speaking: {text}")
            
            audio_data = self.tts_engine.synthesize(text)
            if audio_data:
                self.state = ButlerState.SPEAKING
                sd.play(audio_data, self.tts_engine.config.sample_rate)
                sd.wait()
                self.state = ButlerState.IDLE
                
        except Exception as e:
            logger.error(f"Failed to speak: {e}")
    
    def _listen(self) -> Optional[str]:
        try:
            logger.info("Listening...")
            
            sample_rate = 16000
            duration = self.silence_timeout
            channels = 1
            
            recording = sd.rec(
                int(sample_rate * duration),
                samplerate=sample_rate,
                channels=channels,
                dtype='int16'
            )
            
            timeout_start = time.time()
            while sd.get_stream().active:
                if time.time() - timeout_start > duration + 1:
                    sd.stop()
                    break
                time.sleep(0.1)
            
            audio_bytes = recording.tobytes()
            
            if self.asr_engine:
                result = self.asr_engine.transcribe(audio_bytes, language="zh")
                text = result.get("text", "").strip()
                
                if text:
                    logger.info(f"Recognized: {text}")
                    return text
            
        except Exception as e:
            logger.error(f"Failed to listen: {e}")
        
        return None
    
    def _get_llm_response(self, user_input: str) -> str:
        try:
            self.conversation_history.append(
                ConversationTurn(role="user", content=user_input, timestamp=time.time())
            )
            
            messages = [
                {"role": "system", "content": self._get_system_prompt()}
            ]
            
            for turn in self.conversation_history[-10:]:
                messages.append({"role": turn.role, "content": turn.content})
            
            if self.llm_client:
                response, _ = self.llm_client.chat(messages)
                
                self.conversation_history.append(
                    ConversationTurn(role="assistant", content=response, timestamp=time.time())
                )
                
                if len(self.conversation_history) > 20:
                    self.conversation_history = self.conversation_history[-20:]
                
                return response
            
        except Exception as e:
            logger.error(f"Failed to get LLM response: {e}")
        
        return "抱歉，我没能理解您的话。"
    
    def _get_system_prompt(self) -> str:
        return """你是一个智能管家助手，名叫"小管家"。你的职责是：

1. 友好自然地与用户对话，像真人一样交流
2. 记住之前的对话内容，支持连续对话
3. 根据用户的指令提供帮助
4. 主动关心用户的生活状态
5. 语言简洁明了，语气亲切自然

当前状态：
- 你在家环境中工作
- 可以通过摄像头看到用户的动作
- 可以通过扬声器与用户交流
- 支持控制家居设备（如果需要）

请用中文回复，语气要自然、亲切，像朋友一样交流。"""
    
    def _process_command(self, text: str) -> str:
        logger.info(f"Processing command: {text}")
        
        response = self._get_llm_response(text)
        
        return response
    
    def _capture_frame(self) -> Optional[np.ndarray]:
        if self.camera is None:
            try:
                camera_index = self.config["vision"]["camera_index"]
                self.camera = cv2.VideoCapture(camera_index)
                
                if not self.camera.isOpened():
                    logger.error("Failed to open camera")
                    return None
                
            except Exception as e:
                logger.error(f"Failed to init camera: {e}")
                return None
        
        try:
            ret, frame = self.camera.read()
            if ret:
                return frame
        except Exception as e:
            logger.error(f"Failed to capture frame: {e}")
        
        return None
    
    def _detect_actions(self, frame: np.ndarray) -> List[DetectionEvent]:
        events = []
        
        try:
            from PIL import Image
            
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            
            result = self.vision_detector.detect(
                img,
                model="object",
                min_conf=0.5,
                max_det=10
            )
            
            if "detections" in result:
                for det in result["detections"]:
                    label = det.get("label", "")
                    confidence = det.get("confidence", 0)
                    bbox = det.get("bbox", [])
                    
                    if confidence > self.config["vision"]["detect_interval"]:
                        event = DetectionEvent(
                            event_type="object_detection",
                            confidence=confidence,
                            bbox=bbox,
                            timestamp=time.time(),
                            data={"label": label}
                        )
                        events.append(event)
            
        except Exception as e:
            logger.error(f"Action detection failed: {e}")
        
        return events
    
    def _generate_proactive_response(self, events: List[DetectionEvent]) -> Optional[str]:
        if not events or not self.config["proactive"]["enabled"]:
            return None
        
        now = time.time()
        recent_events = [
            e for e in self.detection_history
            if now - e.timestamp < self.config["proactive"]["cooldown_sec"]
        ]
        
        if recent_events:
            return None
        
        event = events[0]
        label = event.data.get("label", "")
        
        responses = {
            "人": "我看到有人进来了，需要我帮您做点什么吗？",
            "手机": "您在玩手机吗？要注意保护眼睛哦",
            "bottle": "需要我帮您准备一些水吗？",
            "cup": "看起来您需要休息一下",
            "laptop": "您在工作吗？需要我帮您调节灯光吗？",
            "book": "您在看书，保持专注！",
            "tv": "您要开始看电视了吗？需要我帮您调暗灯光吗？",
            "chair": "您坐下来休息一下吧",
            "sofa": "看起来您想放松一下",
            "bed": "您是想休息了吗？需要我帮您准备睡眠环境吗？"
        }
        
        return responses.get(label)
    
    def _vision_loop(self):
        detect_interval = self.config["vision"]["detect_interval"]
        last_detection_time = 0
        
        while self.is_running:
            try:
                now = time.time()
                if now - last_detection_time < detect_interval:
                    time.sleep(0.1)
                    continue
                
                frame = self._capture_frame()
                if frame is not None:
                    events = self._detect_actions(frame)
                    
                    if events:
                        for event in events:
                            self.detection_history.append(event)
                            if len(self.detection_history) > 100:
                                self.detection_history = self.detection_history[-100:]
                        
                        response = self._generate_proactive_response(events)
                        if response and self.state == ButlerState.IDLE:
                            logger.info(f"Proactive response: {response}")
                            self._speak(response)
                    
                    last_detection_time = now
                
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Vision loop error: {e}")
                time.sleep(1)
    
    def _conversation_loop(self):
        while self.is_running:
            try:
                if self.state == ButlerState.LISTENING:
                    self.state = ButlerState.PROCESSING
                    
                    user_input = self._listen()
                    
                    if user_input:
                        response = self._process_command(user_input)
                        
                        if response:
                            self._speak(response)
                    
                    self.state = ButlerState.IDLE
                
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Conversation loop error: {e}")
                self.state = ButlerState.IDLE
    
    def start(self):
        if self.is_running:
            logger.warning("Butler is already running")
            return
        
        logger.info("Starting Smart Butler...")
        self.is_running = True
        
        try:
            if self.wake_word_detector:
                self.wake_word_detector.start()
                logger.info("Wake word detector started")
            
            if self.config["vision"]["enabled"]:
                vision_thread = threading.Thread(target=self._vision_loop, daemon=True)
                vision_thread.start()
                logger.info("Vision loop started")
            
            conversation_thread = threading.Thread(target=self._conversation_loop, daemon=True)
            conversation_thread.start()
            logger.info("Conversation loop started")
            
            logger.info("Smart Butler is now running!")
            
        except Exception as e:
            logger.error(f"Failed to start butler: {e}")
            self.is_running = False
    
    def stop(self):
        logger.info("Stopping Smart Butler...")
        self.is_running = False
        
        if self.wake_word_detector:
            self.wake_word_detector.stop()
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        if self.llm_client:
            self.llm_client.close()
        
        logger.info("Smart Butler stopped")
    
    def run_forever(self):
        self.start()
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()


if __name__ == "__main__":
    butler = SmartButler("config.json")
    butler.run_forever()
