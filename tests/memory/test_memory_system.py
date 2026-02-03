import pytest
import asyncio
from datetime import datetime, timedelta
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from butler.memory.memory_system import MemorySystem, MemoryQuery, ConsolidationStrategy
from butler.memory.working_memory import WorkingMemory, FocusItem
from butler.memory.short_term_memory import ShortTermMemory, MemoryItem
from butler.memory.long_term_memory import LongTermMemory
from butler.memory.episodic_memory import Episode, Event
from butler.memory.semantic_memory import Concept, Relation
from butler.memory.procedural_memory import Procedure, ProcedureStep


class TestMemoryQuery:
    def test_query_creation(self):
        query = MemoryQuery(
            query_type="episodic",
            keywords=["test", "memory"],
            start_time=datetime.now() - timedelta(days=1),
            end_time=datetime.now(),
            limit=10
        )
        
        assert query.query_type == "episodic"
        assert "test" in query.keywords
        assert query.limit == 10


class TestFocusItem:
    def test_focus_item_creation(self):
        item = FocusItem(
            content="Test content",
            importance=5,
            context={"key": "value"}
        )
        
        assert item.content == "Test content"
        assert item.importance == 5
        assert item.context == {"key": "value"}


@pytest.mark.asyncio
class TestWorkingMemory:
    @pytest.fixture
    def working_memory(self):
        return WorkingMemory(max_size=7)

    async def test_working_memory_creation(self, working_memory):
        assert working_memory.max_size == 7
        assert len(working_memory.get_items()) == 0

    async def test_add_item(self, working_memory):
        item = FocusItem(
            content="Test content",
            importance=5
        )
        
        await working_memory.add(item)
        
        items = working_memory.get_items()
        assert len(items) == 1
        assert items[0].content == "Test content"

    async def test_get_item(self, working_memory):
        item = FocusItem(
            content="Test content",
            importance=5
        )
        
        await working_memory.add(item)
        
        retrieved = working_memory.get_item(item.item_id)
        assert retrieved is not None
        assert retrieved.content == "Test content"

    async def test_remove_item(self, working_memory):
        item = FocusItem(
            content="Test content",
            importance=5
        )
        
        await working_memory.add(item)
        working_memory.remove(item.item_id)
        
        retrieved = working_memory.get_item(item.item_id)
        assert retrieved is None

    async def test_clear(self, working_memory):
        for i in range(3):
            item = FocusItem(content=f"Content {i}", importance=i+1)
            await working_memory.add(item)
        
        working_memory.clear()
        assert len(working_memory.get_items()) == 0

    async def test_lru_eviction(self, working_memory):
        for i in range(10):
            item = FocusItem(content=f"Content {i}", importance=i+1)
            await working_memory.add(item)
        
        items = working_memory.get_items()
        assert len(items) == 7


@pytest.mark.asyncio
class TestShortTermMemory:
    @pytest.fixture
    def short_term_memory(self):
        return ShortTermMemory(max_capacity=1000, ttl=3600.0)

    async def test_short_term_memory_creation(self, short_term_memory):
        assert short_term_memory.max_capacity == 1000
        assert short_term_memory.ttl == 3600.0

    async def test_add_memory(self, short_term_memory):
        item = MemoryItem(
            content="Test memory",
            importance=5,
            tags=["test"]
        )
        
        await short_term_memory.add(item)
        
        retrieved = await short_term_memory.get(item.item_id)
        assert retrieved is not None
        assert retrieved.content == "Test memory"

    async def test_search_by_tags(self, short_term_memory):
        item1 = MemoryItem(content="Memory 1", importance=5, tags=["test", "important"])
        item2 = MemoryItem(content="Memory 2", importance=3, tags=["test"])
        item3 = MemoryItem(content="Memory 3", importance=7, tags=["other"])
        
        await short_term_memory.add(item1)
        await short_term_memory.add(item2)
        await short_term_memory.add(item3)
        
        results = await short_term_memory.search(tags=["test"])
        assert len(results) == 2

    async def test_search_by_importance(self, short_term_memory):
        item1 = MemoryItem(content="Memory 1", importance=3)
        item2 = MemoryItem(content="Memory 2", importance=7)
        item3 = MemoryItem(content="Memory 3", importance=5)
        
        await short_term_memory.add(item1)
        await short_term_memory.add(item2)
        await short_term_memory.add(item3)
        
        results = await short_term_memory.search(min_importance=5)
        assert len(results) == 2

    async def test_cleanup_expired(self, short_term_memory):
        short_term_memory.ttl = 0.001
        
        item = MemoryItem(content="Test memory", importance=5)
        await short_term_memory.add(item)
        
        await asyncio.sleep(0.01)
        await short_term_memory.cleanup_expired()
        
        retrieved = await short_term_memory.get(item.item_id)
        assert retrieved is None


@pytest.mark.asyncio
class TestMemorySystem:
    @pytest.fixture
    def memory_system(self, temp_dir):
        return MemorySystem(
            working_memory_size=7,
            short_term_capacity=1000,
            short_term_ttl=3600.0,
            storage_path=temp_dir
        )

    async def test_memory_system_creation(self, memory_system):
        assert memory_system.working_memory.max_size == 7
        assert memory_system.short_term_memory.max_capacity == 1000

    async def test_add_working_memory(self, memory_system):
        content = "Test working memory"
        await memory_system.add_working_memory(content, importance=5)
        
        items = memory_system.working_memory.get_items()
        assert len(items) > 0
        assert any(item.content == content for item in items)

    async def test_add_short_term_memory(self, memory_system):
        content = "Test short term memory"
        await memory_system.add_short_term_memory(content, importance=5, tags=["test"])
        
        results = await memory_system.short_term_memory.search(tags=["test"])
        assert len(results) > 0

    async def test_query_memory(self, memory_system):
        await memory_system.add_short_term_memory("Test memory", importance=5, tags=["test"])
        
        query = MemoryQuery(query_type="short_term", keywords=["test"])
        results = await memory_system.query(query)
        
        assert len(results) > 0

    async def test_consolidate_memory(self, memory_system):
        await memory_system.add_short_term_memory("Important memory", importance=8)
        
        await memory_system.consolidate(ConsolidationStrategy.IMPORTANCE_BASED)
        
        results = await memory_system.long_term_memory.search(keywords=["important"])
        assert len(results) > 0

    async def test_get_statistics(self, memory_system):
        stats = await memory_system.get_statistics()
        
        assert "working_memory" in stats
        assert "short_term_memory" in stats
        assert "long_term_memory" in stats

    async def test_save_load(self, memory_system):
        await memory_system.add_short_term_memory("Test memory", importance=5)
        
        await memory_system.save()
        
        new_system = MemorySystem(storage_path=memory_system.long_term_memory.storage_path)
        await new_system.load()
        
        results = await new_system.long_term_memory.search(keywords=["test"])
        assert len(results) > 0


class TestEpisode:
    def test_episode_creation(self):
        episode = Episode(
            episode_id="ep_001",
            title="Test Episode",
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(minutes=5)
        )
        
        assert episode.episode_id == "ep_001"
        assert episode.title == "Test Episode"

    def test_episode_add_event(self):
        episode = Episode(
            episode_id="ep_001",
            title="Test Episode",
            start_time=datetime.now()
        )
        
        event = Event(
            event_id="evt_001",
            event_type="action",
            description="User action",
            timestamp=datetime.now()
        )
        
        episode.add_event(event)
        
        assert len(episode.events) == 1


class TestConcept:
    def test_concept_creation(self):
        concept = Concept(
            concept_id="conc_001",
            name="Test Concept",
            description="A test concept",
            category="test"
        )
        
        assert concept.concept_id == "conc_001"
        assert concept.name == "Test Concept"
        assert concept.category == "test"

    def test_concept_add_relation(self):
        concept1 = Concept(
            concept_id="conc_001",
            name="Concept 1",
            category="test"
        )
        
        concept2 = Concept(
            concept_id="conc_002",
            name="Concept 2",
            category="test"
        )
        
        relation = Relation(
            relation_id="rel_001",
            source_id="conc_001",
            target_id="conc_002",
            relation_type="related_to"
        )
        
        concept1.add_relation(relation)
        
        assert len(concept1.relations) == 1


class TestProcedure:
    def test_procedure_creation(self):
        procedure = Procedure(
            procedure_id="proc_001",
            name="Test Procedure",
            description="A test procedure"
        )
        
        assert procedure.procedure_id == "proc_001"
        assert procedure.name == "Test Procedure"

    def test_procedure_add_step(self):
        procedure = Procedure(
            procedure_id="proc_001",
            name="Test Procedure"
        )
        
        step = ProcedureStep(
            step_id="step_001",
            step_type="action",
            description="Perform action",
            parameters={"action": "test"}
        )
        
        procedure.add_step(step)
        
        assert len(procedure.steps) == 1

    def test_procedure_success_rate(self):
        procedure = Procedure(
            procedure_id="proc_001",
            name="Test Procedure"
        )
        
        procedure.record_execution(success=True)
        procedure.record_execution(success=True)
        procedure.record_execution(success=False)
        
        assert procedure.get_success_rate() == 2/3
