from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .context_manager import ContextManager, ConversationContext
from .intent_classifier import IntentClassifier, Intent
from .reference_resolver import ReferenceResolver

logger = logging.getLogger(__name__)


@dataclass
class DialogueTurn:
    user_input: str
    user_intent: Intent
    context: ConversationContext
    response: str = ""
    actions: List[Dict[str, Any]] = field(default_factory=list)
    resolved_references: Dict[str, Any] = field(default_factory=dict)
    follow_up_questions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_input": self.user_input,
            "user_intent": self.user_intent.to_dict(),
            "context_id": self.context.conversation_id,
            "response": self.response,
            "actions": self.actions,
            "resolved_references": self.resolved_references,
            "follow_up_questions": self.follow_up_questions,
        }


class DialogueEngine:
    def __init__(
        self,
        context_manager: Optional[ContextManager] = None,
        intent_classifier: Optional[IntentClassifier] = None,
        reference_resolver: Optional[ReferenceResolver] = None
    ) -> None:
        self.context_manager = context_manager or ContextManager()
        self.intent_classifier = intent_classifier or IntentClassifier()
        self.reference_resolver = reference_resolver or ReferenceResolver()
        self._turn_history: List[DialogueTurn] = []

    def process(
        self,
        user_input: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> DialogueTurn:
        additional_context = additional_context or {}
        
        context = self.context_manager.get_or_create_context(user_id, conversation_id)
        
        context_dict = self._build_context_dict(context, additional_context)
        
        intent = self.intent_classifier.classify(user_input, context_dict)
        
        reference_resolution = self.reference_resolver.resolve(user_input, context_dict)
        
        resolved_input = user_input
        if reference_resolution.get("resolved"):
            resolved_input = reference_resolution["resolution"].get("replaced_text", user_input)
        
        context.add_message("user", user_input, {
            "intent": intent.to_dict(),
            "resolved": reference_resolution.get("resolved", False),
        })
        
        response, actions, follow_up = self._generate_response(
            intent,
            resolved_input,
            context,
            context_dict,
            reference_resolution
        )
        
        if intent.action:
            context.update_context({
                "last_action": {
                    "action": intent.action,
                    "target": intent.target,
                    "location": intent.location,
                    "parameters": intent.parameters,
                }
            })
        
        if intent.target:
            context.update_context({"last_device": intent.target})
        
        if intent.location:
            context.update_context({"current_room": intent.location})
        
        turn = DialogueTurn(
            user_input=user_input,
            user_intent=intent,
            context=context,
            response=response,
            actions=actions,
            resolved_references=reference_resolution,
            follow_up_questions=follow_up,
        )
        
        self._turn_history.append(turn)
        if len(self._turn_history) > 100:
            self._turn_history = self._turn_history[-100:]
        
        return turn

    def _build_context_dict(
        self,
        context: ConversationContext,
        additional_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        recent_messages = context.get_recent_messages(3)
        
        context_dict = {
            "conversation_id": context.conversation_id,
            "user_id": context.user_id,
            "current_room": context.current_room,
            "last_device": context.last_device,
            "last_action": context.last_action,
            "active_intent": context.active_intent,
            "recent_messages": [msg.to_dict() for msg in recent_messages],
            "metadata": context.metadata,
        }
        
        context_dict.update(additional_context)
        return context_dict

    def _generate_response(
        self,
        intent: Intent,
        resolved_input: str,
        context: ConversationContext,
        context_dict: Dict[str, Any],
        reference_resolution: Dict[str, Any]
    ) -> tuple[str, List[Dict[str, Any]], List[str]]:
        response = ""
        actions = []
        follow_up = []

        if intent.intent_type.value == "control":
            response, actions = self._handle_control_intent(intent, context_dict)
        
        elif intent.intent_type.value == "query":
            response, follow_up = self._handle_query_intent(intent, context_dict)
        
        elif intent.intent_type.value == "scene":
            response, actions = self._handle_scene_intent(intent, context_dict)
        
        elif intent.intent_type.value == "goal":
            response, actions = self._handle_goal_intent(intent, context_dict)
        
        elif intent.intent_type.value == "conversation":
            response = self._handle_conversation_intent(intent, context_dict)
        
        else:
            response = "抱歉，我没有完全理解您的意思。您能再详细说明一下吗？"
            follow_up = ["您是想控制设备吗？", "您是想查询状态吗？", "您是想设置场景吗？"]

        context.add_message("assistant", response, {
            "actions_count": len(actions),
            "follow_up_count": len(follow_up),
        })

        return response, actions, follow_up

    def _handle_control_intent(
        self,
        intent: Intent,
        context_dict: Dict[str, Any]
    ) -> tuple[str, List[Dict[str, Any]]]:
        actions = []
        
        if not intent.action and not intent.target:
            return "请告诉我您想控制什么设备，以及执行什么操作。", actions
        
        action_str = intent.action or "control"
        target_str = intent.target or "设备"
        location_str = intent.location or ""
        
        if location_str:
            response = f"好的，我来{action_str}{location_str}的{target_str}。"
        else:
            response = f"好的，我来{action_str}{target_str}。"
        
        actions.append({
            "action_type": f"{action_str}_device",
            "params": {
                "target": target_str,
                "location": location_str,
                **intent.parameters,
            }
        })
        
        return response, actions

    def _handle_query_intent(
        self,
        intent: Intent,
        context_dict: Dict[str, Any]
    ) -> tuple[str, List[str]]:
        follow_up = []
        
        if intent.target:
            if intent.location:
                response = f"{intent.location}的{intent.target}状态已查询。"
            else:
                response = f"{intent.target}的状态已查询。"
            follow_up.append(f"您想了解{intent.target}的详细信息吗？")
        else:
            response = "请告诉我您想查询什么设备或状态。"
            follow_up.extend(["灯光状态", "温度湿度", "所有设备"])
        
        return response, follow_up

    def _handle_scene_intent(
        self,
        intent: Intent,
        context_dict: Dict[str, Any]
    ) -> tuple[str, List[Dict[str, Any]]]:
        actions = []
        
        scene_keywords = {
            "回家": "home",
            "离家": "away",
            "睡眠": "sleep",
            "观影": "movie",
            "起床": "wake_up",
        }
        
        scene_name = None
        for keyword, scene_id in scene_keywords.items():
            if keyword in intent.raw_text.lower():
                scene_name = scene_id
                break
        
        if scene_name:
            response = f"好的，正在切换到{scene_name}场景。"
            actions.append({
                "action_type": "activate_scene",
                "params": {"scene_id": scene_name}
            })
        else:
            response = "请告诉我您想切换到哪个场景？"
        
        return response, actions

    def _handle_goal_intent(
        self,
        intent: Intent,
        context_dict: Dict[str, Any]
    ) -> tuple[str, List[Dict[str, Any]]]:
        actions = []
        
        goal_keywords = {
            "我要睡了": "sleep",
            "我要起床": "wake_up",
            "我要出门": "leave",
            "我要回家": "home",
            "我要看电影": "watch_movie",
        }
        
        goal_name = None
        for keyword, goal_id in goal_keywords.items():
            if keyword in intent.raw_text.lower():
                goal_name = goal_id
                break
        
        if goal_name == "sleep":
            response = "好的，准备进入睡眠模式。我会关掉所有灯，拉上窗帘，调低温度。"
            actions = [
                {"action_type": "turn_off", "params": {"target": "all_lights"}},
                {"action_type": "close_cover", "params": {"target": "all_curtains"}},
                {"action_type": "set_temperature", "params": {"value": 22}},
            ]
        elif goal_name:
            response = f"好的，我来帮您{goal_name}。"
            actions.append({
                "action_type": "execute_goal",
                "params": {"goal": goal_name}
            })
        else:
            response = "请告诉我您想做什么？"
        
        return response, actions

    def _handle_conversation_intent(
        self,
        intent: Intent,
        context_dict: Dict[str, Any]
    ) -> str:
        greetings = ["你好", "您好", "hi", "hello", "hey"]
        if any(g in intent.raw_text.lower() for g in greetings):
            return "你好！我是您的智能管家，有什么可以帮您的吗？"
        
        thanks = ["谢谢", "感谢", "thank", "thanks"]
        if any(t in intent.raw_text.lower() for t in thanks):
            return "不客气！还有其他需要帮助的吗？"
        
        return "我在听，请继续。"

    def get_turn_history(self, limit: int = 10) -> List[DialogueTurn]:
        return self._turn_history[-limit:]

    def clear_history(self) -> None:
        self._turn_history.clear()
        logger.info("Dialogue engine history cleared")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "context_manager": self.context_manager.to_dict(),
            "turn_history_count": len(self._turn_history),
        }
