import pytest
import asyncio
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from butler.goal_engine.goal_engine import (
    Goal, GoalEngine, GoalConfig, GoalState,
    GoalStatus, GoalStatistics
)
from butler.goal_engine.composite_goal import (
    CompositeGoal, CompositeGoalExecutor,
    SubGoalStrategy, SubGoal
)
from butler.goal_engine.goal_conflict_resolver import (
    GoalConflictResolver, GoalConflict, ConflictRule,
    ConflictResolutionStrategy, ConflictResolution
)
from butler.goal_engine.goal_priority_manager import (
    GoalPriorityManager, PriorityFactor, PriorityWeight,
    PriorityRule
)
from butler.goal_engine.adaptive_goal import (
    AdaptiveGoalManager, AdaptationEvent, AdaptationRule,
    AdaptationAction, AdaptationResult
)


class TestGoal:
    def test_goal_creation(self):
        goal = Goal(
            goal_id="goal_001",
            name="Test Goal",
            description="A test goal",
            priority=5
        )
        
        assert goal.goal_id == "goal_001"
        assert goal.name == "Test Goal"
        assert goal.priority == 5

    def test_goal_state(self):
        goal = Goal(
            goal_id="goal_001",
            name="Test Goal"
        )
        
        assert goal.state == GoalState.PENDING
        goal.state = GoalState.IN_PROGRESS
        assert goal.state == GoalState.IN_PROGRESS

    def test_goal_status(self):
        goal = Goal(
            goal_id="goal_001",
            name="Test Goal"
        )
        
        assert goal.status == GoalStatus.ACTIVE
        goal.status = GoalStatus.PAUSED
        assert goal.status == GoalStatus.PAUSED


class TestCompositeGoal:
    def test_composite_goal_creation(self):
        sub_goal1 = SubGoal(
            goal_id="sub_001",
            name="Sub Goal 1",
            priority=5
        )
        
        sub_goal2 = SubGoal(
            goal_id="sub_002",
            name="Sub Goal 2",
            priority=3
        )
        
        composite = CompositeGoal(
            goal_id="comp_001",
            name="Composite Goal",
            execution_strategy=SubGoalStrategy.SEQUENTIAL,
            sub_goals=[sub_goal1, sub_goal2]
        )
        
        assert composite.goal_id == "comp_001"
        assert len(composite.sub_goals) == 2
        assert composite.execution_strategy == SubGoalStrategy.SEQUENTIAL

    def test_composite_goal_add_dependency(self):
        sub_goal1 = SubGoal(goal_id="sub_001", name="Sub Goal 1")
        sub_goal2 = SubGoal(goal_id="sub_002", name="Sub Goal 2")
        
        composite = CompositeGoal(
            goal_id="comp_001",
            name="Composite Goal",
            sub_goals=[sub_goal1, sub_goal2]
        )
        
        composite.add_dependency("sub_001", "sub_002")
        
        assert "sub_002" in composite.get_dependencies("sub_001")


@pytest.mark.asyncio
class TestCompositeGoalExecutor:
    @pytest.fixture
    def executor(self):
        return CompositeGoalExecutor()

    async def test_sequential_execution(self, executor):
        sub_goal1 = SubGoal(goal_id="sub_001", name="Sub Goal 1")
        sub_goal2 = SubGoal(goal_id="sub_002", name="Sub Goal 2")
        
        composite = CompositeGoal(
            goal_id="comp_001",
            name="Composite Goal",
            execution_strategy=SubGoalStrategy.SEQUENTIAL,
            sub_goals=[sub_goal1, sub_goal2]
        )
        
        result = await executor.execute_composite_goal(composite)
        
        assert result["success"] is True
        assert result["executed_sub_goals"] == 2

    async def test_parallel_execution(self, executor):
        sub_goal1 = SubGoal(goal_id="sub_001", name="Sub Goal 1")
        sub_goal2 = SubGoal(goal_id="sub_002", name="Sub Goal 2")
        
        composite = CompositeGoal(
            goal_id="comp_001",
            name="Composite Goal",
            execution_strategy=SubGoalStrategy.PARALLEL,
            sub_goals=[sub_goal1, sub_goal2]
        )
        
        result = await executor.execute_composite_goal(composite)
        
        assert result["success"] is True


class TestGoalConflict:
    def test_conflict_creation(self):
        conflict = GoalConflict(
            conflict_id="conf_001",
            goal_a_id="goal_001",
            goal_b_id="goal_002",
            conflict_type="resource",
            description="Both goals require the same resource"
        )
        
        assert conflict.conflict_id == "conf_001"
        assert conflict.goal_a_id == "goal_001"
        assert conflict.goal_b_id == "goal_002"
        assert conflict.conflict_type == "resource"


@pytest.mark.asyncio
class TestGoalConflictResolver:
    @pytest.fixture
    def resolver(self):
        return GoalConflictResolver()

    async def test_priority_based_resolution(self, resolver):
        conflict = GoalConflict(
            conflict_id="conf_001",
            goal_a_id="goal_001",
            goal_b_id="goal_002",
            conflict_type="resource"
        )
        
        rule = ConflictRule(
            conflict_type="resource",
            resolution_strategy=ConflictResolutionStrategy.PRIORITY_BASED
        )
        
        resolver.add_rule(rule)
        
        goal_a = {"goal_id": "goal_001", "priority": 5}
        goal_b = {"goal_id": "goal_002", "priority": 3}
        
        resolution = await resolver.resolve_conflict(conflict, goal_a, goal_b)
        
        assert resolution.strategy == ConflictResolutionStrategy.PRIORITY_BASED
        assert resolution.winner_goal_id == "goal_001"

    async def test_time_based_resolution(self, resolver):
        conflict = GoalConflict(
            conflict_id="conf_001",
            goal_a_id="goal_001",
            goal_b_id="goal_002",
            conflict_type="resource"
        )
        
        rule = ConflictRule(
            conflict_type="resource",
            resolution_strategy=ConflictResolutionStrategy.TIME_BASED
        )
        
        resolver.add_rule(rule)
        
        goal_a = {
            "goal_id": "goal_001",
            "priority": 5,
            "deadline": datetime.now() + timedelta(minutes=10)
        }
        goal_b = {
            "goal_id": "goal_002",
            "priority": 3,
            "deadline": datetime.now() + timedelta(minutes=5)
        }
        
        resolution = await resolver.resolve_conflict(conflict, goal_a, goal_b)
        
        assert resolution.strategy == ConflictResolutionStrategy.TIME_BASED


class TestGoalPriorityManager:
    def test_priority_manager_creation(self):
        manager = GoalPriorityManager()
        
        assert manager is not None

    def test_calculate_priority(self):
        manager = GoalPriorityManager()
        
        goal = {
            "goal_id": "goal_001",
            "base_priority": 5,
            "user_importance": 3,
            "urgency": 2,
            "time_sensitivity": 1
        }
        
        priority = manager.calculate_priority(goal)
        
        assert priority >= 0

    def test_add_priority_rule(self):
        manager = GoalPriorityManager()
        
        rule = PriorityRule(
            rule_id="rule_001",
            condition=lambda goal: goal.get("goal_type") == "safety",
            adjustment=10
        )
        
        manager.add_rule(rule)
        
        assert "rule_001" in manager.get_rules()

    def test_set_factor_weight(self):
        manager = GoalPriorityManager()
        
        weight = PriorityWeight(
            factor=PriorityFactor.USER_IMPORTANCE,
            weight=2.0,
            enabled=True
        )
        
        manager.set_factor_weight(weight)
        
        retrieved = manager.get_factor_weight(PriorityFactor.USER_IMPORTANCE)
        assert retrieved.weight == 2.0


class TestAdaptiveGoalManager:
    @pytest.fixture
    def manager(self):
        return AdaptiveGoalManager()

    def test_manager_creation(self, manager):
        assert manager is not None

    def test_add_adaptation_rule(self, manager):
        rule = AdaptationRule(
            rule_id="rule_001",
            trigger="failure",
            condition=lambda event: event.context.get("retries", 0) < 3,
            actions=[AdaptationAction.RETRY]
        )
        
        manager.add_rule(rule)
        
        assert "rule_001" in manager.get_rules()

    @pytest.mark.asyncio
    async def test_adapt_goal_on_failure(self, manager):
        rule = AdaptationRule(
            rule_id="rule_001",
            trigger="failure",
            condition=lambda event: True,
            actions=[AdaptationAction.RETRY]
        )
        
        manager.add_rule(rule)
        
        event = AdaptationEvent(
            event_id="evt_001",
            trigger="failure",
            goal_id="goal_001",
            context={"error": "Test error"}
        )
        
        goal = {
            "goal_id": "goal_001",
            "name": "Test Goal",
            "retry_count": 0
        }
        
        result = await manager.adapt_goal(event, goal)
        
        assert result is not None
        assert result.actions_taken is not None


@pytest.mark.asyncio
class TestGoalEngine:
    @pytest.fixture
    def engine(self):
        return GoalEngine()

    async def test_engine_initialization(self, engine):
        await engine.initialize()
        
        assert engine.is_initialized() is True

    async def test_add_goal(self, engine):
        await engine.initialize()
        
        goal = Goal(
            goal_id="goal_001",
            name="Test Goal",
            priority=5
        )
        
        await engine.add_goal(goal)
        
        retrieved = engine.get_goal("goal_001")
        assert retrieved is not None

    async def test_remove_goal(self, engine):
        await engine.initialize()
        
        goal = Goal(
            goal_id="goal_001",
            name="Test Goal"
        )
        
        await engine.add_goal(goal)
        await engine.remove_goal("goal_001")
        
        retrieved = engine.get_goal("goal_001")
        assert retrieved is None

    async def test_get_all_goals(self, engine):
        await engine.initialize()
        
        goal1 = Goal(goal_id="goal_001", name="Goal 1")
        goal2 = Goal(goal_id="goal_002", name="Goal 2")
        
        await engine.add_goal(goal1)
        await engine.add_goal(goal2)
        
        all_goals = engine.get_all_goals()
        assert len(all_goals) == 2

    async def test_execute_goal(self, engine):
        await engine.initialize()
        
        goal = Goal(
            goal_id="goal_001",
            name="Test Goal",
            priority=5
        )
        
        await engine.add_goal(goal)
        
        result = await engine.execute_goal(goal)
        
        assert result is not None
        assert "success" in result or "error" in result

    async def test_get_goal_statistics(self, engine):
        await engine.initialize()
        
        goal = Goal(
            goal_id="goal_001",
            name="Test Goal"
        )
        
        await engine.add_goal(goal)
        
        stats = engine.get_goal_statistics("goal_001")
        assert stats is not None

    async def test_pause_resume_goal(self, engine):
        await engine.initialize()
        
        goal = Goal(
            goal_id="goal_001",
            name="Test Goal"
        )
        
        await engine.add_goal(goal)
        await engine.pause_goal("goal_001")
        
        assert goal.status == GoalStatus.PAUSED
        
        await engine.resume_goal("goal_001")
        
        assert goal.status == GoalStatus.ACTIVE

    async def test_cancel_goal(self, engine):
        await engine.initialize()
        
        goal = Goal(
            goal_id="goal_001",
            name="Test Goal"
        )
        
        await engine.add_goal(goal)
        await engine.cancel_goal("goal_001")
        
        assert goal.status == GoalStatus.CANCELLED
