from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from .agent import Agent, AgentConfig, AgentMessage, MessageType, AgentTask, AgentCapability

logger = logging.getLogger(__name__)

class DecisionType(Enum):
    AUTOMATION = "automation"
    DEVICE_CONTROL = "device_control"
    ACTION_SELECTION = "action_selection"
    RESOURCE_ALLOCATION = "resource_allocation"
    PRIORITY_ADJUSTMENT = "priority_adjustment"
    CONFLICT_RESOLUTION = "conflict_resolution"

class DecisionOutcome(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    MODIFIED = "modified"

@dataclass
class DecisionRequest:
    request_id: str
    decision_type: DecisionType
    requester: str
    payload: Dict[str, Any]
    context: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "decision_type": self.decision_type.value,
            "requester": self.requester,
            "payload": self.payload,
            "context": self.context,
            "priority": self.priority,
            "created_at": self.created_at.isoformat()
        }

@dataclass
class DecisionResponse:
    response_id: str
    request_id: str
    outcome: DecisionOutcome
    reasoning: str
    decision_data: Dict[str, Any] = field(default_factory=dict)
    alternative_options: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_id": self.response_id,
            "request_id": self.request_id,
            "outcome": self.outcome.value,
            "reasoning": self.reasoning,
            "decision_data": self.decision_data,
            "alternative_options": self.alternative_options,
            "timestamp": self.timestamp.isoformat()
        }

class DecisionAgent(Agent):
    def __init__(
        self,
        config: AgentConfig,
        llm_client: Any = None
    ):
        super().__init__(config)
        self._llm_client = llm_client
        self._decision_history: List[Dict[str, Any]] = []
        self._decision_rules: Dict[str, List[Dict[str, Any]]] = {}
        self._max_history_length = 500
        self._default_outcome = DecisionOutcome.DEFERRED

    async def initialize(self) -> bool:
        try:
            self.add_capability(AgentCapability(
                name="decision_making",
                description="Make intelligent decisions based on context and rules",
                input_types=["decision_request", "context"],
                output_types=["decision_response", "reasoning"],
                parameters={
                    "use_llm": {"type": "boolean", "default": True},
                    "max_reasoning_length": {"type": "integer", "default": 500}
                }
            ))

            self.add_capability(AgentCapability(
                name="conflict_resolution",
                description="Resolve conflicts between competing requests",
                input_types=["conflict_description", "requests"],
                output_types=["resolution", "reasoning"]
            ))

            self.add_capability(AgentCapability(
                name="priority_assessment",
                description="Assess and adjust priority of tasks",
                input_types=["task", "context"],
                output_types=["priority", "reasoning"]
            ))

            self.add_capability(AgentCapability(
                name="resource_allocation",
                description="Allocate resources efficiently",
                input_types=["resource_request", "availability"],
                output_types=["allocation", "reasoning"]
            ))

            await self._load_default_rules()

            return True

        except Exception as e:
            self._logger.error(f"Failed to initialize decision agent: {e}")
            return False

    async def _load_default_rules(self):
        self._decision_rules["automation"] = [
            {
                "name": "safety_first",
                "condition": lambda req: any(
                    kw in str(req.payload).lower() 
                    for kw in ["emergency", "fire", "gas", "leak", "alarm"]
                ),
                "outcome": DecisionOutcome.APPROVED,
                "priority_boost": 100
            },
            {
                "name": "energy_saving_hours",
                "condition": lambda req: self._is_energy_saving_hours() and req.payload.get("energy_impact", 0) > 50,
                "outcome": DecisionOutcome.DEFERRED,
                "reasoning": "Deferred due to energy saving hours"
            },
            {
                "name": "user_preference_override",
                "condition": lambda req: req.payload.get("user_preference") == "block",
                "outcome": DecisionOutcome.REJECTED,
                "reasoning": "Blocked by user preference"
            }
        ]

        self._decision_rules["device_control"] = [
            {
                "name": "device_availability",
                "condition": lambda req: req.payload.get("device_available", True) is False,
                "outcome": DecisionOutcome.DEFERRED,
                "reasoning": "Device not available"
            },
            {
                "name": "conflict_check",
                "condition": lambda req: self._has_conflicting_operation(req),
                "outcome": DecisionOutcome.MODIFIED,
                "reasoning": "Modified to avoid conflict"
            }
        ]

    async def process_message(self, message: AgentMessage) -> Optional[AgentMessage]:
        try:
            if message.message_type == MessageType.REQUEST:
                return await self._handle_request(message)

            elif message.message_type == MessageType.NOTIFICATION:
                await self._handle_notification(message)

        except Exception as e:
            self._logger.error(f"Error processing message: {e}")

        return None

    async def _handle_request(self, message: AgentMessage) -> Optional[AgentMessage]:
        content = message.content if isinstance(message.content, dict) else {"payload": message.content}

        action = content.get("action", "decide")

        if action == "decide":
            request = content.get("request")
            if request:
                decision_response = await self._make_decision(request)
                return AgentMessage(
                    message_id=message.message_id + "_response",
                    sender_id=self.agent_id,
                    recipient_id=message.sender_id,
                    message_type=MessageType.RESPONSE,
                    content=decision_response.to_dict()
                )

        elif action == "resolve_conflict":
            response = await self._resolve_conflict(
                conflict_description=content.get("conflict_description", ""),
                requests=content.get("requests", [])
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=response
            )

        elif action == "assess_priority":
            response = await self._assess_priority(
                task=content.get("task", {}),
                context=content.get("context", {})
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=response
            )

        return None

    async def _handle_notification(self, message: AgentMessage):
        content = message.content if isinstance(message.content, dict) else {}

        if content.get("type") == "update_rules":
            await self._update_rules(content.get("rules", {}))

    async def _make_decision(self, request: DecisionRequest) -> DecisionResponse:
        import uuid

        rule_based_outcome = await self._apply_rules(request)

        if rule_based_outcome:
            response = DecisionResponse(
                response_id=str(uuid.uuid4()),
                request_id=request.request_id,
                outcome=rule_based_outcome["outcome"],
                reasoning=rule_based_outcome["reasoning"],
                decision_data=rule_based_outcome.get("data", {})
            )
        elif self._llm_client and request.payload.get("use_llm", True):
            response = await self._make_llm_decision(request)
        else:
            response = DecisionResponse(
                response_id=str(uuid.uuid4()),
                request_id=request.request_id,
                outcome=self._default_outcome,
                reasoning="No matching rules and LLM unavailable",
                decision_data={}
            )

        self._decision_history.append({
            "request": request.to_dict(),
            "response": response.to_dict(),
            "timestamp": datetime.now().isoformat()
        })

        if len(self._decision_history) > self._max_history_length:
            self._decision_history = self._decision_history[-self._max_history_length:]

        return response

    async def _apply_rules(self, request: DecisionRequest) -> Optional[Dict[str, Any]]:
        decision_type = request.decision_type.value

        if decision_type not in self._decision_rules:
            return None

        rules = self._decision_rules[decision_type]

        for rule in rules:
            try:
                if rule["condition"](request):
                    return {
                        "outcome": rule["outcome"],
                        "reasoning": rule.get("reasoning", f"Rule '{rule['name']}' matched"),
                        "data": rule.get("data", {})
                    }
            except Exception as e:
                self._logger.error(f"Error applying rule {rule['name']}: {e}")

        return None

    async def _make_llm_decision(self, request: DecisionRequest) -> DecisionResponse:
        import uuid

        prompt = self._build_decision_prompt(request)

        try:
            if hasattr(self._llm_client, "chat"):
                response = await self._llm_client.chat(prompt)
            else:
                response = "Deferred - LLM unavailable"

            return DecisionResponse(
                response_id=str(uuid.uuid4()),
                request_id=request.request_id,
                outcome=DecisionOutcome.DEFERRED,
                reasoning=response[:500],
                decision_data={"llm_used": True}
            )

        except Exception as e:
            self._logger.error(f"LLM decision failed: {e}")
            return DecisionResponse(
                response_id=str(uuid.uuid4()),
                request_id=request.request_id,
                outcome=self._default_outcome,
                reasoning=f"LLM error: {str(e)[:200]}",
                decision_data={}
            )

    def _build_decision_prompt(self, request: DecisionRequest) -> str:
        return f"""You are a smart home decision assistant. Make a decision based on the following request:

Request Type: {request.decision_type.value}
Requester: {request.requester}
Priority: {request.priority}

Payload: {request.payload}

Context: {request.context}

Respond with:
1. Decision outcome (APPROVED/REJECTED/DEFERRED/MODIFIED)
2. Brief reasoning (under 200 words)
3. Any additional data needed"""

    async def _resolve_conflict(
        self,
        conflict_description: str,
        requests: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        resolutions = []

        for req in requests:
            decision = await self._make_decision(
                DecisionRequest(
                    request_id=req.get("request_id", ""),
                    decision_type=DecisionType(req.get("decision_type", "action_selection")),
                    requester=req.get("requester", "unknown"),
                    payload=req.get("payload", {}),
                    context=req.get("context", {})
                )
            )
            resolutions.append(decision.to_dict())

        return {
            "conflict_description": conflict_description,
            "resolutions": resolutions,
            "timestamp": datetime.now().isoformat()
        }

    async def _assess_priority(
        self,
        task: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        base_priority = task.get("priority", 0)

        adjustments = {
            "user_requested": 20 if task.get("user_requested") else 0,
            "safety_related": 50 if any(
                kw in str(task.get("description", "")).lower()
                for kw in ["emergency", "safety", "alert"]
            ) else 0,
            "time_sensitive": 30 if task.get("deadline") else 0,
            "energy_aware": -10 if self._is_energy_saving_hours() and task.get("energy_impact", 0) > 30 else 0
        }

        final_priority = base_priority + sum(adjustments.values())

        return {
            "task_id": task.get("task_id"),
            "base_priority": base_priority,
            "adjustments": adjustments,
            "final_priority": max(0, min(100, final_priority)),
            "reasoning": f"Priority adjusted from {base_priority} to {final_priority}",
            "timestamp": datetime.now().isoformat()
        }

    def _is_energy_saving_hours(self) -> bool:
        hour = datetime.now().hour
        return hour >= 23 or hour <= 6

    def _has_conflicting_operation(self, request: DecisionRequest) -> bool:
        device = request.payload.get("device")
        operation = request.payload.get("operation")

        for history_item in self._decision_history[-10:]:
            hist_payload = history_item.get("request", {}).get("payload", {})
            if hist_payload.get("device") == device and hist_payload.get("operation") != operation:
                if (datetime.now() - datetime.fromisoformat(history_item["timestamp"])).seconds < 60:
                    return True

        return False

    async def _update_rules(self, rules: Dict[str, List[Dict[str, Any]]]):
        for rule_type, rule_list in rules.items():
            self._decision_rules[rule_type] = rule_list

        self._logger.info(f"Updated decision rules for {len(rules)} types")

    async def execute_task(self, task: AgentTask) -> Any:
        task_type = task.task_type
        payload = task.payload

        if task_type == "decide":
            request = DecisionRequest(**payload.get("request", {}))
            return await self._make_decision(request)

        elif task_type == "resolve_conflict":
            return await self._resolve_conflict(
                conflict_description=payload.get("conflict_description", ""),
                requests=payload.get("requests", [])
            )

        elif task_type == "assess_priority":
            return await self._assess_priority(
                task=payload.get("task", {}),
                context=payload.get("context", {})
            )

        elif task_type == "batch_decide":
            requests = [
                DecisionRequest(**req)
                for req in payload.get("requests", [])
            ]
            results = []
            for request in requests:
                result = await self._make_decision(request)
                results.append(result.to_dict())
            return results

        raise ValueError(f"Unknown task type: {task_type}")

    async def shutdown(self):
        self._logger.info("Decision agent shutting down")

    def get_decision_history(
        self,
        limit: int = 50,
        decision_type: Optional[DecisionType] = None
    ) -> List[Dict[str, Any]]:
        history = self._decision_history[-limit:]

        if decision_type:
            history = [
                h for h in history
                if h.get("request", {}).get("decision_type") == decision_type.value
            ]

        return history

    def get_rules(self, rule_type: Optional[str] = None) -> Dict[str, Any]:
        if rule_type:
            return {"rule_type": rule_type, "rules": self._decision_rules.get(rule_type, [])}
        return self._decision_rules.copy()

    def clear_history(self):
        self._decision_history.clear()

    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            "decision_capabilities": list(self.capabilities.keys()),
            "decision_history_size": len(self._decision_history),
            "rules_count": sum(len(rules) for rules in self._decision_rules.values()),
            "llm_available": self._llm_client is not None
        })
        return base_dict
