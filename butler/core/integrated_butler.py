import asyncio
import json
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import sounddevice as sd

from butler.conversation.smart_dialogue import (
    SmartDialogueEngine,
    DialogueContext,
    EmotionType
)
from butler.vision import (
    SmartVisionMonitor,
    ProactiveEngine,
    VisionEvent,
    ActivityType
)

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
    VISION_ACTIVE = "vision_active"


@dataclass
class ButlerConfig:
    name: str = "小管家"
    wake_word: str = "小管家"
    wake_threshold: float = 0.5
    asr_provider: str = "faster-whisper"
    asr_model: str = "small"
    asr_language: str = "zh"
    tts_enabled: bool = True
    tts_speaker_id: int = 0
    tts_sample_rate: int = 22050
    llm_api_key: str = ""
    llm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    llm_model: str = "glm-4"
    llm_temperature: float = 0.7
    vision_enabled: bool = True
    camera_index: int = 0
    proactive_enabled: bool = True
    silence_timeout: float = 3.0
    user_name: str = "主人"
    current_room: str = "客厅"


class IntegratedSmartButler:
    def __init__(self, config_path: Optional[str] = None):
        self.config = self._load_config(config_path)
        self.state = ButlerState.IDLE
        
        self.wake_word_detector = None
        self.asr_engine = None
        self.tts_engine = None
        self.llm_client = None
        self.vision_monitor = None
        self.proactive_engine = None
        self.dialogue_engine = None
        
        self.is_running = False
        self.last_interaction_time = 0
        self.conversation_count = 0
        
        self._init_components()
        self._setup_callbacks()
        
        logger.info(f"Integrated Smart Butler '{self.config.name}' initialized")
    
    def _load_config(self, config_path: Optional[str]) -> ButlerConfig:
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return ButlerConfig(**data)
            except Exception as e:
                logger.warning(f"Failed to load config from {config_path}: {e}")
        
        return ButlerConfig()
    
    def _init_components(self):
        logger.info("Initializing components...")
        
        try:
            self._init_wake_word_detector()
            self._init_asr_engine()
            self._init_tts_engine()
            self._init_llm_client()
            self._init_vision_monitor()
            self._init_proactive_engine()
            self._init_dialogue_engine()
            
            logger.info("All components initialized")
        except Exception as e:
            logger.error(f"Component initialization failed: {e}")
    
    def _init_wake_word_detector(self):
        try:
            from DaShan.host.modules.voice.wake_word import WakeWordDetector, WakeWordConfig
            
            config = WakeWordConfig(
                model_path="models/wakeword",
                threshold=self.config.wake_threshold
            )
            
            self.wake_word_detector = WakeWordDetector(config)
            self.wake_word_detector.set_callback(self._on_wake_word_detected)
            logger.info("Wake word detector initialized")
        except Exception as e:
            logger.warning(f"Failed to init wake word detector: {e}")
    
    def _init_asr_engine(self):
        try:
            from butler.tools.voice import VoiceClient
            
            self.asr_engine = VoiceClient(
                api_url="",
                api_key="",
                model="base",
                timeout_sec=30,
                provider=self.config.asr_provider,
                local_model=self.config.asr_model,
                local_language=self.config.asr_language
            )
            logger.info("ASR engine initialized")
        except Exception as e:
            logger.warning(f"Failed to init ASR engine: {e}")
    
    def _init_tts_engine(self):
        if not self.config.tts_enabled:
            return
        
        try:
            from DaShan.host.modules.voice.tts import TextToSpeech, TTSConfig
            
            config = TTSConfig(
                model_path="models/tts/zh_CN-xiaoyan-low",
                sample_rate=self.config.tts_sample_rate,
                speaker_id=self.config.tts_speaker_id
            )
            
            self.tts_engine = TextToSpeech(config)
            logger.info("TTS engine initialized")
        except Exception as e:
            logger.warning(f"Failed to init TTS engine: {e}")
    
    def _init_llm_client(self):
        if not self.config.llm_api_key:
            logger.warning("LLM API key not configured")
            return
        
        try:
            from butler.brain.glm_client import GLMClient, GLMConfig
            
            config = GLMConfig(
                api_key=self.config.llm_api_key,
                base_url=self.config.llm_base_url,
                model_text=self.config.llm_model,
                model_vision=None,
                timeout_sec=60,
                temperature=self.config.llm_temperature,
                max_tokens=1024,
                top_p=0.8
            )
            
            self.llm_client = GLMClient(config)
            logger.info("LLM client initialized")
        except Exception as e:
            logger.warning(f"Failed to init LLM client: {e}")
    
    def _init_vision_monitor(self):
        if not self.config.vision_enabled:
            return
        
        try:
            self.vision_monitor = SmartVisionMonitor({
                "camera_index": self.config.camera_index,
                "detect_interval": 0.5,
                "min_person_confidence": 0.5,
                "min_object_confidence": 0.3,
                "activity_detection": True,
                "track_people": True,
                "proactive_mode": True,
                "cooldown_seconds": 30
            })
            logger.info("Vision monitor initialized")
        except Exception as e:
            logger.warning(f"Failed to init vision monitor: {e}")
    
    def _init_proactive_engine(self):
        if not self.config.proactive_enabled:
            return
        
        try:
            self.proactive_engine = ProactiveEngine()
            logger.info("Proactive engine initialized")
        except Exception as e:
            logger.warning(f"Failed to init proactive engine: {e}")
    
    def _init_dialogue_engine(self):
        try:
            self.dialogue_engine = SmartDialogueEngine(self.llm_client)
            self.dialogue_engine.context.user_name = self.config.user_name
            self.dialogue_engine.context.current_room = self.config.current_room
            logger.info("Dialogue engine initialized")
        except Exception as e:
            logger.warning(f"Failed to init dialogue engine: {e}")
    
    def _setup_callbacks(self):
        if self.vision_monitor and self.proactive_engine:
            self.vision_monitor.register_callback(
                "activity_detected",
                self._on_activity_detected
            )
            
            self.proactive_engine.register_interaction_callback(
                self._on_proactive_interaction
            )
            
            logger.info("Callbacks set up")
    
    def _on_wake_word_detected(self):
        logger.info("Wake word detected!")
        self.state = ButlerState.LISTENING
        self.last_interaction_time = time.time()
        
        if self.tts_engine:
            self._speak("我在听")
    
    def _on_activity_detected(self, event: VisionEvent):
        logger.debug(f"Activity detected: {event.activity}")
        
        if self.proactive_engine and self.config.proactive_enabled:
            self.proactive_engine.process_event(event)
    
    def _on_proactive_interaction(self, message: str):
        if self.state == ButlerState.IDLE:
            logger.info(f"Proactive interaction: {message}")
            
            if self.tts_engine:
                self._speak(message)
    
    def _speak(self, text: str):
        try:
            logger.info(f"Speaking: {text}")
            
            if self.tts_engine:
                self.state = ButlerState.SPEAKING
                
                audio_data = self.tts_engine.synthesize(text)
                if audio_data:
                    sd.play(audio_data, self.tts_engine.config.sample_rate)
                    sd.wait()
                
                self.state = ButlerState.IDLE
        except Exception as e:
            logger.error(f"Failed to speak: {e}")
            self.state = ButlerState.IDLE
    
    def _listen(self) -> Optional[str]:
        try:
            logger.info("Listening...")
            
            sample_rate = 16000
            duration = self.config.silence_timeout
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
    
    def _process_conversation(self, user_input: str) -> str:
        try:
            if self.dialogue_engine:
                result = self.dialogue_engine.process(user_input)
                return result["response"]
            
            if self.llm_client:
                messages = [
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": user_input}
                ]
                response, _ = self.llm_client.chat(messages)
                return response
            
            return self._get_fallback_response(user_input)
        except Exception as e:
            logger.error(f"Failed to process conversation: {e}")
            return self._get_fallback_response(user_input)
    
    def _get_system_prompt(self) -> str:
        return f"""你是"{self.config.name}"，一个温暖、贴心、像真人一样的智能管家助手。

你的特点：
1. 语气自然亲切，像家人朋友一样交流
2. 主动关心用户的生活状态和需求
3. 记住之前的对话，支持连续对话
4. 能够感知用户的情绪并做出适当的回应
5. 语言简洁明了，不啰嗦，但也不冷漠

当前情况：
- 用户是{self.config.user_name}
- 用户在{self.config.current_room}
- 你可以通过摄像头看到用户的动作
- 你可以主动与用户交流

对话原则：
- 回复要简短自然，像真人说话
- 不要用机械的回复
- 适当使用语气词，让对话更生动
- 主动关心用户
- 记住上下文，支持连续对话
- 如果不确定用户意图，可以适当询问

记住：你是一个有温度的管家，不是冷冰冰的机器！"""
    
    def _get_fallback_response(self, user_input: str) -> str:
        input_lower = user_input.lower()
        
        greetings = ["你好", "您好", "hi", "hello", "hey", "小管家"]
        if any(g in input_lower for g in greetings):
            return f"你好，{self.config.user_name}！有什么我可以帮你的吗？"
        
        thanks = ["谢谢", "感谢", "thank", "thanks"]
        if any(t in input_lower for t in thanks):
            return "不客气！这是我应该做的"
        
        if "再见" in input_lower or "拜拜" in input_lower:
            return "好的，有需要随时叫我"
        
        return "嗯...你说得对！还有什么需要我帮忙的吗？"
    
    def _vision_loop(self):
        if not self.vision_monitor:
            return
        
        if not self.vision_monitor.start():
            logger.error("Failed to start vision monitor")
            return
        
        logger.info("Vision loop started")
        
        try:
            while self.is_running:
                try:
                    self.vision_monitor.process_frame()
                    time.sleep(0.1)
                except Exception as e:
                    logger.error(f"Vision loop error: {e}")
                    time.sleep(1)
        finally:
            self.vision_monitor.stop()
    
    def _conversation_loop(self):
        logger.info("Conversation loop started")
        
        try:
            while self.is_running:
                try:
                    if self.state == ButlerState.LISTENING:
                        self.state = ButlerState.PROCESSING
                        
                        user_input = self._listen()
                        
                        if user_input:
                            response = self._process_conversation(user_input)
                            
                            if response:
                                self._speak(response)
                            
                            self.conversation_count += 1
                        
                        self.state = ButlerState.IDLE
                    
                    time.sleep(0.1)
                except Exception as e:
                    logger.error(f"Conversation loop error: {e}")
                    self.state = ButlerState.IDLE
        except Exception as e:
            logger.error(f"Conversation loop failed: {e}")
    
    def start(self):
        if self.is_running:
            logger.warning("Butler is already running")
            return
        
        logger.info("Starting Integrated Smart Butler...")
        self.is_running = True
        
        try:
            if self.wake_word_detector:
                self.wake_word_detector.start()
                logger.info("Wake word detector started")
            
            if self.vision_monitor:
                vision_thread = threading.Thread(
                    target=self._vision_loop,
                    daemon=True
                )
                vision_thread.start()
            
            conversation_thread = threading.Thread(
                target=self._conversation_loop,
                daemon=True
            )
            conversation_thread.start()
            
            logger.info(f"{self.config.name} is now running!")
            
        except Exception as e:
            logger.error(f"Failed to start butler: {e}")
            self.is_running = False
    
    def stop(self):
        logger.info("Stopping Integrated Smart Butler...")
        self.is_running = False
        
        if self.wake_word_detector:
            self.wake_word_detector.stop()
        
        if self.vision_monitor:
            self.vision_monitor.stop()
        
        if self.llm_client:
            self.llm_client.close()
        
        logger.info("Integrated Smart Butler stopped")
    
    def run_forever(self):
        self.start()
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()
    
    def get_status(self) -> Dict[str, Any]:
        return {
            "name": self.config.name,
            "state": self.state.value,
            "is_running": self.is_running,
            "conversation_count": self.conversation_count,
            "last_interaction": time.time() - self.last_interaction_time,
            "components": {
                "wake_word_detector": self.wake_word_detector is not None,
                "asr_engine": self.asr_engine is not None,
                "tts_engine": self.tts_engine is not None,
                "llm_client": self.llm_client is not None,
                "vision_monitor": self.vision_monitor is not None,
                "proactive_engine": self.proactive_engine is not None,
                "dialogue_engine": self.dialogue_engine is not None
            }
        }


if __name__ == "__main__":
    butler = IntegratedSmartButler("butler/smart_butler_config.json")
    
    print(f"\n{'='*50}")
    print(f"  {butler.config.name} - 智能管家系统")
    print(f"{'='*50}")
    print(f"\n使用说明：")
    print(f"1. 说 '{butler.config.wake_word}' 唤醒我")
    print(f"2. 然后说出你的指令或问题")
    print(f"3. 我会主动关注你的行为并给予建议")
    print(f"\n按 Ctrl+C 退出\n")
    
    butler.run_forever()
