"""
Judge0 Worker
큐에서 코드 실행 작업을 가져와서 Judge0 API로 실행하고 결과를 저장
"""
import asyncio
import logging
import uuid
from typing import Optional

from app.domain.queue import create_queue_adapter, JudgeTask, JudgeResult
from app.infrastructure.judge0.client import Judge0Client
from app.core.config import settings


logger = logging.getLogger(__name__)


class JudgeWorker:
    """Judge0 코드 실행 Worker"""
    
    def __init__(self):
        self.queue = create_queue_adapter()
        self.judge0_client = Judge0Client()
        self.running = False
    
    async def start(self):
        """Worker 시작"""
        self.running = True
        logger.info("[JudgeWorker] Worker 시작")
        
        try:
            await self._worker_loop()
        except KeyboardInterrupt:
            logger.info("[JudgeWorker] Worker 중지 요청 수신")
        except Exception as e:
            logger.error(f"[JudgeWorker] Worker 오류: {str(e)}", exc_info=True)
        finally:
            await self.stop()
    
    async def stop(self):
        """Worker 중지"""
        self.running = False
        await self.judge0_client.close()
        logger.info("[JudgeWorker] Worker 중지")
    
    async def _worker_loop(self):
        """Worker 메인 루프"""
        while self.running:
            try:
                # 큐에서 작업 가져오기
                task = await self.queue.dequeue()
                
                if task is None:
                    # 큐가 비어있으면 잠시 대기
                    await asyncio.sleep(0.1)
                    continue
                
                logger.info(f"[JudgeWorker] 작업 처리 시작 - task_id: {task.task_id}")
                
                # 상태를 "processing"으로 변경
                await self.queue.set_status(task.task_id, "processing")
                
                # 코드 실행
                result = await self._execute_task(task)
                
                # 결과 저장
                await self.queue.save_result(task.task_id, result)
                
                logger.info(
                    f"[JudgeWorker] 작업 완료 - task_id: {task.task_id}, "
                    f"status: {result.status}, time: {result.execution_time}s"
                )
                
            except Exception as e:
                logger.error(f"[JudgeWorker] 작업 처리 중 오류: {str(e)}", exc_info=True)
                
                # 에러 발생 시 실패 결과 저장
                if task:
                    error_result = JudgeResult(
                        task_id=task.task_id,
                        status="error",
                        output="",
                        error=str(e),
                        execution_time=0.0,
                        memory_used=0,
                        exit_code=1
                    )
                    try:
                        await self.queue.save_result(task.task_id, error_result)
                    except Exception as save_error:
                        logger.error(f"[JudgeWorker] 결과 저장 실패: {str(save_error)}")
    
    async def _execute_task(self, task: JudgeTask) -> JudgeResult:
        """
        Judge0 API를 사용하여 코드 실행
        
        Args:
            task: 실행할 태스크
            
        Returns:
            실행 결과
        """
        try:
            # 테스트 케이스가 있는 경우
            if task.test_cases:
                # 여러 테스트 케이스 실행
                test_case_results = await self.judge0_client.execute_test_cases(
                    code=task.code,
                    language=task.language,
                    test_cases=[
                        {
                            "input": tc.get("input", "") if isinstance(tc, dict) else str(tc),
                            "expected": tc.get("expected") if isinstance(tc, dict) else None
                        }
                        for tc in task.test_cases
                    ],
                    cpu_time_limit=task.timeout,
                    memory_limit=task.memory_limit
                )
                
                # 결과 집계
                passed_count = sum(1 for r in test_case_results if r["passed"])
                total_count = len(test_case_results)
                
                # 실행 시간 및 메모리 (최대값)
                max_time = max(float(r.get("time", "0")) for r in test_case_results)
                max_memory = max(int(r.get("memory", "0")) for r in test_case_results)
                
                # 상태 결정
                if passed_count == total_count:
                    status = "success"
                    error = None
                else:
                    status = "error"
                    failed_tests = [r for r in test_case_results if not r["passed"]]
                    error = f"{total_count - passed_count}/{total_count} 테스트 실패: {failed_tests[0].get('status_description', 'Unknown error')}"
                
                # 출력 (모든 테스트 케이스 결과)
                output_lines = []
                for i, r in enumerate(test_case_results):
                    output_lines.append(f"Test {i+1}: {r['status_description']}")
                    if r.get("actual"):
                        output_lines.append(f"  Output: {r['actual']}")
                    if r.get("stderr"):
                        output_lines.append(f"  Error: {r['stderr']}")
                output = "\n".join(output_lines)
                
                return JudgeResult(
                    task_id=task.task_id,
                    status=status,
                    output=output,
                    error=error,
                    execution_time=max_time,
                    memory_used=max_memory * 1024,  # KB -> bytes
                    exit_code=0 if status == "success" else 1
                )
            
            else:
                # 단일 실행 (테스트 케이스 없음)
                result = await self.judge0_client.execute_code(
                    code=task.code,
                    language=task.language,
                    stdin="",
                    cpu_time_limit=task.timeout,
                    memory_limit=task.memory_limit,
                    wait=True
                )
                
                # Judge0 결과를 JudgeResult로 변환
                status_id = result.get("status", {}).get("id")
                
                if status_id == 3:  # Accepted
                    status = "success"
                    error = None
                elif status_id == 5:  # Time Limit Exceeded
                    status = "timeout"
                    error = "Time limit exceeded"
                elif status_id == 6:  # Compilation Error
                    status = "error"
                    error = result.get("compile_output", "Compilation error")
                else:
                    status = "error"
                    error = result.get("stderr") or result.get("status", {}).get("description", "Unknown error")
                
                return JudgeResult(
                    task_id=task.task_id,
                    status=status,
                    output=result.get("stdout", ""),
                    error=error,
                    execution_time=float(result.get("time", "0")),
                    memory_used=int(result.get("memory", "0")) * 1024,  # KB -> bytes
                    exit_code=0 if status == "success" else 1
                )
                
        except asyncio.TimeoutError:
            return JudgeResult(
                task_id=task.task_id,
                status="timeout",
                output="",
                error="Judge0 API 호출 타임아웃",
                execution_time=task.timeout,
                memory_used=0,
                exit_code=1
            )
        except Exception as e:
            logger.error(f"[JudgeWorker] Judge0 API 호출 실패: {str(e)}", exc_info=True)
            return JudgeResult(
                task_id=task.task_id,
                status="error",
                output="",
                error=f"Judge0 API 오류: {str(e)}",
                execution_time=0.0,
                memory_used=0,
                exit_code=1
            )


async def main():
    """Worker 메인 함수"""
    worker = JudgeWorker()
    await worker.start()


if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Worker 실행
    asyncio.run(main())

