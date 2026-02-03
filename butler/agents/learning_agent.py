from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import json

from .agent import Agent, AgentConfig, AgentMessage, MessageType, AgentTask, AgentCapability

logger = logging.getLogger(__name__)

class LearningType(Enum):
    PATTERN_RECOGNITION = "pattern_recognition"
    USER_PREFERENCE = "user_preference"
    BEHAVIOR_MODELING = "behavior_modeling"
    PREDICTION = "prediction"
    OPTIMIZATION = "optimization"

class LearningMode(Enum):
    ONLINE = "online"
    BATCH = "batch"
    HYBRID = "hybrid"

@dataclass
class LearningData:
    data_id: str
    learning_type: LearningType
    features: Dict[str, Any]
    labels: Optional[Dict[str, Any]] = None
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "data_id": self.data_id,
            "learning_type": self.learning_type.value,
            "features": self.features,
            "labels": self.labels,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "metadata": self.metadata
        }

@dataclass
class LearningModel:
    model_id: str
    model_type: LearningType
    model_name: str
    version: str
    accuracy: float = 0.0
    last_trained: Optional[datetime] = None
    training_samples: int = 0
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_type": self.model_type.value,
            "model_name": self.model_name,
            "version": self.version,
            "accuracy": self.accuracy,
            "last_trained": self.last_trained.isoformat() if self.last_trained else None,
            "training_samples": self.training_samples,
            "parameters": self.parameters,
            "is_active": self.is_active
        }

class LearningAgent(Agent):
    def __init__(
        self,
        config: AgentConfig,
        storage_path: Optional[str] = None
    ):
        super().__init__(config)
        self._storage_path = storage_path
        self._learning_data: List[LearningData] = []
        self._models: Dict[str, LearningModel] = {}
        self._patterns: Dict[str, List[Dict[str, Any]]] = {}
        self._user_preferences: Dict[str, Dict[str, Any]] = {}
        self._behavior_models: Dict[str, Dict[str, Any]] = {}
        self._predictions: Dict[str, Dict[str, Any]] = {}
        self._learning_mode = LearningMode.HYBRID
        self._max_data_size = 10000
        self._min_samples_for_training = 100
        self._model_update_interval = 3600.0
        self._last_model_update = datetime.now()

    async def initialize(self) -> bool:
        try:
            self.add_capability(AgentCapability(
                name="pattern_recognition",
                description="Recognize patterns in user behavior and system events",
                input_types=["events", "behaviors"],
                output_types=["patterns", "insights"],
                parameters={
                    "min_occurrences": {"type": "integer", "default": 5},
                    "time_window_hours": {"type": "float", "default": 24.0}
                }
            ))

            self.add_capability(AgentCapability(
                name="user_preference_learning",
                description="Learn and adapt to user preferences",
                input_types=["user_actions", "feedback"],
                output_types=["preferences", "recommendations"]
            ))

            self.add_capability(AgentCapability(
                name="behavior_modeling",
                description="Model user and system behavior patterns",
                input_types=["behavioral_data"],
                output_types=["behavior_models", "predictions"]
            ))

            self.add_capability(AgentCapability(
                name="prediction",
                description="Predict future events and user actions",
                input_types=["context", "history"],
                output_types=["predictions", "confidence"]
            ))

            self.add_capability(AgentCapability(
                name="optimization",
                description="Optimize system settings based on learned patterns",
                input_types=["current_state", "goals"],
                output_types=["optimizations", "expected_improvements"]
            ))

            await self._load_models()
            await self._load_learning_data()

            return True

        except Exception as e:
            self._logger.error(f"Failed to initialize learning agent: {e}")
            return False

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
        content = message.content if isinstance(message.content, dict) else {"action": message.content}

        action = content.get("action", "learn")

        if action == "learn":
            result = await self._learn(
                data_type=content.get("data_type", "behavior"),
                features=content.get("features", {}),
                labels=content.get("labels")
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        elif action == "recognize_patterns":
            result = await self._recognize_patterns(
                data_type=content.get("data_type", "behavior"),
                time_window=content.get("time_window_hours", 24.0),
                min_occurrences=content.get("min_occurrences", 5)
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        elif action == "predict":
            result = await self._predict(
                prediction_type=content.get("prediction_type", "user_action"),
                context=content.get("context", {}),
                horizon=content.get("horizon", 1)
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        elif action == "get_preferences":
            result = await self._get_user_preferences(
                user_id=content.get("user_id", "default")
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        elif action == "optimize":
            result = await self._optimize(
                current_state=content.get("current_state", {}),
                goals=content.get("goals", [])
            )
            return AgentMessage(
                message_id=message.message_id + "_response",
                sender_id=self.agent_id,
                recipient_id=message.sender_id,
                message_type=MessageType.RESPONSE,
                content=result
            )

        return None

    async def _handle_notification(self, message: AgentMessage):
        content = message.content if isinstance(message.content, dict) else {}

        if content.get("type") == "user_feedback":
            await self._process_user_feedback(
                user_id=content.get("user_id", "default"),
                feedback=content.get("feedback", {})
            )

        elif content.get("type") == "behavior_event":
            await self._learn(
                data_type="behavior",
                features=content.get("features", {}),
                labels=content.get("labels")
            )

    async def _learn(
        self,
        data_type: str,
        features: Dict[str, Any],
        labels: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        import uuid

        learning_data = LearningData(
            data_id=str(uuid.uuid4()),
            learning_type=LearningType(data_type) if data_type in [lt.value for lt in LearningType] else LearningType.BEHAVIOR_MODELING,
            features=features,
            labels=labels
        )

        self._learning_data.append(learning_data)

        if len(self._learning_data) > self._max_data_size:
            self._learning_data = self._learning_data[-self._max_data_size:]

        if self._learning_mode == LearningMode.ONLINE or (self._learning_mode == LearningMode.HYBRID and len(self._learning_data) % 10 == 0):
            await self._update_models()

        return {
            "data_id": learning_data.data_id,
            "status": "learned",
            "total_samples": len(self._learning_data),
            "timestamp": learning_data.timestamp.isoformat()
        }

    async def _recognize_patterns(
        self,
        data_type: str,
        time_window: float = 24.0,
        min_occurrences: int = 5
    ) -> Dict[str, Any]:
        cutoff_time = datetime.now() - timedelta(hours=time_window)
        recent_data = [
            d for d in self._learning_data
            if d.timestamp > cutoff_time
        ]

        patterns = await self._extract_patterns(recent_data, min_occurrences)

        return {
            "data_type": data_type,
            "time_window_hours": time_window,
            "patterns": patterns,
            "pattern_count": len(patterns),
            "sample_count": len(recent_data)
        }

    async def _extract_patterns(
        self,
        data: List[LearningData],
        min_occurrences: int
    ) -> List[Dict[str, Any]]:
        patterns = []

        feature_patterns: Dict[str, Dict[Tuple[Any, ...], int]] = {}

        for item in data:
            for feature_key, feature_value in item.features.items():
                if isinstance(feature_value, dict):
                    key_tuple = tuple(sorted(feature_value.items()))
                elif isinstance(feature_value, (list, tuple)):
                    key_tuple = tuple(feature_value)
                else:
                    key_tuple = (feature_value,)

                if feature_key not in feature_patterns:
                    feature_patterns[feature_key] = {}

                if key_tuple not in feature_patterns[feature_key]:
                    feature_patterns[feature_key][key_tuple] = 0
                feature_patterns[feature_key][key_tuple] += 1

        for feature_key, pattern_counts in feature_patterns.items():
            for pattern_value, count in pattern_counts.items():
                if count >= min_occurrences:
                    patterns.append({
                        "feature": feature_key,
                        "pattern": pattern_value if len(pattern_value) > 1 else pattern_value[0],
                        "occurrences": count,
                        "frequency": count / len(data) if data else 0
                    })

        patterns.sort(key=lambda p: p["occurrences"], reverse=True)

        return patterns[:50]

    async def _predict(
        self,
        prediction_type: str,
        context: Dict[str, Any],
        horizon: int = 1
    ) -> Dict[str, Any]:
        import uuid

        prediction_id = str(uuid.uuid4())

        if prediction_type == "user_action":
            predictions = await self._predict_user_actions(context, horizon)
        elif prediction_type == "device_state":
            predictions = await self._predict_device_states(context, horizon)
        elif prediction_type == "energy_consumption":
            predictions = await self._predict_energy_consumption(context, horizon)
        else:
            predictions = []

        prediction_data = {
            "prediction_id": prediction_id,
            "prediction_type": prediction_type,
            "context": context,
            "predictions": predictions,
            "horizon": horizon,
            "timestamp": datetime.now().isoformat()
        }

        self._predictions[prediction_id] = prediction_data

        return prediction_data

    async def _predict_user_actions(
        self,
        context: Dict[str, Any],
        horizon: int
    ) -> List[Dict[str, Any]]:
        time_of_day = context.get("time_of_day", datetime.now().hour)
        day_of_week = context.get("day_of_week", datetime.now().strftime("%A"))
        user_id = context.get("user_id", "default")

        relevant_data = [
            d for d in self._learning_data
            if "time" in d.features or "hour" in d.features
        ]

        predictions = []

        for i in range(horizon):
            predicted_hour = (time_of_day + i) % 24

            similar_contexts = [
                d for d in relevant_data
                if d.features.get("hour") == predicted_hour
            ]

            if similar_contexts:
                action_counts = {}
                for d in similar_contexts:
                    action = d.labels.get("action") if d.labels else None
                    if action:
                        action_counts[action] = action_counts.get(action, 0) + 1

                if action_counts:
                    most_likely = max(action_counts.items(), key=lambda x: x[1])
                    predictions.append({
                        "step": i + 1,
                        "predicted_time": f"{predicted_hour:02d}:00",
                        "predicted_action": most_likely[0],
                        "confidence": most_likely[1] / len(similar_contexts)
                    })

        return predictions

    async def _predict_device_states(
        self,
        context: Dict[str, Any],
        horizon: int
    ) -> List[Dict[str, Any]]:
        device_id = context.get("device_id")

        relevant_data = [
            d for d in self._learning_data
            if d.features.get("device_id") == device_id
        ]

        predictions = []

        for i in range(horizon):
            if relevant_data:
                state_counts = {}
                for d in relevant_data:
                    state = d.labels.get("state") if d.labels else d.features.get("state")
                    if state:
                        state_counts[state] = state_counts.get(state, 0) + 1

                if state_counts:
                    most_likely = max(state_counts.items(), key=lambda x: x[1])
                    predictions.append({
                        "step": i + 1,
                        "device_id": device_id,
                        "predicted_state": most_likely[0],
                        "confidence": most_likely[1] / len(relevant_data)
                    })

        return predictions

    async def _predict_energy_consumption(
        self,
        context: Dict[str, Any],
        horizon: int
    ) -> List[Dict[str, Any]]:
        return []

    async def _get_user_preferences(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        return self._user_preferences.get(user_id, {})

    async def _process_user_feedback(
        self,
        user_id: str,
        feedback: Dict[str, Any]
    ):
        if user_id not in self._user_preferences:
            self._user_preferences[user_id] = {}

        preference_type = feedback.get("type", "general")
        value = feedback.get("value")
        weight = feedback.get("weight", 1.0)

        if preference_type not in self._user_preferences[user_id]:
            self._user_preferences[user_id][preference_type] = {"values": {}, "weights": {}}

        if value is not None:
            current_weight = self._user_preferences[user_id][preference_type]["weights"].get(value, 0)
            new_weight = current_weight + weight
            self._user_preferences[user_id][preference_type]["values"][value] = new_weight
            self._user_preferences[user_id][preference_type]["weights"][value] = new_weight

    async def _optimize(
        self,
        current_state: Dict[str, Any],
        goals: List[str]
    ) -> Dict[str, Any]:
        optimizations = []

        if "energy" in goals:
            energy_opt = await self._optimize_energy(current_state)
            optimizations.append(energy_opt)

        if "comfort" in goals:
            comfort_opt = await self._optimize_comfort(current_state)
            optimizations.append(comfort_opt)

        if "security" in goals:
            security_opt = await self._optimize_security(current_state)
            optimizations.append(security_opt)

        return {
            "current_state": current_state,
            "goals": goals,
            "optimizations": optimizations,
            "timestamp": datetime.now().isoformat()
        }

    async def _optimize_energy(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "energy",
            "optimizations": [
                {"action": "adjust_temperature", "target": "optimal_range", "saving": "10%"},
                {"action": "dim_lights", "condition": "daylight_sufficient", "saving": "5%"}
            ],
            "expected_improvement": "15% energy reduction"
        }

    async def _optimize_comfort(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "comfort",
            "optimizations": [
                {"action": "adjust_humidity", "target": "40-60%", "impact": "improved"}
            ],
            "expected_improvement": "Enhanced comfort level"
        }

    async def _optimize_security(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "security",
            "optimizations": [
                {"action": "activate_sensors", "condition": "away_mode", "impact": "full_coverage"}
            ],
            "expected_improvement": "Improved security coverage"
        }

    async def _update_models(self):
        now = datetime.now()
        if (now - self._last_model_update).total_seconds() < self._model_update_interval:
            return

        if len(self._learning_data) < self._min_samples_for_training:
            return

        for model in self._models.values():
            if model.is_active:
                await self._train_model(model)

        self._last_model_update = now

    async def _train_model(self, model: LearningModel):
        model.last_trained = datetime.now()
        model.training_samples = len(self._learning_data)
        model.accuracy = min(0.95, 0.5 + (model.training_samples / 10000) * 0.45)

        self._logger.info(f"Trained model {model.model_id} with accuracy {model.accuracy:.2f}")

    async def _load_models(self):
        if self._storage_path:
            try:
                model_file = f"{self._storage_path}/models.json"
                import os
                if os.path.exists(model_file):
                    with open(model_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for model_data in data.get("models", []):
                            model = LearningModel(**model_data)
                            self._models[model.model_id] = model
                    self._logger.info(f"Loaded {len(self._models)} models")
            except Exception as e:
                self._logger.error(f"Failed to load models: {e}")

    async def _load_learning_data(self):
        if self._storage_path:
            try:
                data_file = f"{self._storage_path}/learning_data.json"
                import os
                if os.path.exists(data_file):
                    with open(data_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        for data_item in data.get("data", []):
                            learning_data = LearningData(**data_item)
                            self._learning_data.append(learning_data)
                    self._logger.info(f"Loaded {len(self._learning_data)} learning data samples")
            except Exception as e:
                self._logger.error(f"Failed to load learning data: {e}")

    async def execute_task(self, task: AgentTask) -> Any:
        task_type = task.task_type
        payload = task.payload

        if task_type == "learn":
            return await self._learn(
                data_type=payload.get("data_type", "behavior"),
                features=payload.get("features", {}),
                labels=payload.get("labels")
            )

        elif task_type == "recognize_patterns":
            return await self._recognize_patterns(
                data_type=payload.get("data_type", "behavior"),
                time_window=payload.get("time_window_hours", 24.0),
                min_occurrences=payload.get("min_occurrences", 5)
            )

        elif task_type == "predict":
            return await self._predict(
                prediction_type=payload.get("prediction_type", "user_action"),
                context=payload.get("context", {}),
                horizon=payload.get("horizon", 1)
            )

        elif task_type == "optimize":
            return await self._optimize(
                current_state=payload.get("current_state", {}),
                goals=payload.get("goals", [])
            )

        raise ValueError(f"Unknown task type: {task_type}")

    async def shutdown(self):
        await self._save_models()
        await self._save_learning_data()
        self._logger.info("Learning agent shutting down")

    async def _save_models(self):
        if self._storage_path:
            try:
                import os
                os.makedirs(self._storage_path, exist_ok=True)

                model_file = f"{self._storage_path}/models.json"
                data = {
                    "models": [model.to_dict() for model in self._models.values()],
                    "saved_at": datetime.now().isoformat()
                }

                with open(model_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                self._logger.info(f"Saved {len(self._models)} models")

            except Exception as e:
                self._logger.error(f"Failed to save models: {e}")

    async def _save_learning_data(self):
        if self._storage_path:
            try:
                import os
                os.makedirs(self._storage_path, exist_ok=True)

                data_file = f"{self._storage_path}/learning_data.json"
                data = {
                    "data": [d.to_dict() for d in self._learning_data[-5000:]],
                    "saved_at": datetime.now().isoformat(),
                    "total_samples": len(self._learning_data)
                }

                with open(data_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                self._logger.info(f"Saved learning data")

            except Exception as e:
                self._logger.error(f"Failed to save learning data: {e}")

    def get_learning_statistics(self) -> Dict[str, Any]:
        return {
            "total_samples": len(self._learning_data),
            "model_count": len(self._models),
            "pattern_count": len(self._patterns),
            "user_count": len(self._user_preferences),
            "prediction_count": len(self._predictions),
            "learning_mode": self._learning_mode.value,
            "last_model_update": self._last_model_update.isoformat() if self._last_model_update else None
        }

    def to_dict(self) -> Dict[str, Any]:
        base_dict = super().to_dict()
        base_dict.update({
            "learning_capabilities": list(self.capabilities.keys()),
            "statistics": self.get_learning_statistics()
        })
        return base_dict
