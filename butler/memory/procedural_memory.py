from __future__ import annotations
import asyncio
import logging
import json
import os
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass, field

from .long_term_memory import LongTermMemory
from .memory_types import MemoryItem, MemoryType

logger = logging.getLogger(__name__)


@dataclass
class ProcedureStep:
    step_id: str
    step_type: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    optional: bool = False
    timeout: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_type": self.step_type,
            "description": self.description,
            "parameters": self.parameters,
            "optional": self.optional,
            "timeout": self.timeout
        }


@dataclass
class Procedure:
    procedure_id: str
    name: str
    description: str
    steps: List[Dict[str, Any]]
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    success_rate: float = 1.0
    execution_count: int = 0
    last_executed: Optional[datetime] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "procedure_id": self.procedure_id,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "preconditions": self.preconditions,
            "postconditions": self.postconditions,
            "parameters": self.parameters,
            "success_rate": self.success_rate,
            "execution_count": self.execution_count,
            "last_executed": self.last_executed.isoformat() if self.last_executed else None,
            "created_at": self.created_at.isoformat()
        }

@dataclass
class Skill:
    skill_id: str
    name: str
    skill_type: str
    proficiency: float
    practice_count: int = 0
    last_practiced: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "skill_type": self.skill_type,
            "proficiency": self.proficiency,
            "practice_count": self.practice_count,
            "last_practiced": self.last_practiced.isoformat() if self.last_practiced else None,
            "metadata": self.metadata
        }

class ProceduralMemory(LongTermMemory):
    def __init__(self, storage_path: Optional[str] = None):
        super().__init__(storage_path)
        self._procedures: Dict[str, Procedure] = {}
        self._skills: Dict[str, Skill] = {}
        self._procedures_by_type: Dict[str, List[str]] = {}
        self._skill_types: Dict[str, List[str]] = {}

    async def initialize(self) -> bool:
        if not await super().initialize():
            return False

        procedures_file = os.path.join(self._storage_path, "procedures.json")
        if os.path.exists(procedures_file):
            try:
                with open(procedures_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for proc_data in data.get("procedures", []):
                        procedure = Procedure(
                            procedure_id=proc_data["procedure_id"],
                            name=proc_data["name"],
                            description=proc_data["description"],
                            steps=proc_data["steps"],
                            preconditions=proc_data.get("preconditions", []),
                            postconditions=proc_data.get("postconditions", []),
                            parameters=proc_data.get("parameters", {}),
                            success_rate=proc_data.get("success_rate", 1.0),
                            execution_count=proc_data.get("execution_count", 0),
                            last_executed=datetime.fromisoformat(proc_data["last_executed"]) if proc_data.get("last_executed") else None,
                            created_at=datetime.fromisoformat(proc_data["created_at"])
                        )
                        self._procedures[procedure.procedure_id] = procedure
                        self._index_procedure(procedure)

                logger.info(f"Loaded {len(self._procedures)} procedures")

            except Exception as e:
                logger.error(f"Failed to load procedures: {e}")

        skills_file = os.path.join(self._storage_path, "skills.json")
        if os.path.exists(skills_file):
            try:
                with open(skills_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for skill_data in data.get("skills", []):
                        skill = Skill(
                            skill_id=skill_data["skill_id"],
                            name=skill_data["name"],
                            skill_type=skill_data["skill_type"],
                            proficiency=skill_data["proficiency"],
                            practice_count=skill_data.get("practice_count", 0),
                            last_practiced=datetime.fromisoformat(skill_data["last_practiced"]) if skill_data.get("last_practiced") else None,
                            metadata=skill_data.get("metadata", {})
                        )
                        self._skills[skill.skill_id] = skill
                        self._index_skill(skill)

                logger.info(f"Loaded {len(self._skills)} skills")

            except Exception as e:
                logger.error(f"Failed to load skills: {e}")

        return True

    async def add_procedure(
        self,
        name: str,
        description: str,
        steps: List[Dict[str, Any]],
        preconditions: Optional[List[str]] = None,
        postconditions: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None
    ) -> str:
        import uuid

        procedure_id = str(uuid.uuid4())

        procedure = Procedure(
            procedure_id=procedure_id,
            name=name,
            description=description,
            steps=steps,
            preconditions=preconditions or [],
            postconditions=postconditions or [],
            parameters=parameters or {}
        )

        self._procedures[procedure_id] = procedure
        self._index_procedure(procedure)
        await self._save_procedures()

        return procedure_id

    def _index_procedure(self, procedure: Procedure):
        for step in procedure.steps:
            step_type = step.get("type", "general")
            if step_type not in self._procedures_by_type:
                self._procedures_by_type[step_type] = []
            self._procedures_by_type[step_type].append(procedure.procedure_id)

    async def get_procedure(self, procedure_id: str) -> Optional[Procedure]:
        return self._procedures.get(procedure_id)

    async def get_procedure_by_name(self, name: str) -> Optional[Procedure]:
        for procedure in self._procedures.values():
            if procedure.name.lower() == name.lower():
                return procedure
        return None

    async def get_procedures_by_type(self, step_type: str) -> List[Procedure]:
        procedure_ids = self._procedures_by_type.get(step_type, [])
        return [self._procedures[pid] for pid in procedure_ids if pid in self._procedures]

    async def find_procedures_for_goal(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Procedure]:
        goal_lower = goal.lower()
        results = []

        for procedure in self._procedures.values():
            if goal_lower in procedure.name.lower() or goal_lower in procedure.description.lower():
                results.append(procedure)

        results.sort(key=lambda p: p.success_rate, reverse=True)
        return results

    async def execute_procedure(
        self,
        procedure_id: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        procedure = self._procedures.get(procedure_id)
        if not procedure:
            return {
                "success": False,
                "error": f"Procedure {procedure_id} not found"
            }

        execution_results = []

        for i, step in enumerate(procedure.steps):
            step_result = await self._execute_step(step, parameters or {})
            execution_results.append({
                "step_number": i + 1,
                "step_type": step.get("type"),
                "result": step_result
            })

            if not step_result.get("success", False):
                procedure.execution_count += 1
                procedure.success_rate = procedure.success_rate * 0.9
                await self._save_procedures()

                return {
                    "success": False,
                    "procedure_id": procedure_id,
                    "failed_at_step": i + 1,
                    "results": execution_results
                }

        procedure.execution_count += 1
        procedure.success_rate = min(1.0, procedure.success_rate * 0.95 + 0.05)
        procedure.last_executed = datetime.now()
        await self._save_procedures()

        return {
            "success": True,
            "procedure_id": procedure_id,
            "results": execution_results
        }

    async def _execute_step(
        self,
        step: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        step_type = step.get("type")

        if step_type == "action":
            return await self._execute_action_step(step, parameters)
        elif step_type == "condition":
            return await self._execute_condition_step(step, parameters)
        elif step_type == "loop":
            return await self._execute_loop_step(step, parameters)
        elif step_type == "parallel":
            return await self._execute_parallel_step(step, parameters)
        else:
            return {
                "success": True,
                "step_type": step_type,
                "message": f"Executed {step_type} step"
            }

    async def _execute_action_step(
        self,
        step: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        action = step.get("action")
        action_params = {**parameters, **step.get("parameters", {})}

        return {
            "success": True,
            "action": action,
            "parameters": action_params
        }

    async def _execute_condition_step(
        self,
        step: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        condition = step.get("condition")

        if_true = step.get("if_true", [])
        if_false = step.get("if_false", [])

        condition_met = await self._evaluate_condition(condition, parameters)

        steps_to_execute = if_true if condition_met else if_false

        for sub_step in steps_to_execute:
            await self._execute_step(sub_step, parameters)

        return {
            "success": True,
            "condition_met": condition_met
        }

    async def _evaluate_condition(self, condition: str, parameters: Dict[str, Any]) -> bool:
        return True

    async def _execute_loop_step(
        self,
        step: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        iterations = step.get("iterations", 1)
        loop_steps = step.get("steps", [])

        for i in range(iterations):
            loop_params = {**parameters, "iteration": i}
            for sub_step in loop_steps:
                await self._execute_step(sub_step, loop_params)

        return {
            "success": True,
            "iterations": iterations
        }

    async def _execute_parallel_step(
        self,
        step: Dict[str, Any],
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        parallel_steps = step.get("steps", [])

        tasks = []
        for sub_step in parallel_steps:
            tasks.append(self._execute_step(sub_step, parameters))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "success": all(isinstance(r, dict) and r.get("success", False) for r in results if not isinstance(r, Exception)),
            "results": results
        }

    async def add_skill(
        self,
        name: str,
        skill_type: str,
        initial_proficiency: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        import uuid

        skill_id = str(uuid.uuid4())

        skill = Skill(
            skill_id=skill_id,
            name=name,
            skill_type=skill_type,
            proficiency=initial_proficiency,
            metadata=metadata or {}
        )

        self._skills[skill_id] = skill
        self._index_skill(skill)
        await self._save_skills()

        return skill_id

    def _index_skill(self, skill: Skill):
        if skill.skill_type not in self._skill_types:
            self._skill_types[skill.skill_type] = []
        self._skill_types[skill.skill_type].append(skill.skill_id)

    async def get_skill(self, skill_id: str) -> Optional[Skill]:
        return self._skills.get(skill_id)

    async def get_skills_by_type(self, skill_type: str) -> List[Skill]:
        skill_ids = self._skill_types.get(skill_type, [])
        return [self._skills[sid] for sid in skill_ids if sid in self._skills]

    async def practice_skill(
        self,
        skill_id: str,
        performance_score: float
    ) -> bool:
        skill = self._skills.get(skill_id)
        if not skill:
            return False

        skill.practice_count += 1
        skill.last_practiced = datetime.now()

        learning_rate = 0.1
        skill.proficiency = min(1.0, skill.proficiency + (performance_score - skill.proficiency) * learning_rate)

        await self._save_skills()
        return True

    async def add(self, item: MemoryItem):
        await super().add(item)

    async def query(self, query: Any) -> List[Any]:
        return await super().query(query)

    async def _save_procedures(self):
        try:
            procedures_file = os.path.join(self._storage_path, "procedures.json")
            data = {
                "procedures": [p.to_dict() for p in self._procedures.values()],
                "saved_at": datetime.now().isoformat()
            }

            with open(procedures_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to save procedures: {e}")

    async def _save_skills(self):
        try:
            skills_file = os.path.join(self._storage_path, "skills.json")
            data = {
                "skills": [s.to_dict() for s in self._skills.values()],
                "saved_at": datetime.now().isoformat()
            }

            with open(skills_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to save skills: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        base_stats = super().get_statistics()
        base_stats.update({
            "total_procedures": len(self._procedures),
            "total_skills": len(self._skills),
            "average_success_rate": sum(p.success_rate for p in self._procedures.values()) / len(self._procedures) if self._procedures else 0,
            "average_proficiency": sum(s.proficiency for s in self._skills.values()) / len(self._skills) if self._skills else 0,
            "procedure_types": len(self._procedures_by_type),
            "skill_types": len(self._skill_types)
        })
        return base_stats
