# Butler Project Tests

This directory contains comprehensive pytest tests for the Butler (Smart Butler) project.

## Test Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures and test configuration
├── core/                    # Core system tests
│   ├── test_entity_model.py
│   └── test_error_handler.py
├── automation/              # Automation system tests
│   ├── test_triggers.py
│   └── test_automation_engine.py
├── agents/                  # Multi-agent system tests
│   └── test_agent.py
├── memory/                  # Memory system tests
│   └── test_memory_system.py
└── goal_engine/             # Goal engine tests
    └── test_goal_engine.py
```

## Running Tests

### Run all tests:
```bash
pytest
```

Or on Windows:
```batch
run_tests.bat
```

### Run specific test module:
```bash
pytest tests/core/test_entity_model.py
```

### Run specific test class:
```bash
pytest tests/core/test_entity_model.py::TestEntity
```

### Run specific test function:
```bash
pytest tests/core/test_entity_model.py::TestEntity::test_entity_creation
```

### Run tests with coverage:
```bash
pytest --cov=butler --cov-report=html
```

### Run only fast tests (skip slow):
```bash
pytest -m "not slow"
```

### Run only integration tests:
```bash
pytest -m integration
```

## Test Categories

- **Unit tests**: Test individual components in isolation
- **Integration tests**: Test interactions between components
- **Async tests**: Test asynchronous functionality using pytest-asyncio

## Fixtures

The `conftest.py` file provides shared fixtures:
- `temp_dir`: Temporary directory for file operations
- `sample_device_data`: Sample device entity data
- `sample_sensor_data`: Sample sensor entity data
- `sample_user_data`: Sample user entity data
- `sample_context`: Sample execution context
- `sample_agent_message`: Sample agent message
- `sample_agent_task`: Sample agent task
- And many more...

## Adding New Tests

When adding new functionality, follow these patterns:

1. Create a new test file in the appropriate directory
2. Use descriptive test names that explain what is being tested
3. Use fixtures to set up test data
4. Test both success and failure cases
5. Use pytest marks for categorizing tests

Example:
```python
import pytest
from butler.core.module import MyClass

class TestMyClass:
    def test_creation(self):
        obj = MyClass()
        assert obj is not None
    
    @pytest.mark.asyncio
    async def test_async_method(self):
        obj = MyClass()
        result = await obj.async_method()
        assert result is not None
```

## Test Requirements

- pytest >= 7.0.0
- pytest-asyncio >= 0.20.0
- pytest-cov (optional, for coverage reports)

Install dependencies:
```bash
pip install pytest pytest-asyncio pytest-cov
```
