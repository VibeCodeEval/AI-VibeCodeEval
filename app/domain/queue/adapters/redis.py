"""
Redis 기반 큐 어댑터 (프로덕션용)
"""
import json
from typing import Optional

from app.domain.queue.adapters.base import QueueAdapter, JudgeTask, JudgeResult
from app.infrastructure.cache.redis_client import RedisClient


class RedisQueueAdapter(QueueAdapter):
    """Redis 기반 큐 (프로덕션용)"""
    
    def __init__(self, redis: RedisClient):
        """
        Args:
            redis: Redis 클라이언트 인스턴스
        """
        self.redis = redis
        self.queue_key = "judge_queue:pending"
        self.result_prefix = "judge_result:"
        self.status_prefix = "judge_status:"
        self.default_ttl = 3600  # 1시간
    
    def _task_to_dict(self, task: JudgeTask) -> dict:
        """JudgeTask를 딕셔너리로 변환"""
        return {
            "task_id": task.task_id,
            "code": task.code,
            "language": task.language,
            "test_cases": task.test_cases,
            "timeout": task.timeout,
            "memory_limit": task.memory_limit,
            "meta": task.meta or {}
        }
    
    def _dict_to_task(self, data: dict) -> JudgeTask:
        """딕셔너리를 JudgeTask로 변환"""
        return JudgeTask(
            task_id=data["task_id"],
            code=data["code"],
            language=data["language"],
            test_cases=data["test_cases"],
            timeout=data.get("timeout", 5),
            memory_limit=data.get("memory_limit", 128),
            meta=data.get("meta")
        )
    
    def _result_to_dict(self, result: JudgeResult) -> dict:
        """JudgeResult를 딕셔너리로 변환"""
        return {
            "task_id": result.task_id,
            "status": result.status,
            "output": result.output,
            "error": result.error,
            "execution_time": result.execution_time,
            "memory_used": result.memory_used,
            "exit_code": result.exit_code
        }
    
    def _dict_to_result(self, data: dict) -> JudgeResult:
        """딕셔너리를 JudgeResult로 변환"""
        return JudgeResult(
            task_id=data["task_id"],
            status=data["status"],
            output=data.get("output", ""),
            error=data.get("error"),
            execution_time=data.get("execution_time", 0.0),
            memory_used=data.get("memory_used", 0),
            exit_code=data.get("exit_code", 0)
        )
    
    async def enqueue(self, task: JudgeTask) -> str:
        """Redis List에 태스크 추가"""
        task_dict = self._task_to_dict(task)
        task_json = json.dumps(task_dict, ensure_ascii=False)
        
        # 큐에 추가 (LPUSH) - RedisClient를 통해 직접 접근
        await self.redis.client.lpush(self.queue_key, task_json)
        
        # 상태 저장
        await self.redis.set(
            f"{self.status_prefix}{task.task_id}",
            "pending",
            ttl_seconds=self.default_ttl
        )
        
        return task.task_id
    
    async def dequeue(self) -> Optional[JudgeTask]:
        """Redis List에서 태스크 가져오기 (BLPOP - 블로킹)"""
        # BLPOP: 큐가 비어있으면 최대 1초 대기
        result = await self.redis.client.brpop(self.queue_key, timeout=1)
        
        if result:
            _, task_json = result
            task_data = json.loads(task_json)
            task = self._dict_to_task(task_data)
            
            # 상태를 "processing"으로 변경
            await self.redis.set(
                f"{self.status_prefix}{task.task_id}",
                "processing",
                ttl_seconds=self.default_ttl
            )
            
            return task
        
        return None
    
    async def get_result(self, task_id: str) -> Optional[JudgeResult]:
        """Redis에서 결과 조회"""
        result_json = await self.redis.get(f"{self.result_prefix}{task_id}")
        
        if result_json:
            result_data = json.loads(result_json)
            return self._dict_to_result(result_data)
        
        return None
    
    async def get_status(self, task_id: str) -> str:
        """Redis에서 상태 조회"""
        status = await self.redis.get(f"{self.status_prefix}{task_id}")
        
        if status:
            return status
        return "unknown"
    
    async def save_result(self, task_id: str, result: JudgeResult) -> bool:
        """Redis에 결과 저장"""
        result_dict = self._result_to_dict(result)
        result_json = json.dumps(result_dict, ensure_ascii=False)
        
        # 결과 저장
        await self.redis.set(
            f"{self.result_prefix}{task_id}",
            result_json,
            ttl_seconds=self.default_ttl
        )
        
        # 상태 업데이트
        status = "completed" if result.status == "success" else "failed"
        await self.redis.set(
            f"{self.status_prefix}{task_id}",
            status,
            ttl_seconds=self.default_ttl
        )
        
        return True
    
    async def set_status(self, task_id: str, status: str) -> bool:
        """Redis에 상태 설정"""
        await self.redis.set(
            f"{self.status_prefix}{task_id}",
            status,
            ttl_seconds=self.default_ttl
        )
        return True

