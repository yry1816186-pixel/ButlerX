# Contributing to ButlerX (智慧管家)

Thank you for your interest in contributing to ButlerX! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

### Prerequisites

- Python 3.11 or higher
- Docker and Docker Compose
- Git
- Node.js 18+ (for frontend development)

### Setting Up Development Environment

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/ButlerX.git
   cd ButlerX
   ```

3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

5. Set up configuration:
   ```bash
   cp butler/config.json.example butler/config.json
   ```

6. Run tests:
   ```bash
   pytest
   ```

## Development Workflow

### Branch Naming

- `feature/` - New features
- `bugfix/` - Bug fixes
- `hotfix/` - Critical fixes for production
- `docs/` - Documentation changes
- `refactor/` - Code refactoring
- `test/` - Test additions or changes

### Commit Messages

Follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Example:
```
feat(vision): add face recognition support

Implement face recognition using YOLOv8 with improved
accuracy and performance optimization.

Closes #123
```

## Coding Standards

### Python

- Follow PEP 8 style guidelines
- Use type hints for function signatures
- Write docstrings for all public functions and classes
- Maximum line length: 100 characters
- Use `black` for formatting and `isort` for imports

### Vue.js/JavaScript

- Follow Vue.js style guide
- Use Composition API
- Use ESLint for linting
- Follow naming conventions: camelCase for variables, PascalCase for components

### Code Quality Tools

Run these before committing:
```bash
# Format code
black butler/
isort butler/

# Lint
flake8 butler/
pylint butler/

# Type check
mypy butler/

# Run tests
pytest --cov=butler
```

## Testing

### Writing Tests

- Write unit tests for all new functions and classes
- Write integration tests for critical workflows
- Use descriptive test names
- Follow Arrange-Act-Assert pattern

### Test Coverage

Maintain at least 80% code coverage. New features should include tests.

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=butler --cov-report=html

# Run specific test file
pytest butler/tests/test_exceptions.py

# Run with markers
pytest -m unit
pytest -m integration
```

## Submitting Changes

1. Ensure all tests pass
2. Run code quality checks
3. Update documentation if needed
4. Create a pull request with:
   - Clear title and description
   - Reference related issues
   - Screenshots for UI changes
   - Performance metrics for optimizations

## Reporting Issues

When reporting bugs or suggesting features:

1. Search existing issues first
2. Use appropriate issue templates
3. Provide:
   - Clear description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)
   - Logs or screenshots

## Questions?

Feel free to open an issue for questions or discussions about the project.

---

Thank you for contributing to ButlerX! Your contributions make this project better for everyone.
