import asyncio
import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from butler.core.config import ButlerConfig, load_config
from butler.core.enhanced_integration import create_enhanced_integration

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_basic_functionality():
    logger.info("=" * 60)
    logger.info("测试基本功能")
    logger.info("=" * 60)

    config = load_config()
    integration = await create_enhanced_integration(config)

    stats = await integration.get_global_stats()
    logger.info(f"\n全局统计:\n{stats}\n")

    test_message = "你好，我是测试用户"
    logger.info(f"发送测试消息: {test_message}")

    result = await integration.chat(user_message=test_message, user_id="test_user")
    logger.info(f"回复: {result['response']}")
    logger.info(f"会话ID: {result['conversation_id']}\n")

    await integration.add_memory(
        content="用户喜欢喝咖啡，特别是早上喝拿铁",
        source="test",
        metadata={"type": "preference"},
    )

    search_results = await integration.search_memory("咖啡", limit=3)
    logger.info(f"搜索'咖啡'找到 {len(search_results)} 条记忆")
    for i, r in enumerate(search_results, 1):
        logger.info(f"  {i}. {r['chunk']['content'][:50]}...")

    await integration.shutdown()


async def test_workspace():
    logger.info("\n" + "=" * 60)
    logger.info("测试工作区系统")
    logger.info("=" * 60)

    from butler.core.workspace import create_workspace_manager

    workspace_manager = create_workspace_manager("test_workspace")
    result = workspace_manager.ensure_workspace()

    logger.info(f"工作区创建结果: {result['created']}")

    for filename, status in result["files"].items():
        logger.info(f"  {filename}: {status['status']}")

    status = workspace_manager.get_workspace_status()
    logger.info(f"\n工作区状态:\n{status}\n")

    validation = workspace_manager.validate_workspace()
    logger.info(f"工作区验证: {'通过' if validation['valid'] else '失败'}")
    if validation["errors"]:
        for error in validation["errors"]:
            logger.error(f"  - {error}")
    if validation["warnings"]:
        for warning in validation["warnings"]:
            logger.warning(f"  - {warning}")


async def test_skills():
    logger.info("\n" + "=" * 60)
    logger.info("测试技能系统")
    logger.info("=" * 60)

    from butler.skills import SkillRegistry, SkillContext
    from butler.skills.builtin import DeviceSkill

    registry = SkillRegistry()
    await registry.initialize_skill(DeviceSkill)

    stats = registry.get_statistics()
    logger.info(f"技能统计: {stats}\n")

    all_commands = registry.get_all_commands()
    logger.info(f"可用命令 ({len(all_commands)}):")
    for name, spec in all_commands.items():
        logger.info(f"  - {name}: {spec.description}")

    context = SkillContext(
        conversation_id="test_conversation",
        user_id="test_user",
    )

    result = await registry.execute_command(
        "turn_on",
        {"device_id": "light_test", "brightness": 80},
        context,
    )
    logger.info(f"\n执行 turn_on: {result.output}")


async def test_memory():
    logger.info("\n" + "=" * 60)
    logger.info("测试内存系统")
    logger.info("=" * 60)

    from butler.memory import EnhancedMemorySystem, MemoryIndexConfig

    memory = EnhancedMemorySystem(
        config=MemoryIndexConfig(
            db_path="test_memory.db",
            embedding_dims=1024,
            enable_fts=True,
            auto_sync=False,
        ),
        embedding_provider=None,
    )

    await memory.initialize()

    await memory.add_memory(
        content="智慧管家是一个智能家居控制系统",
        source="test",
        tags=["system", "description"],
    )

    await memory.add_memory(
        content="用户可以通过语音或文字与管家交互",
        source="test",
        tags=["system", "interaction"],
    )

    results = await memory.search(
        query_text="智能家居",
        limit=5,
        min_score=0.1,
    )

    logger.info(f"搜索'智能家居'找到 {len(results)} 条结果:")
    for i, r in enumerate(results, 1):
        logger.info(
            f"  {i}. [分数: {r.score:.2f}] {r.chunk.content[:60]}..."
        )

    stats = await memory.get_stats()
    logger.info(f"\n内存统计: {stats}\n")

    await memory.stop()


async def test_sessions():
    logger.info("\n" + "=" * 60)
    logger.info("测试会话管理")
    logger.info("=" * 60)

    from butler.core.enhanced_session import SessionManager, SessionBuilder

    session_manager = SessionManager(db_path="test_sessions.db")

    session = await session_manager.create_session(user_id="test_user")
    logger.info(f"创建会话: {session.session_id}")

    await session_manager.add_message(
        session_id=session.session_id,
        role="user",
        content="你好",
    )

    await session_manager.add_message(
        session_id=session.session_id,
        role="assistant",
        content="你好！有什么可以帮助你的？",
    )

    messages = await session_manager.get_messages(session.session_id)
    logger.info(f"会话消息 ({len(messages)}):")
    for msg in messages:
        logger.info(f"  [{msg.role}]: {msg.content[:30]}...")

    stats = await session_manager.get_session_stats(session.session_id)
    logger.info(f"\n会话统计: {stats.to_dict()}\n")

    session_manager.close()


async def run_all_tests():
    logger.info("\n开始整合测试\n")

    try:
        await test_workspace()
        await test_skills()
        await test_memory()
        await test_sessions()
        await test_basic_functionality()

        logger.info("\n" + "=" * 60)
        logger.info("所有测试完成！")
        logger.info("=" * 60 + "\n")

    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
