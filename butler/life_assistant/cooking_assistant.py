from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class Difficulty(Enum):
    EASY = 1
    MEDIUM = 2
    HARD = 3


@dataclass
class RecipeIngredient:
    name: str
    quantity: str
    unit: str = ""
    optional: bool = False


@dataclass
class RecipeStep:
    step_number: int
    instruction: str
    duration_minutes: int = 0
    temperature: Optional[str] = None


@dataclass
class Recipe:
    id: str
    name: str
    description: str
    ingredients: List[RecipeIngredient]
    steps: List[RecipeStep]
    difficulty: int
    prep_time_minutes: int
    cook_time_minutes: int
    servings: int
    tags: List[str] = field(default_factory=list)
    created_at: int = 0

    def __post_init__(self) -> None:
        if self.created_at == 0:
            from ..core.utils import utc_ts
            self.created_at = utc_ts()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Recipe":
        ingredients = [
            RecipeIngredient(**ing) if isinstance(ing, dict) else ing
            for ing in data.get("ingredients", [])
        ]
        steps = [
            RecipeStep(**step) if isinstance(step, dict) else step
            for step in data.get("steps", [])
        ]
        data["ingredients"] = ingredients
        data["steps"] = steps
        return cls(**data)


@dataclass
class CookingSession:
    id: str
    recipe_id: str
    current_step: int
    started_at: int
    completed_at: Optional[int] = None
    notes: str = ""
    paused: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CookingSession":
        return cls(**data)


class CookingAssistant:
    def __init__(self, storage_path: Optional[str] = None) -> None:
        self.storage_path = storage_path or "/app/butler/data/cooking.json"
        self.recipes: Dict[str, Recipe] = {}
        self.sessions: Dict[str, CookingSession] = {}
        self._load_from_disk()
        self._init_default_recipes()

    def _load_from_disk(self) -> None:
        try:
            path = Path(self.storage_path)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    recipes_data = data.get("recipes", {})
                    for recipe_id, recipe_data in recipes_data.items():
                        self.recipes[recipe_id] = Recipe.from_dict(recipe_data)
                    sessions_data = data.get("sessions", {})
                    for session_id, session_data in sessions_data.items():
                        self.sessions[session_id] = CookingSession.from_dict(session_data)
                logger.info(f"Loaded {len(self.recipes)} recipes, {len(self.sessions)} sessions")
        except Exception as e:
            logger.error(f"Failed to load cooking data: {e}")

    def _save_to_disk(self) -> None:
        try:
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                data = {
                    "recipes": {
                        recipe_id: recipe.to_dict()
                        for recipe_id, recipe in self.recipes.items()
                    },
                    "sessions": {
                        session_id: session.to_dict()
                        for session_id, session in self.sessions.items()
                    }
                }
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save cooking data: {e}")

    def _init_default_recipes(self) -> None:
        if not self.recipes:
            self._add_default_recipe(
                "番茄炒蛋",
                "简单经典的家常菜",
                [
                    RecipeIngredient("鸡蛋", 3, "个"),
                    RecipeIngredient("番茄", 2, "个"),
                    RecipeIngredient("盐", 1, "小勺"),
                    RecipeIngredient("油", 2, "大勺"),
                    RecipeIngredient("葱", 1, "根", True),
                ],
                [
                    RecipeStep(1, "将鸡蛋打散，加入少许盐", 2),
                    RecipeStep(2, "番茄切块，葱切花", 3),
                    RecipeStep(3, "热锅下油，炒熟鸡蛋盛出", 5, "中火"),
                    RecipeStep(4, "下番茄块炒出汁水", 3),
                    RecipeStep(5, "倒入鸡蛋翻炒均匀", 2),
                    RecipeStep(6, "撒上葱花即可出锅", 1),
                ],
                Difficulty.EASY.value,
                10,
                10,
                2,
                ["家常", "简单", "快手菜"],
            )

    def _add_default_recipe(
        self,
        name: str,
        description: str,
        ingredients: List[RecipeIngredient],
        steps: List[RecipeStep],
        difficulty: int,
        prep_time: int,
        cook_time: int,
        servings: int,
        tags: List[str],
    ) -> None:
        from ..core.utils import new_uuid
        recipe_id = new_uuid()
        recipe = Recipe(
            id=recipe_id,
            name=name,
            description=description,
            ingredients=ingredients,
            steps=steps,
            difficulty=difficulty,
            prep_time_minutes=prep_time,
            cook_time_minutes=cook_time,
            servings=servings,
            tags=tags,
        )
        self.recipes[recipe_id] = recipe
        self._save_to_disk()
        logger.info(f"Added default recipe: {name}")

    def add_recipe(
        self,
        name: str,
        description: str,
        ingredients: List[Dict[str, Any]],
        steps: List[Dict[str, Any]],
        difficulty: int,
        prep_time_minutes: int,
        cook_time_minutes: int,
        servings: int,
        tags: Optional[List[str]] = None,
    ) -> Recipe:
        from ..core.utils import new_uuid
        recipe_id = new_uuid()
        ingredient_objs = [RecipeIngredient(**ing) for ing in ingredients]
        step_objs = [RecipeStep(**step) for step in steps]
        recipe = Recipe(
            id=recipe_id,
            name=name,
            description=description,
            ingredients=ingredient_objs,
            steps=step_objs,
            difficulty=difficulty,
            prep_time_minutes=prep_time_minutes,
            cook_time_minutes=cook_time_minutes,
            servings=servings,
            tags=tags or [],
        )
        self.recipes[recipe_id] = recipe
        self._save_to_disk()
        logger.info(f"Added recipe: {name}")
        return recipe

    def get_recipe(self, recipe_id: str) -> Optional[Recipe]:
        return self.recipes.get(recipe_id)

    def list_recipes(
        self,
        difficulty: Optional[int] = None,
        tags: Optional[List[str]] = None,
        max_time_minutes: Optional[int] = None,
    ) -> List[Recipe]:
        recipes = list(self.recipes.values())
        if difficulty is not None:
            recipes = [r for r in recipes if r.difficulty == difficulty]
        if tags:
            recipes = [r for r in recipes if any(tag in r.tags for tag in tags)]
        if max_time_minutes is not None:
            recipes = [r for r in recipes if (r.prep_time_minutes + r.cook_time_minutes) <= max_time_minutes]
        recipes.sort(key=lambda r: r.created_at, reverse=True)
        return recipes

    def search_recipes(self, query: str) -> List[Recipe]:
        query_lower = query.lower()
        recipes = [
            recipe for recipe in self.recipes.values()
            if query_lower in recipe.name.lower() or
               query_lower in recipe.description.lower() or
               any(query_lower in tag.lower() for tag in recipe.tags) or
               any(query_lower in ing.name.lower() for ing in recipe.ingredients)
        ]
        recipes.sort(key=lambda r: r.created_at, reverse=True)
        return recipes

    def get_recipe_suggestions(self, available_ingredients: List[str]) -> List[Recipe]:
        available_lower = [ing.lower() for ing in available_ingredients]
        suggestions = []
        for recipe in self.recipes.values():
            required_ingredients = [
                ing.name.lower() for ing in recipe.ingredients
                if not ing.optional
            ]
            available_count = sum(1 for ing in required_ingredients if ing in available_lower)
            match_ratio = available_count / len(required_ingredients) if required_ingredients else 0
            if match_ratio >= 0.5:
                suggestions.append((recipe, match_ratio))
        suggestions.sort(key=lambda x: (-x[1], x[0].difficulty))
        return [recipe for recipe, _ in suggestions]

    def start_cooking(self, recipe_id: str) -> Optional[CookingSession]:
        if recipe_id not in self.recipes:
            return None
        from ..core.utils import new_uuid, utc_ts
        session_id = new_uuid()
        session = CookingSession(
            id=session_id,
            recipe_id=recipe_id,
            current_step=0,
            started_at=utc_ts(),
        )
        self.sessions[session_id] = session
        self._save_to_disk()
        logger.info(f"Started cooking session for recipe: {self.recipes[recipe_id].name}")
        return session

    def get_current_step(self, session_id: str) -> Optional[RecipeStep]:
        if session_id not in self.sessions:
            return None
        session = self.sessions[session_id]
        recipe = self.recipes.get(session.recipe_id)
        if not recipe:
            return None
        if session.current_step < len(recipe.steps):
            return recipe.steps[session.current_step]
        return None

    def next_step(self, session_id: str) -> Optional[RecipeStep]:
        if session_id not in self.sessions:
            return None
        session = self.sessions[session_id]
        session.current_step += 1
        self._save_to_disk()
        return self.get_current_step(session_id)

    def previous_step(self, session_id: str) -> Optional[RecipeStep]:
        if session_id not in self.sessions:
            return None
        session = self.sessions[session_id]
        session.current_step = max(0, session.current_step - 1)
        self._save_to_disk()
        return self.get_current_step(session_id)

    def complete_cooking(self, session_id: str, notes: str = "") -> Optional[CookingSession]:
        if session_id not in self.sessions:
            return None
        from ..core.utils import utc_ts
        session = self.sessions[session_id]
        session.completed_at = utc_ts()
        session.notes = notes
        self._save_to_disk()
        logger.info(f"Completed cooking session: {session_id}")
        return session

    def pause_cooking(self, session_id: str) -> Optional[CookingSession]:
        if session_id not in self.sessions:
            return None
        self.sessions[session_id].paused = True
        self._save_to_disk()
        return self.sessions[session_id]

    def resume_cooking(self, session_id: str) -> Optional[CookingSession]:
        if session_id not in self.sessions:
            return None
        self.sessions[session_id].paused = False
        self._save_to_disk()
        return self.sessions[session_id]

    def get_active_sessions(self) -> List[CookingSession]:
        sessions = [
            session for session in self.sessions.values()
            if session.completed_at is None
        ]
        sessions.sort(key=lambda s: s.started_at, reverse=True)
        return sessions

    def delete_recipe(self, recipe_id: str) -> bool:
        if recipe_id in self.recipes:
            name = self.recipes[recipe_id].name
            del self.recipes[recipe_id]
            self._save_to_disk()
            logger.info(f"Deleted recipe: {name}")
            return True
        return False

    def delete_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save_to_disk()
            logger.info(f"Deleted cooking session: {session_id}")
            return True
        return False
