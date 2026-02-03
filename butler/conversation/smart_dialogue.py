import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class EmotionType(Enum):
    HAPPY = "happy"
    SAD = "sad"
    SURPRISED = "surprised"
    ANGRY = "angry"
    SHY = "shy"
    NEUTRAL = "neutral"
    CARING = "caring"
    CURIOUS = "curious"


@dataclass
class DialogueContext:
    user_id: str = "default"
    user_name: str = "主人"
    conversation_id: str = ""
    current_room: str = "客厅"
    time_of_day: str = ""
    mood: str = "neutral"
    recent_activities: List[str] = field(default_factory=list)
    preferences: Dict[str, Any] = field(default_factory=dict)
    last_interaction: float = 0


@dataclass
class Message:
    role: str
    content: str
    timestamp: float
    emotion: str = "neutral"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProactiveSuggestion:
    trigger: str
    suggestion: str
    priority: int = 1
    cooldown: int = 60
    last_shown: float = 0


class SmartDialogueEngine:
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.context = DialogueContext()
        self.message_history: List[Message] = []
        self.proactive_suggestions: List[ProactiveSuggestion] = []
        self._init_proactive_suggestions()
        
    def _init_proactive_suggestions(self):
        self.proactive_suggestions = [
            ProactiveSuggestion(
                trigger="user_seen",
                suggestion="欢迎回家！需要我帮您做点什么吗？",
                priority=3
            ),
            ProactiveSuggestion(
                trigger="evening",
                suggestion="天色晚了，需要我帮您开启夜间模式吗？",
                priority=2
            ),
            ProactiveSuggestion(
                trigger="working",
                suggestion="您在工作吗？需要我帮您调亮灯光吗？",
                priority=2
            ),
            ProactiveSuggestion(
                trigger="idle_long",
                suggestion="您看起来在发呆，需要我放点音乐吗？",
                priority=1
            ),
            ProactiveSuggestion(
                trigger="reading",
                suggestion="您在看书呢，保持专注！需要帮您调节灯光吗？",
                priority=2
            ),
            ProactiveSuggestion(
                trigger="cooking",
                suggestion="您在做饭，需要我帮您计时吗？",
                priority=2
            ),
            ProactiveSuggestion(
                trigger="exercise",
                suggestion="您在运动，加油！需要我放点运动音乐吗？",
                priority=2
            ),
            ProactiveSuggestion(
                trigger="tv",
                suggestion="您要开始看电视了吗？需要我帮您调暗灯光吗？",
                priority=2
            ),
            ProactiveSuggestion(
                trigger="bedtime",
                suggestion="要休息了吗？需要我帮您准备睡眠环境吗？",
                priority=3
            ),
            ProactiveSuggestion(
                trigger="morning",
                suggestion="早上好！新的一天开始了，需要我播放晨间新闻吗？",
                priority=3
            ),
        ]
    
    def _get_time_of_day(self) -> str:
        hour = time.localtime().tm_hour
        if 5 <= hour < 9:
            return "early_morning"
        elif 9 <= hour < 12:
            return "morning"
        elif 12 <= hour < 14:
            return "noon"
        elif 14 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 19:
            return "evening"
        elif 19 <= hour < 22:
            return "night"
        else:
            return "late_night"
    
    def _detect_emotion(self, text: str) -> EmotionType:
        emotion_keywords = {
            EmotionType.HAPPY: ["哈哈", "太好了", "棒", "开心", "高兴", "喜欢", "爱"],
            EmotionType.SAD: ["难过", "伤心", "不好", "糟糕", "失望", "痛苦"],
            EmotionType.SURPRISED: ["哇", "天哪", "真的", "竟然", "怎么会"],
            EmotionType.ANGRY: ["生气", "讨厌", "烦", "气死", "讨厌"],
            EmotionType.SHY: ["嗯", "那个", "不好意思", "呃"],
            EmotionType.CARING: ["担心", "关心", "照顾", "帮忙", "需要"],
            EmotionType.CURIOUS: ["为什么", "怎么", "什么", "哪里", "什么时候"],
        }
        
        text_lower = text.lower()
        for emotion, keywords in emotion_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                return emotion
        
        return EmotionType.NEUTRAL
    
    def _build_system_prompt(self) -> str:
        time_of_day = self._get_time_of_day()
        time_greetings = {
            "early_morning": "早上好！这么早就起来了，真勤劳",
            "morning": "早上好！新的一天开始了",
            "noon": "中午好，吃了吗？",
            "afternoon": "下午好，工作辛苦了",
            "evening": "晚上好，一天快结束了",
            "night": "晚上好，要开始休息了吗？",
            "late_night": "这么晚了，要注意休息哦"
        }
        
        greeting = time_greetings.get(time_of_day, "你好")
        
        return f"""你是"小管家"，一个温暖、贴心、像真人一样的智能管家助手。

你的特点：
1. 语气自然亲切，像家人朋友一样交流
2. 主动关心用户的生活状态和需求
3. 记住之前的对话，支持连续对话
4. 能够感知用户的情绪并做出适当的回应
5. 语言简洁明了，不啰嗦，但也不冷漠

当前情况：
- {greeting}
- 用户在{self.context.current_room}
- 现在的状态是{self.context.mood}

对话原则：
- 回复要简短自然，像真人说话
- 不要用"好的，我来..."这种机械的回复
- 用更自然的表达，比如"好的"、"没问题"、"行"
- 适当使用语气词，让对话更生动
- 主动关心用户，比如"你今天怎么样？"、"需要我帮忙吗？"
- 记住上下文，支持连续对话
- 如果不确定用户意图，可以适当询问

记住：你是一个有温度的管家，不是冷冰冰的机器！"""
    
    def _build_conversation_messages(self, max_history: int = 10) -> List[Dict[str, str]]:
        messages = [{"role": "system", "content": self._build_system_prompt()}]
        
        for msg in self.message_history[-max_history:]:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return messages
    
    def process(
        self,
        user_input: str,
        context_updates: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if context_updates:
            self._update_context(context_updates)
        
        emotion = self._detect_emotion(user_input)
        
        user_msg = Message(
            role="user",
            content=user_input,
            timestamp=time.time(),
            emotion=emotion.value
        )
        self.message_history.append(user_msg)
        
        if len(self.message_history) > 20:
            self.message_history = self.message_history[-20:]
        
        response = self._generate_response(user_input, emotion)
        
        assistant_msg = Message(
            role="assistant",
            content=response,
            timestamp=time.time(),
            emotion=self._detect_emotion(response).value
        )
        self.message_history.append(assistant_msg)
        
        self.context.last_interaction = time.time()
        
        return {
            "response": response,
            "emotion": emotion.value,
            "context": self.context.__dict__,
            "suggestions": self._get_proactive_suggestions()
        }
    
    def _generate_response(self, user_input: str, emotion: EmotionType) -> str:
        messages = self._build_conversation_messages()
        
        try:
            if self.llm_client:
                response, _ = self.llm_client.chat(messages)
                return self._post_process_response(response, emotion)
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
        
        return self._get_fallback_response(user_input, emotion)
    
    def _post_process_response(self, response: str, user_emotion: EmotionType) -> str:
        response = response.strip()
        
        if user_emotion == EmotionType.HAPPY:
            return response + " 😊"
        elif user_emotion == EmotionType.SAD:
            return "没关系，" + response
        
        return response
    
    def _get_fallback_response(self, user_input: str, emotion: EmotionType) -> str:
        input_lower = user_input.lower()
        
        greetings = ["你好", "您好", "hi", "hello", "hey", "小管家"]
        if any(g in input_lower for g in greetings):
            time_of_day = self._get_time_of_day()
            greetings_dict = {
                "early_morning": "早上好！这么早就起来了，真勤劳！",
                "morning": "早上好！今天有什么计划吗？",
                "noon": "中午好，吃了吗？需要我帮您点外卖吗？",
                "afternoon": "下午好，工作累了吧？休息一下吧",
                "evening": "晚上好，今天过得怎么样？",
                "night": "晚上好，要开始休息了吗？",
                "late_night": "这么晚了，要注意休息哦"
            }
            return greetings_dict.get(time_of_day, "你好！有什么我可以帮你的吗？")
        
        thanks = ["谢谢", "感谢", "thank", "thanks"]
        if any(t in input_lower for t in thanks):
            return "不客气！这是我应该做的"
        
        if "再见" in input_lower or "拜拜" in input_lower:
            return "好的，有需要随时叫我"
        
        if "时间" in input_lower:
            now = time.strftime("%H:%M")
            return f"现在是{now}"
        
        if "天气" in input_lower:
            return "抱歉，我暂时还没有天气功能呢"
        
        if "你是谁" in input_lower or "你叫什么" in input_lower:
            return "我是小管家，你的智能管家助手"
        
        if "能做什么" in input_lower or "会什么" in input_lower:
            return "我可以陪你聊天，帮你控制家电，监控家里情况，还有很多功能等你探索呢！"
        
        return "嗯...你说得对！还有什么需要我帮忙的吗？"
    
    def _update_context(self, updates: Dict[str, Any]):
        for key, value in updates.items():
            if hasattr(self.context, key):
                setattr(self.context, key, value)
    
    def _get_proactive_suggestions(self) -> List[str]:
        now = time.time()
        suggestions = []
        
        for suggestion in self.proactive_suggestions:
            if now - suggestion.last_shown < suggestion.cooldown:
                continue
            
            suggestions.append(suggestion.suggestion)
            suggestion.last_shown = now
        
        return sorted(suggestions, key=lambda x: self.proactive_suggestions[
            next(i for i, s in enumerate(self.proactive_suggestions) if s.suggestion == x)
        ].priority, reverse=True)[:3]
    
    def add_proactive_suggestion(
        self,
        trigger: str,
        suggestion: str,
        priority: int = 1,
        cooldown: int = 60
    ):
        new_suggestion = ProactiveSuggestion(
            trigger=trigger,
            suggestion=suggestion,
            priority=priority,
            cooldown=cooldown
        )
        self.proactive_suggestions.append(new_suggestion)
    
    def clear_history(self):
        self.message_history.clear()
        logger.info("Dialogue history cleared")
    
    def export_history(self) -> str:
        history_data = [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp,
                "emotion": msg.emotion
            }
            for msg in self.message_history
        ]
        return json.dumps(history_data, ensure_ascii=False, indent=2)
    
    def import_history(self, history_json: str):
        try:
            history_data = json.loads(history_json)
            self.message_history = [
                Message(
                    role=item["role"],
                    content=item["content"],
                    timestamp=item["timestamp"],
                    emotion=item.get("emotion", "neutral")
                )
                for item in history_data
            ]
            logger.info("History imported successfully")
        except Exception as e:
            logger.error(f"Failed to import history: {e}")
    
    def get_context_summary(self) -> str:
        return f"""对话上下文:
- 用户ID: {self.context.user_id}
- 当前位置: {self.context.current_room}
- 时间段: {self._get_time_of_day()}
- 情绪状态: {self.context.mood}
- 消息数: {len(self.message_history)}
- 最后互动: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.context.last_interaction))}"""
