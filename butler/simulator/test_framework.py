from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TestStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TestResult:
    test_id: str
    test_name: str
    status: TestStatus
    start_time: float
    end_time: Optional[float] = None
    duration: float = 0.0
    error_message: Optional[str] = None
    assertion_results: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "test_name": self.test_name,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "error_message": self.error_message,
            "assertion_results": self.assertion_results,
            "metadata": self.metadata,
        }


@dataclass
class TestCase:
    test_id: str
    name: str
    description: str
    setup: Optional[Callable] = None
    test_func: Optional[Callable] = None
    teardown: Optional[Callable] = None
    expected_results: Optional[Dict[str, Any]] = None
    timeout: float = 30.0
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_id": self.test_id,
            "name": self.name,
            "description": self.description,
            "expected_results": self.expected_results,
            "timeout": self.timeout,
            "enabled": self.enabled,
        }


class TestFramework:
    def __init__(self) -> None:
        self.test_cases: Dict[str, TestCase] = {}
        self.test_results: List[TestResult] = []
        self.before_all: Optional[Callable] = None
        self.after_all: Optional[Callable] = None
        self._init_default_tests()

    def _init_default_tests(self) -> None:
        default_tests = [
            TestCase(
                test_id="test_virtual_device_creation",
                name="虚拟设备创建",
                description="测试虚拟设备管理器创建和添加设备",
                expected_results={"device_count": 10},
            ),
            TestCase(
                test_id="test_light_control",
                name="灯光控制",
                description="测试灯光设备的开关和亮度控制",
                expected_results={"light_states": ["on", "off", "on"]},
            ),
            TestCase(
                test_id="test_climate_control",
                name="空调控制",
                description="测试空调设备的温度和模式控制",
                expected_results={"temperature_set": True},
            ),
            TestCase(
                test_id="test_scene_activation",
                name="场景激活",
                description="测试场景的激活和执行",
                expected_results={"scene_executed": True},
            ),
            TestCase(
                test_id="test_goal_execution",
                name="目标执行",
                description="测试目标式交互的执行",
                expected_results={"goal_completed": True},
            ),
            TestCase(
                test_id="test_anomaly_detection",
                name="异常检测",
                description="测试异常监测系统的功能",
                expected_results={"anomaly_detected": True},
            ),
            TestCase(
                test_id="test_automation_trigger",
                name="自动化触发",
                description="测试自动化规则触发和执行",
                expected_results={"automation_triggered": True},
            ),
            TestCase(
                test_id="test_energy_optimization",
                name="能耗优化",
                description="测试能耗优化建议生成",
                expected_results={"suggestions_generated": True},
            ),
        ]

        for test in default_tests:
            self.add_test_case(test)

        logger.info(f"Initialized {len(default_tests)} test cases")

    def add_test_case(self, test_case: TestCase) -> None:
        self.test_cases[test_case.test_id] = test_case
        logger.info(f"Added test case: {test_case.name}")

    def remove_test_case(self, test_id: str) -> bool:
        if test_id not in self.test_cases:
            return False
        test_case = self.test_cases.pop(test_id)
        logger.info(f"Removed test case: {test_case.name}")
        return True

    def get_test_case(self, test_id: str) -> Optional[TestCase]:
        return self.test_cases.get(test_id)

    def list_test_cases(self, enabled_only: bool = False) -> List[TestCase]:
        test_cases = list(self.test_cases.values())
        if enabled_only:
            test_cases = [t for t in test_cases if t.enabled]
        return test_cases

    def set_before_all(self, func: Callable) -> None:
        self.before_all = func

    def set_after_all(self, func: Callable) -> None:
        self.after_all = func

    def run_test(
        self,
        test_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> TestResult:
        context = context or {}
        test_case = self.test_cases.get(test_id)

        if not test_case:
            return TestResult(
                test_id=test_id,
                test_name="Unknown",
                status=TestStatus.FAILED,
                start_time=time.time(),
                error_message=f"Test case not found: {test_id}",
            )

        if not test_case.enabled:
            return TestResult(
                test_id=test_id,
                test_name=test_case.name,
                status=TestStatus.SKIPPED,
                start_time=time.time(),
                end_time=time.time(),
                duration=0.0,
            )

        result = TestResult(
            test_id=test_id,
            test_name=test_case.name,
            status=TestStatus.RUNNING,
            start_time=time.time(),
        )

        try:
            logger.info(f"Running test: {test_case.name}")

            if test_case.setup:
                test_case.setup(context)

            if test_case.test_func:
                test_result = test_case.test_func(context)
                if isinstance(test_result, dict):
                    result.metadata.update(test_result)
                    result.assertion_results.append({
                        "type": "test_result",
                        "result": test_result,
                    })

            result.status = TestStatus.PASSED
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time

            if test_case.teardown:
                test_case.teardown(context)

            logger.info(f"Test passed: {test_case.name}")

        except AssertionError as e:
            result.status = TestStatus.FAILED
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time
            result.error_message = str(e)
            logger.error(f"Test failed (assertion): {test_case.name} - {e}")
        except Exception as e:
            result.status = TestStatus.FAILED
            result.end_time = time.time()
            result.duration = result.end_time - result.start_time
            result.error_message = str(e)
            logger.error(f"Test failed (error): {test_case.name} - {e}")

        self.test_results.append(result)
        return result

    def run_all_tests(
        self,
        context: Optional[Dict[str, Any]] = None,
        parallel: bool = False
    ) -> Dict[str, Any]:
        context = context or {}
        results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "results": [],
            "start_time": time.time(),
            "end_time": None,
            "duration": 0.0,
        }

        try:
            if self.before_all:
                self.before_all(context)

            enabled_tests = self.list_test_cases(enabled_only=True)
            results["total"] = len(enabled_tests)

            for test_case in enabled_tests:
                test_result = self.run_test(test_case.test_id, context)
                results["results"].append(test_result.to_dict())

                if test_result.status == TestStatus.PASSED:
                    results["passed"] += 1
                elif test_result.status == TestStatus.FAILED:
                    results["failed"] += 1
                elif test_result.status == TestStatus.SKIPPED:
                    results["skipped"] += 1

            if self.after_all:
                self.after_all(context)

        except Exception as e:
            logger.error(f"Test suite execution failed: {e}")
            results["error"] = str(e)

        results["end_time"] = time.time()
        results["duration"] = results["end_time"] - results["start_time"]

        return results

    def get_test_results(
        self,
        limit: int = 50,
        status: Optional[TestStatus] = None
    ) -> List[TestResult]:
        results = self.test_results[-limit:]

        if status:
            results = [r for r in results if r.status == status]

        return results

    def get_statistics(self) -> Dict[str, Any]:
        if not self.test_results:
            return {
                "total_runs": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "success_rate": 0.0,
            }

        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in self.test_results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in self.test_results if r.status == TestStatus.SKIPPED)

        return {
            "total_runs": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "success_rate": (passed / total * 100) if total > 0 else 0.0,
        }

    def assert_equal(self, actual: Any, expected: Any, message: str = "") -> None:
        if actual != expected:
            raise AssertionError(
                f"{message or 'Values are not equal'}: expected {expected}, got {actual}"
            )

    def assert_true(self, value: Any, message: str = "") -> None:
        if not value:
            raise AssertionError(
                f"{message or 'Expected True'}: got {value}"
            )

    def assert_false(self, value: Any, message: str = "") -> None:
        if value:
            raise AssertionError(
                f"{message or 'Expected False'}: got {value}"
            )

    def assert_contains(self, container: Any, item: Any, message: str = "") -> None:
        if item not in container:
            raise AssertionError(
                f"{message or 'Item not found in container'}: {item} not in {container}"
            )

    def clear_results(self) -> None:
        self.test_results.clear()
        logger.info("Cleared test results")

    def search_tests(self, query: str) -> List[TestCase]:
        query_lower = query.lower()
        return [
            test for test in self.test_cases.values()
            if (query_lower in test.name.lower() or 
                query_lower in test.description.lower() or
                query_lower in test.test_id.lower())
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "test_cases": [tc.to_dict() for tc in self.test_cases.values()],
            "test_results": [tr.to_dict() for tr in self.test_results[-50:]],
            "statistics": self.get_statistics(),
        }

    def save_to_file(self, filepath: str) -> None:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"Test framework data saved to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str) -> "TestFramework":
        framework = cls()
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        for test_data in data.get("test_cases", []):
            test_case = TestCase(
                test_id=test_data["test_id"],
                name=test_data["name"],
                description=test_data["description"],
                expected_results=test_data.get("expected_results"),
                timeout=test_data.get("timeout", 30.0),
                enabled=test_data.get("enabled", True),
            )
            framework.add_test_case(test_case)

        logger.info(f"Test framework loaded from {filepath}")
        return framework
