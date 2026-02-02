# Butler Core 增强版 - 实施指南

## 概述

根据《全屋智慧管家功能深化设计蓝图》，我们已经完成了 Butler Core 系统的全面增强，实现了从"语音控制"到"主动管家服务"的升级。

## 已实现的功能模块

### 1. 家庭知识图谱系统 (`butler/knowledge_graph/`)

**核心组件：**
- **空间建模** (`space_model.py`): 区域-房间-设备三级空间模型
- **设备注册表** (`device_registry.py`): 设备能力库和状态管理
- **用户偏好** (`user_preferences.py`): 用户画像和环境偏好
- **知识图谱** (`knowledge_graph.py`): 统一查询和推理接口

**主要功能：**
```python
from butler.knowledge_graph import KnowledgeGraph

kg = KnowledgeGraph()
kg.query("客厅灯")
kg.get_context_for_user("user_001")
kg.infer_intent_from_context("这里", user_id="user_001")
kg.resolve_reference("那个", user_id="user_001")
```

### 2. 智能对话引擎 (`butler/conversation/`)

**核心组件：**
- **意图分类器** (`intent_classifier.py`): 识别用户意图类型
- **指代消解** (`reference_resolver.py`): 解析"这里"、"那个"等指代
- **上下文管理** (`context_manager.py`): 多轮对话历史管理
- **对话引擎** (`dialogue_engine.py`): 统一对话处理接口

**主要功能：**
```python
from butler.conversation import DialogueEngine

engine = DialogueEngine()
turn = engine.process("我要睡了", user_id="user_001")
print(turn.response)
print(turn.actions)
```

### 3. 目标式交互系统 (`butler/goal_engine/`)

**核心组件：**
- **目标模板** (`goal_templates.py`): 预定义目标模板
- **目标引擎** (`goal_engine.py`): 目标解析和执行

**支持的目标：**
- "我要睡了" - 睡眠模式
- "我要起床" - 起床模式
- "我要出门" - 离家模式
- "我回来了" - 回家模式
- "我要看电影" - 观影模式

**使用示例：**
```python
from butler.goal_engine import GoalEngine

engine = GoalEngine()
goal = engine.parse_goal("我要睡了")
result = engine.execute_goal(goal, action_executor)
```

### 4. 智能场景与自动化引擎 (`butler/automation/`)

**核心组件：**
- **场景引擎** (`scene_engine.py`): 场景管理
- **自动化引擎** (`automation_engine.py`): 触发器-条件-动作规则
- **习惯学习** (`habit_learner.py`): 用户行为模式学习

**预设场景：**
- 回家、离家、睡眠、观影、起床、温馨

**使用示例：**
```python
from butler.automation import SceneEngine, AutomationEngine

scene_engine = SceneEngine()
result = scene_engine.activate_scene("scene_sleep")

auto_engine = AutomationEngine()
auto_engine.evaluate_triggers(trigger_data, state_data)
```

### 5. 主动式管家能力 (`butler/proactive/`)

**核心组件：**
- **异常检测器** (`anomaly_detector.py`): 安全/设备/环境异常监测
- **能耗优化器** (`energy_optimizer.py`): 能耗分析和建议
- **预测服务** (`predictive_service.py`): 用户行为预测

**主要功能：**
```python
from butler.proactive import AnomalyDetector, EnergyOptimizer, PredictiveService

detector = AnomalyDetector()
detector.add_sensor_data("temperature", 38.0)

optimizer = EnergyOptimizer()
optimizer.record_consumption("device_001", 1500)
suggestions = optimizer.generate_suggestions()

predictor = PredictiveService()
prediction = predictor.predict_user_arrival("user_001")
```

### 6. 红外与遥控设备接入 (`butler/ir_control/`)

**核心组件：**
- **IR 控制器** (`ir_controller.py`): 红外命令发送
- **IR 学习器** (`ir_learner.py`): 红外信号学习
- **IR 映射** (`ir_mapping.py`): 语义到红外命令映射

**支持协议：**
- NEC, RC5, RC6, Sony, Samsung, Raw

**使用示例：**
```python
from butler.ir_control import IRController, IRLearner

controller = IRController(use_broadlink=True)
controller.send_command("tv_samsung", "power_on")

learner = IRLearner()
session = learner.start_learning_session("tv_samsung", "volume_up")
result = learner.learn_command(session.session_id)
```

### 7. Docker 虚拟测试环境 (`butler/simulator/`)

**核心组件：**
- **虚拟设备** (`virtual_device.py`): 完整的虚拟设备模拟
- **场景回放** (`scene_replay.py`): 场景录制和回放
- **测试框架** (`test_framework.py`): 自动化测试

**使用示例：**
```python
from butler.simulator import VirtualDeviceManager, SceneReplayer, TestFramework

device_manager = VirtualDeviceManager()
device_manager.execute_command("living_room_light", "turn_on", {"brightness": 100})

replayer = SceneReplayer()
result = replayer.replay_session("session_morning_routine")

framework = TestFramework()
test_results = framework.run_all_tests(context)
```

## 快速开始

### 1. 启动 Docker 环境

```bash
docker-compose up -d
```

### 2. 运行增强版 Butler Core

```bash
cd butler/core
python enhanced_main.py
```

### 3. 运行测试

```bash
cd butler/core
python -c "from enhanced_main import *; b = EnhancedButlerCore(); print(b.run_tests())"
```

### 4. 交互式测试

```python
from butler.core.enhanced_main import EnhancedButlerCore

butler = EnhancedButlerCore()
butler.start()

result = butler.process_user_input("我要睡了", user_id="user_001")
print(result["response"])
```

## 系统架构

```
Butler Enhanced Core
├── Knowledge Graph (知识图谱)
│   ├── Space Model (空间模型)
│   ├── Device Registry (设备注册)
│   └── User Preferences (用户偏好)
├── Conversation Engine (对话引擎)
│   ├── Intent Classifier (意图分类)
│   ├── Reference Resolver (指代消解)
│   └── Context Manager (上下文管理)
├── Goal Engine (目标引擎)
│   └── Goal Templates (目标模板)
├── Automation (自动化)
│   ├── Scene Engine (场景引擎)
│   ├── Automation Engine (自动化引擎)
│   └── Habit Learner (习惯学习)
├── Proactive Services (主动服务)
│   ├── Anomaly Detector (异常检测)
│   ├── Energy Optimizer (能耗优化)
│   └── Predictive Service (预测服务)
├── IR Control (红外控制)
│   ├── IR Controller (控制器)
│   ├── IR Learner (学习器)
│   └── IR Mapping (映射)
└── Simulator (模拟器)
    ├── Virtual Devices (虚拟设备)
    ├── Scene Replayer (场景回放)
    └── Test Framework (测试框架)
```

## 配置文件

配置文件位于 `butler/core/enhanced_config.json`，包含以下模块配置：

- `knowledge_graph`: 知识图谱设置
- `dialogue_engine`: 对话引擎设置
- `goal_engine`: 目标引擎设置
- `scene_engine`: 场景引擎设置
- `automation_engine`: 自动化引擎设置
- `habit_learner`: 习惯学习设置
- `anomaly_detector`: 异常检测设置
- `energy_optimizer`: 能耗优化设置
- `predictive_service`: 预测服务设置
- `ir_control`: 红外控制设置
- `simulator`: 模拟器设置
- `test_framework`: 测试框架设置

## 创新亮点实现

### 1. 目标式交互
从"关灯"升级为"我要睡了"，系统自动理解并执行一系列相关操作。

### 2. 指代消解
能够理解"这里"、"那个"等模糊指代，基于上下文进行推理。

### 3. 主动关怀
通过异常检测和预测服务，主动提醒用户需要注意的事项。

### 4. 习惯学习
自动学习用户的行为模式，提供个性化的自动化建议。

### 5. 跨品牌兼容
通过 IR 映射和学习功能，支持各种品牌的红外设备。

### 6. 完整测试
Docker 内完整的虚拟设备和测试框架，确保系统可靠性。

## 后续扩展建议

1. **生活助手功能**：日程管理、购物清单、烹饪助手（优先级：低）
2. **多模态交互**：手势识别、情感识别（优先级：中）
3. **外部服务集成**：天气、交通、新闻等（优先级：中）
4. **移动 App/Web 控制**：提供更友好的用户界面（优先级：高）

## 技术栈

- **核心框架**: Python 3.11+
- **事件驱动**: MQTT (Eclipse Mosquitto)
- **LLM 规划**: GLM-4.7
- **语音识别**: faster-whisper
- **红外控制**: Broadlink / LIRC
- **容器化**: Docker + Docker Compose

## 文件结构

```
butler/
├── knowledge_graph/       # 知识图谱系统
├── conversation/          # 智能对话引擎
├── goal_engine/          # 目标式交互
├── automation/           # 智能场景与自动化
├── proactive/            # 主动式管家能力
├── ir_control/           # 红外与遥控设备接入
├── simulator/            # 虚拟测试环境
├── core/                # 核心集成
│   ├── enhanced_main.py
│   └── enhanced_config.json
```

## 总结

通过这次优化，Butler Core 已经从一个基础的语音控制系统升级为一个完整的智能家庭管家系统。所有核心功能都已完成，并在 Docker 环境中提供了完整的测试支持。

系统现在具备了：
- ✅ 完整的家庭知识图谱
- ✅ 智能的多轮对话能力
- ✅ 目标式交互
- ✅ 智能场景和自动化
- ✅ 主动式管家服务
- ✅ 红外设备接入
- ✅ 完整的虚拟测试环境

所有模块都是独立的、可配置的、可测试的，为后续的功能扩展打下了坚实的基础。
