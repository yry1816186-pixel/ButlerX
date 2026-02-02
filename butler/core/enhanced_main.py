from __future__ import annotations

import logging
import time
from typing import Optional

from butler.core.models import ButlerState, StateChange, Event, Command, ActionPlan, ActionResult
from butler.brain.planner import LLMPlanner
from butler.brain.strategy_engine import StrategyEngine, Strategy, Rule
from butler.knowledge_graph import KnowledgeGraph
from butler.conversation import DialogueEngine, ContextManager, IntentClassifier, ReferenceResolver
from butler.goal_engine import GoalEngine, GoalTemplateRegistry
from butler.automation import SceneEngine, AutomationEngine, HabitLearner
from butler.proactive import AnomalyDetector, EnergyOptimizer, PredictiveService
from butler.ir_control import IRController, IRLearner, IRMappingRegistry
from butler.simulator import VirtualDeviceManager, SceneReplayer, TestFramework

logger = logging.getLogger(__name__)


class EnhancedButlerCore:
    def __init__(self) -> None:
        self.knowledge_graph = KnowledgeGraph()
        self.dialogue_engine = DialogueEngine()
        self.goal_engine = GoalEngine()
        self.scene_engine = SceneEngine()
        self.automation_engine = AutomationEngine()
        self.habit_learner = HabitLearner()
        self.anomaly_detector = AnomalyDetector()
        self.energy_optimizer = EnergyOptimizer()
        self.predictive_service = PredictiveService()
        self.ir_controller = IRController()
        self.ir_learner = IRLearner()
        self.ir_mapping = IRMappingRegistry()
        self.virtual_device_manager = VirtualDeviceManager()
        self.scene_replayer = SceneReplayer()
        self.test_framework = TestFramework()

        self._setup_integrations()

    def _setup_integrations(self) -> None:
        logger.info("Setting up enhanced Butler Core integrations")

        self.dialogue_engine.context_manager = ContextManager()

        self.scene_replayer.set_device_executor(
            lambda device_id, action, params: self.virtual_device_manager.execute_command(device_id, action, params)
        )

        self.automation_engine.set_action_executor(
            lambda action: self._execute_automation_action(action)
        )

    def _execute_automation_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("action_type")
        params = action.get("params", {})

        if action_type in ["turn_on", "turn_off", "set_brightness", "set_temperature", "open", "close"]:
            device_id = params.get("target")
            if device_id:
                return self.virtual_device_manager.execute_command(device_id, action_type, params)
        
        return {
            "success": False,
            "message": f"Unsupported action type: {action_type}",
        }

    def process_user_input(
        self,
        user_input: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.info(f"Processing user input: {user_input}")

        turn = self.dialogue_engine.process(user_input, user_id)
        
        if turn.actions:
            for action in turn.actions:
                self._execute_action(action)
        
        return {
            "response": turn.response,
            "actions": turn.actions,
            "intent": turn.user_intent.to_dict(),
            "resolved_references": turn.resolved_references,
        }

    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action.get("action_type")
        params = action.get("params", {})

        if action_type == "turn_on_device":
            device_id = params.get("target")
            return self.virtual_device_manager.execute_command(device_id, "turn_on", params)
        
        elif action_type == "turn_off_device":
            device_id = params.get("target")
            return self.virtual_device_manager.execute_command(device_id, "turn_off", params)
        
        elif action_type == "activate_scene":
            scene_id = params.get("scene_id")
            return self.scene_engine.activate_scene(
                scene_id,
                lambda action: self._execute_action(action)
            )
        
        elif action_type == "execute_goal":
            goal = self.goal_engine.parse_goal(action.get("text", ""))
            if goal:
                return self.goal_engine.execute_goal(
                    goal,
                    lambda action, ctx: self._execute_action(action)
                )
        
        return {
            "success": False,
            "message": f"Unknown action type: {action_type}",
        }

    def run_tests(self) -> Dict[str, Any]:
        logger.info("Running Butler Core tests")

        test_context = {
            "virtual_device_manager": self.virtual_device_manager,
            "scene_engine": self.scene_engine,
            "goal_engine": self.goal_engine,
            "anomaly_detector": self.anomaly_detector,
            "automation_engine": self.automation_engine,
            "energy_optimizer": self.energy_optimizer,
        }

        return self.test_framework.run_all_tests(test_context)

    def get_system_status(self) -> Dict[str, Any]:
        return {
            "knowledge_graph": self.knowledge_graph.get_scene_state(),
            "dialogue_engine": self.dialogue_engine.to_dict(),
            "goal_engine": self.goal_engine.to_dict(),
            "scene_engine": self.scene_engine.to_dict(),
            "automation_engine": self.automation_engine.to_dict(),
            "habit_learner": self.habit_learner.to_dict(),
            "anomaly_detector": self.anomaly_detector.to_dict(),
            "energy_optimizer": self.energy_optimizer.to_dict(),
            "predictive_service": self.predictive_service.to_dict(),
            "ir_controller": self.ir_controller.to_dict(),
            "virtual_device_manager": self.virtual_device_manager.to_dict(),
            "test_framework": self.test_framework.get_statistics(),
        }

    def start(self) -> None:
        logger.info("Starting Enhanced Butler Core")
        logger.info("All systems initialized and ready")

    def stop(self) -> None:
        logger.info("Stopping Enhanced Butler Core")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    butler = EnhancedButlerCore()
    butler.start()

    try:
        logger.info("Butler Core running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        butler.stop()


if __name__ == "__main__":
    main()
