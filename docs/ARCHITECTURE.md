# Smart Butler Architecture Documentation

## Overview

Smart Butler is an intelligent home automation system built with Python, designed to coordinate multiple agents, manage smart home devices, and provide voice and vision-based interaction capabilities.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │   Web UI  │  │  Mobile   │  │   API    │           │
│  └──────────┘  └──────────┘  └──────────┘           │
└────────────────────────┬────────────────────────────────────────┘
                     │ REST/WebSocket
┌────────────────────────▼────────────────────────────────────────┐
│                     FastAPI Server                          │
└────────────────────────┬────────────────────────────────────────┘
                     │ MQTT
┌────────────────────────▼────────────────────────────────────────┐
│                    ButlerService                             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   MQTT      │  │    Brain     │  │    Tool      │ │
│  │   Client    │  │   System     │  │   Runner     │ │
│  └─────────────┘  └──────────────┘  └──────────────┘ │
└────────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┼────────────┬────────────┐
        │            │            │            │
┌───────▼─────┐ ┌───▼─────┐ ┌───▼─────┐ ┌───▼─────┐
│  Database    │ │  Agents  │ │  Tools  │ │  Open   │
│  (SQLite)    │ │          │ │          │ │  Claw   │
└──────────────┘ └──────────┘ └──────────┘ └──────────┘
```

## Core Components

### 1. ButlerService (`butler/core/service.py`)

**Purpose**: Central service orchestrating all system components

**Responsibilities**:
- MQTT message handling
- Brain/planning coordination
- Policy evaluation
- Tool execution coordination
- Scheduling management

**Key Methods**:
- `start()`: Initialize all subsystems
- `stop()`: Graceful shutdown
- `_on_connect()`: MQTT connection handler
- `_on_message()`: Message dispatcher

### 2. ToolRunner (`butler/core/tool_runner.py`)

**Purpose**: Executes actions and manages tool integrations

**Responsibilities**:
- PTZ camera control
- Home Assistant integration
- Email operations
- Image generation
- Voice recognition
- Vision detection
- Web search
- OpenClaw integration
- System/script execution
- Device control

**Key Methods**:
- `execute_plan()`: Execute multiple actions
- `_execute_action()`: Execute single action with validation
- `_blocked_by_privacy()`: Privacy mode check

### 3. Brain System (`butler/brain/`)

**Purpose**: LLM-based planning and decision making

**Components**:

#### BrainPlanner (`planner.py`)
- Generates action plans from user requests
- Implements caching with LRU eviction
- Supports vision input
- Configurable allowlists for security

#### BrainRuleEngine (`rule_engine.py`)
- Rule-based decision making
- Event-condition-action patterns
- Dynamic rule management

#### BrainMemory (`memory.py`)
- Vector-based memory storage
- Embedding-based similarity search
- Long-term and short-term memory

### 4. Agent System (`butler/agents/`)

**Purpose**: Specialized agents for different capabilities

**Agents**:
- **AgentCoordinator**: Orchestrates multiple agents
- **DeviceAgent**: Manages device interactions
- **VisionAgent**: Handles computer vision tasks
- **DialogueAgent**: Manages conversations
- **GoalAgent**: Goal-oriented planning

### 5. Device Hub (`butler/core/device_hub.py`)

**Purpose**: Unified device control interface

**Responsibilities**:
- Home Assistant device control
- DaShan robot control
- PTZ camera control
- Infrared remote control
- Frigate monitoring integration

### 6. Automation Engine (`butler/automation/`)

**Purpose**: Scene and automation management

**Components**:
- **SceneEngine**: Scene activation and management
- **TriggerEngine**: Event-based triggers
- **ConditionEngine**: Condition evaluation
- **ActionEngine**: Action execution

### 7. Goal Engine (`butler/goal_engine.py`)

**Purpose**: Goal-oriented planning and execution

**Features**:
- Natural language goal parsing
- Goal decomposition
- Step-by-step execution
- Progress tracking

## Data Flow

### Event Processing Flow

```
1. Event (MQTT/Web/API)
   ↓
2. ButlerService._on_message()
   ↓
3. PolicyEngine.evaluate()
   ↓
4. If policy allows:
   - BrainPlanner.plan() → generates actions
   - OR BrainRuleEngine.evaluate() → matches rules
   ↓
5. ToolRunner.execute_plan()
   ↓
6. Action execution (various tools)
   ↓
7. ActionResult → MQTT/Web/API
```

### Planning Flow

```
1. User Request
   ↓
2. BrainRequest (text + images + context)
   ↓
3. BrainPlanner.plan()
   - Check cache
   - Run vision if images present
   - Call LLM for planning
   ↓
4. ActionPlan generated
   ↓
5. ToolRunner.execute_plan()
   ↓
6. Execute actions sequentially
   ↓
7. Return ActionResult[]
```

### Device Control Flow

```
1. Device Request
   ↓
2. DeviceControlHub
   - Identify backend (HA/DaShan/PTZ/IR)
   ↓
3. Backend-specific implementation
   - HomeAssistantAPI.call_service()
   - OR DaShanAdapter.send_command()
   - OR PTZOnvif.goto_preset()
   - OR IRController.send_command()
   ↓
4. Return device state/response
```

## Database Schema

### Events Table
```sql
CREATE TABLE events (
    id TEXT PRIMARY KEY,
    ts REAL NOT NULL,
    type TEXT NOT NULL,
    source TEXT,
    payload TEXT,
    processed INTEGER DEFAULT 0
);
CREATE INDEX idx_events_ts ON events(ts);
```

### Plans Table
```sql
CREATE TABLE plans (
    plan_id TEXT PRIMARY KEY,
    triggered_by_event_id TEXT,
    actions TEXT NOT NULL,
    policy TEXT,
    reason TEXT,
    created_ts REAL NOT NULL
);
CREATE INDEX idx_plans_created_ts ON plans(created_ts);
CREATE INDEX idx_plans_triggered ON plans(triggered_by_event_id);
```

### Results Table
```sql
CREATE TABLE results (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL,
    output TEXT,
    created_ts REAL NOT NULL
);
CREATE INDEX idx_results_plan_id ON results(plan_id);
CREATE INDEX idx_results_created_ts ON results(created_ts);
```

## Security Architecture

### 1. Input Validation
- Configuration validation (`config_validator.py`)
- Parameter validation in ToolRunner
- URL and path validation

### 2. Execution Safety
- Allowlist-based command execution
- Script execution restrictions
- Sandbox environment (`sandbox.py`)
- Resource limits

### 3. Privacy Mode
- Configurable action blocking
- Camera action restrictions
- Event storage filtering

### 4. Authentication
- API key authentication
- Token-based authentication
- Secure credential storage

## Configuration Management

### Configuration Structure (`butler/config.json`)
```json
{
  "mqtt": {
    "host": "localhost",
    "port": 1883,
    "username": null,
    "password": null,
    "use_tls": false
  },
  "llm": {
    "api_url": "https://api.example.com",
    "api_key": "...",
    "model": "gpt-4"
  },
  "openclaw": {
    "cli_path": "/path/to/openclaw",
    "gateway_enabled": true,
    "gateway_url": "ws://localhost:18789",
    "channels": [...]
  },
  "security": {
    "system_exec_allowlist": [...],
    "script_allowlist": [...]
  }
}
```

### Environment Variables
Sensitive values can be overridden via environment:
- `BUTLER_MQTT_PASSWORD`
- `BUTLER_LLM_API_KEY`
- `BUTLER_OPENCLAW_TOKEN`
- etc.

## Performance Optimization

### 1. Database Optimization (`db_optimization.py`)
- Indexing on frequently queried columns
- Query result caching
- Periodic VACUUM and ANALYZE
- Connection pooling

### 2. LLM Caching
- Request/response caching
- LRU eviction policy
- Cache key based on content hash
- Configurable TTL

### 3. Retry Mechanism (`retry.py`)
- Exponential backoff
- Multiple backoff strategies
- Fallback support
- Configurable retry counts

### 4. Asynchronous Operations
- MQTT message handling
- Gateway WebSocket connections
- HTTP request handling
- Background task processing

## OpenClaw Integration

### Integration Modes

1. **CLI Mode**: Uses subprocess to call OpenClaw CLI
   - Pros: Simple, no additional dependencies
   - Cons: Slower, no real-time events

2. **Gateway Mode**: Uses WebSocket connection to OpenClaw Gateway
   - Pros: Fast, real-time events, reconnection support
   - Cons: Requires running gateway

### Optimized Gateway Client (`openclaw_gateway_optimized.py`)
- Automatic reconnection with exponential backoff
- Connection state management
- Request timeout and retry
- Heartbeat mechanism
- Event handling with callbacks

### Supported Operations
- Send message
- Send media
- Send buttons
- Reply to message
- Send to thread
- Get contacts
- Get channels
- etc.

## Extension Points

### 1. Custom Tools
Create a new tool class and integrate with ToolRunner:
```python
class MyTool:
    def execute(self, params):
        # Implementation
        return {"result": ...}
```

### 2. Custom Agents
Inherit from base agent class:
```python
class MyAgent(Agent):
    def process(self, event):
        # Implementation
        pass
```

### 3. Custom Rules
Define rules in JSON format:
```json
{
  "name": "my_rule",
  "trigger": {...},
  "conditions": [...],
  "actions": [...]
}
```

### 4. Custom Scenes
Define scenes in JSON format:
```json
{
  "id": "my_scene",
  "name": "My Scene",
  "actions": [...]
}
```

## Monitoring and Logging

### Logging
- Structured logging with Python logging
- Log levels: DEBUG, INFO, WARNING, ERROR
- Contextual information in logs

### Metrics
- Cache hit rates
- Request/response times
- Error rates
- System resource usage

### Health Checks
- Database connectivity
- MQTT connectivity
- LLM API connectivity
- Device connectivity

## Deployment Considerations

### System Requirements
- Python 3.8+
- SQLite 3.x
- MQTT broker (Mosquitto, EMQX, etc.)
- Optional: Docker for sandboxing
- Optional: Firejail for sandboxing

### Recommended Hardware
- CPU: 4+ cores for concurrent processing
- RAM: 4GB+ for LLM and vision models
- Storage: SSD for database performance
- GPU: Optional for accelerated vision processing

### Scaling
- Horizontal scaling via MQTT clustering
- Load balancing for API endpoints
- Database sharding for large deployments
- Distributed caching (Redis)

## Future Enhancements

### Planned Features
1. Plugin system for dynamic tool loading
2. Multi-language support
3. WebRTC for real-time communication
4. Machine learning for pattern recognition
5. Voice cloning and synthesis
6. AR/VR interface
7. Mobile app development

### Architecture Improvements
1. Microservices architecture
2. Event sourcing
3. CQRS pattern
4. GraphQL API
5. gRPC for service communication

## References

- [OpenClaw Integration Guide](./OPENCLAW_INTEGRATION.md)
- [API Documentation](./API.md)
- [User Guide](./USER_GUIDE.md)
- [Developer Guide](./DEVELOPER_GUIDE.md)
