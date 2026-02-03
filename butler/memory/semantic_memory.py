from __future__ import annotations
import asyncio
import logging
import json
import os
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

from .long_term_memory import LongTermMemory
from .memory_types import MemoryItem, MemoryType

logger = logging.getLogger(__name__)


@dataclass
class Relation:
    relation_id: str
    source_id: str
    target_id: str
    relation_type: str
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation_type": self.relation_type,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class Concept:
    concept_id: str
    name: str
    category: str
    description: str
    properties: Dict[str, Any] = field(default_factory=dict)
    relations: List[Tuple[str, str, str]] = field(default_factory=list)
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "properties": self.properties,
            "relations": self.relations,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat()
        }

class SemanticMemory(LongTermMemory):
    def __init__(self, storage_path: Optional[str] = None):
        super().__init__(storage_path)
        self._concepts: Dict[str, Concept] = {}
        self._concepts_by_category: Dict[str, List[str]] = {}
        self._relations_index: Dict[str, List[Tuple[str, str]]] = {}

    async def initialize(self) -> bool:
        if not await super().initialize():
            return False

        concepts_file = os.path.join(self._storage_path, "concepts.json")
        if os.path.exists(concepts_file):
            try:
                with open(concepts_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for concept_data in data.get("concepts", []):
                        concept = Concept(
                            concept_id=concept_data["concept_id"],
                            name=concept_data["name"],
                            category=concept_data["category"],
                            description=concept_data["description"],
                            properties=concept_data.get("properties", {}),
                            relations=[
                                tuple(rel) if isinstance(rel, list) else rel
                                for rel in concept_data.get("relations", [])
                            ],
                            confidence=concept_data.get("confidence", 1.0),
                            created_at=datetime.fromisoformat(concept_data["created_at"]),
                            last_updated=datetime.fromisoformat(concept_data["last_updated"])
                        )
                        self._concepts[concept.concept_id] = concept
                        self._index_concept(concept)

                logger.info(f"Loaded {len(self._concepts)} concepts")

            except Exception as e:
                logger.error(f"Failed to load concepts: {e}")

        return True

    async def add_concept(
        self,
        name: str,
        category: str,
        description: str,
        properties: Optional[Dict[str, Any]] = None,
        relations: Optional[List[Tuple[str, str, str]]] = None
    ) -> str:
        import uuid

        concept_id = str(uuid.uuid4())

        concept = Concept(
            concept_id=concept_id,
            name=name,
            category=category,
            description=description,
            properties=properties or {},
            relations=relations or []
        )

        self._concepts[concept_id] = concept
        self._index_concept(concept)
        await self._save_concepts()

        return concept_id

    def _index_concept(self, concept: Concept):
        if concept.category not in self._concepts_by_category:
            self._concepts_by_category[concept.category] = []
        self._concepts_by_category[concept.category].append(concept.concept_id)

        for relation_type, target_id in [(r[0], r[1]) for r in concept.relations if len(r) >= 2]:
            if relation_type not in self._relations_index:
                self._relations_index[relation_type] = []
            self._relations_index[relation_type].append((concept.concept_id, target_id))

    async def get_concept(self, concept_id: str) -> Optional[Concept]:
        return self._concepts.get(concept_id)

    async def get_concept_by_name(self, name: str) -> Optional[Concept]:
        for concept in self._concepts.values():
            if concept.name.lower() == name.lower():
                return concept
        return None

    async def get_concepts_by_category(self, category: str) -> List[Concept]:
        concept_ids = self._concepts_by_category.get(category, [])
        return [self._concepts[cid] for cid in concept_ids if cid in self._concepts]

    async def search_concepts(
        self,
        keywords: List[str],
        category: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[Concept]:
        results = []

        for concept in self._concepts.values():
            if category and concept.category != category:
                continue

            if concept.confidence < min_confidence:
                continue

            concept_text = f"{concept.name} {concept.description} {' '.join(concept.properties.values())}".lower()

            if any(kw.lower() in concept_text for kw in keywords):
                results.append(concept)

        results.sort(key=lambda c: c.confidence, reverse=True)
        return results

    async def get_related_concepts(
        self,
        concept_id: str,
        relation_type: Optional[str] = None,
        max_depth: int = 1
    ) -> List[Concept]:
        related = []
        visited = set()
        queue = [(concept_id, 0)]

        while queue:
            current_id, depth = queue.pop(0)

            if depth > max_depth or current_id in visited:
                continue

            visited.add(current_id)

            concept = self._concepts.get(current_id)
            if not concept:
                continue

            for relation in concept.relations:
                if len(relation) >= 2:
                    rel_type, target_id = relation[0], relation[1]

                    if relation_type and relation_type != rel_type:
                        continue

                    if target_id in self._concepts and target_id not in visited:
                        related.append(self._concepts[target_id])
                        queue.append((target_id, depth + 1))

        return related

    async def update_concept(
        self,
        concept_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
        relations: Optional[List[Tuple[str, str, str]]] = None
    ) -> bool:
        concept = self._concepts.get(concept_id)
        if not concept:
            return False

        if name is not None:
            concept.name = name
        if description is not None:
            concept.description = description
        if properties is not None:
            concept.properties.update(properties)
        if relations is not None:
            concept.relations = relations

        concept.last_updated = datetime.now()
        await self._save_concepts()

        return True

    async def delete_concept(self, concept_id: str) -> bool:
        if concept_id not in self._concepts:
            return False

        concept = self._concepts[concept_id]

        if concept.category in self._concepts_by_category:
            self._concepts_by_category[concept.category].remove(concept_id)

        for relation_type, relations in self._relations_index.items():
            self._relations_index[relation_type] = [
                (src, tgt) for src, tgt in relations
                if src != concept_id and tgt != concept_id
            ]

        del self._concepts[concept_id]
        await self._save_concepts()

        return True

    async def add_relation(
        self,
        source_id: str,
        relation_type: str,
        target_id: str
    ) -> bool:
        source = self._concepts.get(source_id)
        target = self._concepts.get(target_id)

        if not source or not target:
            return False

        relation = (relation_type, target_id)
        if relation not in source.relations:
            source.relations.append(relation)
            source.last_updated = datetime.now()

        if relation_type not in self._relations_index:
            self._relations_index[relation_type] = []
        if (source_id, target_id) not in self._relations_index[relation_type]:
            self._relations_index[relation_type].append((source_id, target_id))

        await self._save_concepts()
        return True

    async def add(self, item: MemoryItem):
        await super().add(item)

    async def query(self, query: Any) -> List[Any]:
        return await super().query(query)

    async def _save_concepts(self):
        try:
            concepts_file = os.path.join(self._storage_path, "concepts.json")
            data = {
                "concepts": [c.to_dict() for c in self._concepts.values()],
                "saved_at": datetime.now().isoformat()
            }

            with open(concepts_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.error(f"Failed to save concepts: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        base_stats = super().get_statistics()
        base_stats.update({
            "total_concepts": len(self._concepts),
            "categories": len(self._concepts_by_category),
            "total_relations": sum(len(c.relations) for c in self._concepts.values()),
            "relation_types": len(self._relations_index)
        })
        return base_stats
