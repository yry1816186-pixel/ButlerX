# Changelog

All notable changes to ButlerX (智慧管家) will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Core Infrastructure
- Structured exception hierarchy with error codes and details (`butler/core/exceptions.py`)
- Comprehensive retry mechanism with 5 backoff strategies (`butler/core/retry.py`)
  - Fixed, Linear, Exponential, Exponential with Jitter, Fibonacci backoffs
  - Support for sync and async execution
  - Decorator-based retry with `@retry_with_config`
- Configuration validation system (`butler/core/config_validator.py`)
  - URL, port, path validation
  - MQTT, OpenClaw, email, vision, security settings validation
  - Detailed error and warning reporting
- Sandbox execution environment (`butler/core/sandbox.py`)
  - Resource limits (memory, CPU, files, network)
  - Multiple sandbox types (none, chroot, namespace, docker, firejail)
  - Command safety validation with allowlist
- Database optimization module (`butler/core/db_optimization.py`)
  - Automatic index creation on frequently queried columns
  - Query result caching with LRU/LFU/FIFO/TTL eviction strategies
  - Table version tracking for cache invalidation
  - ANALYZE and VACUUM operations for performance

#### OpenClaw Integration
- Optimized OpenClaw Gateway client (`butler/tools/openclaw_gateway_optimized.py`)
  - WebSocket client with auto-reconnect
  - Heartbeat/keepalive mechanism
  - Connection state management
  - Request timeout and retry logic
  - Backward compatibility with synchronous wrapper

#### Code Quality
- Comprehensive docstrings added to core classes:
  - `ButlerService` - Core service orchestration
  - `ToolRunner` - Action execution engine
  - `BrainPlanner` - LLM-based planning
- Parameter validation for all critical actions in ToolRunner
- Type annotations improved across core modules

#### Testing
- Complete test suite with 800+ test cases
  - `test_exceptions.py` - Exception hierarchy tests (150+ tests)
  - `test_retry.py` - Retry mechanism tests (200+ tests)
  - `test_config_validator.py` - Config validation tests (100+ tests)
  - `test_sandbox.py` - Sandbox and resource limit tests (150+ tests)
  - `test_tool_runner.py` - Tool runner functionality tests (100+ tests)
  - `test_db_optimization.py` - Database optimization tests (100+ tests)
- Pytest configuration with coverage reporting
- Development dependencies in `requirements-dev.txt`

#### Documentation
- Architecture documentation (`docs/ARCHITECTURE.md`)
  - System architecture diagrams
  - Core components and data flow
  - Database schema
  - Security architecture
  - OpenClaw integration details
  - Extension points
- Optimization roadmap (`docs/OPTIMIZATION_ROADMAP.md`)
  - 9-phase improvement plan
  - Testing and quality assurance
  - Performance and scalability
  - Advanced features
  - User experience improvements
  - Security and compliance
  - AI and machine learning enhancements
  - DevOps and monitoring

### Changed
- Enhanced error handling in `ToolRunner` with custom exceptions
- Improved parameter validation across all tool actions
- Updated project structure with organized core modules
- Enhanced logging with structured error reporting

### Security
- Command allowlist for sandbox execution
- Dangerous command detection and blocking
- Resource limiting for command execution
- Path-based access control (allowed/blocked paths)

### Performance
- Database indexes on 10+ tables for query optimization
- Query caching with multiple eviction strategies
- Automatic cache invalidation on table modifications
- Connection pooling and retry logic for external services

## [0.1.0] - 2025-01-XX

### Initial Release

#### Features
- Smart Butler AI system with GLM-4.7 LLM
- DaShan robot integration via MQTT
- Mobile camera integration with PTZ control
- Home Assistant API integration
- Vision capabilities:
  - Face recognition
  - Object detection (YOLOv8/v11)
  - Human pose estimation
- Voice interaction:
  - Automatic speech recognition (Faster-Whisper)
  - Text-to-speech (Piper-TTS)
- Event-driven architecture
- Policy engine for automatic actions
- Scheduling system
- Memory and context management
- Multi-modal perception
- Decision making system
- OpenClaw integration (CLI and Gateway modes)
- IR control for appliances
- Email notifications
- Image generation
- System command execution

#### Infrastructure
- FastAPI backend
- MQTT broker (Eclipse Mosquitto)
- SQLite database with WAL mode
- Vue.js 3 frontend with Tailwind CSS
- Docker containerization
- WebSocket for real-time updates

#### Documentation
- Comprehensive README with architecture diagrams
- API documentation
- Configuration guide
- Deployment instructions
- OpenClaw integration documentation

---

[Unreleased]: https://github.com/YourUsername/ButlerX/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/YourUsername/ButlerX/releases/tag/v0.1.0
