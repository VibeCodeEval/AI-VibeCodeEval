"""
큐 어댑터 인터페이스 정의
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class JudgeTask:
    """코드 실행 태스크"""

    task_id: str
    code: str
    language: str
    test_cases: list
    timeout: int = 5
    memory_limit: int = 128  # MB
    meta: Optional[Dict[str, Any]] = None


@dataclass
class JudgeResult:
    """실행 결과"""

    task_id: str
    status: str  # "success", "timeout", "error", "memory_limit"
    output: str
    error: Optional[str] = None
    execution_time: float = 0.0  # seconds
    memory_used: int = 0  # bytes
    exit_code: int = 0
    # 다중 테스트 케이스 실행 시에만 설정 (부분 통과 점수용)
    passed_test_cases: Optional[int] = None
    total_test_cases: Optional[int] = None
    # Judge0 per-TC 결과 (client._map_judge0_result_to_test_case 형식)
    test_case_results: Optional[List[Dict[str, Any]]] = None


class QueueAdapter(ABC):
    """큐 어댑터 인터페이스"""

    @abstractmethod
    async def enqueue(self, task: JudgeTask) -> str:
        """
        태스크를 큐에 추가

        Args:
            task: 실행할 태스크

        Returns:
            task_id: 태스크 ID
        """
        pass

    @abstractmethod
    async def dequeue(self) -> Optional[JudgeTask]:
        """
        큐에서 태스크를 가져옴

        Returns:
            JudgeTask 또는 None (큐가 비어있을 경우)
        """
        pass

    @abstractmethod
    async def get_result(self, task_id: str) -> Optional[JudgeResult]:
        """
        실행 결과 조회

        Args:
            task_id: 태스크 ID

        Returns:
            JudgeResult 또는 None (결과가 없을 경우)
        """
        pass

    @abstractmethod
    async def get_status(self, task_id: str) -> str:
        """
        태스크 상태 조회

        Args:
            task_id: 태스크 ID

        Returns:
            상태 문자열: "pending", "processing", "completed", "failed", "unknown"
        """
        pass

    @abstractmethod
    async def save_result(self, task_id: str, result: JudgeResult) -> bool:
        """
        실행 결과 저장

        Args:
            task_id: 태스크 ID
            result: 실행 결과

        Returns:
            저장 성공 여부
        """
        pass

    @abstractmethod
    async def set_status(self, task_id: str, status: str) -> bool:
        """
        태스크 상태 설정

        Args:
            task_id: 태스크 ID
            status: 상태 문자열

        Returns:
            설정 성공 여부
        """
        pass
