"""
Judge0 API 클라이언트
코드 실행 및 결과 조회
"""
import httpx
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.core.config import settings


logger = logging.getLogger(__name__)


class Judge0Client:
    """Judge0 API 클라이언트"""
    
    # 언어 ID 매핑
    LANGUAGE_IDS = {
        "python": 71,
        "python3": 71,
        "java": 62,
        "cpp": 54,
        "c++": 54,
        "c": 50,
        "javascript": 63,
        "nodejs": 63,
        "go": 60,
        "rust": 73,
    }
    
    def __init__(
        self, 
        api_url: Optional[str] = None, 
        api_key: Optional[str] = None,
        use_rapidapi: Optional[bool] = None,
        rapidapi_host: Optional[str] = None
    ):
        """
        Args:
            api_url: Judge0 API URL (기본값: settings.JUDGE0_API_URL)
            api_key: Judge0 API Key (기본값: settings.JUDGE0_API_KEY)
            use_rapidapi: RapidAPI 사용 여부 (기본값: settings.JUDGE0_USE_RAPIDAPI)
            rapidapi_host: RapidAPI Host (기본값: settings.JUDGE0_RAPIDAPI_HOST)
        """
        self.api_url = (api_url or settings.JUDGE0_API_URL).rstrip('/')
        self.api_key = api_key or settings.JUDGE0_API_KEY
        self.use_rapidapi = use_rapidapi if use_rapidapi is not None else settings.JUDGE0_USE_RAPIDAPI
        self.rapidapi_host = rapidapi_host or settings.JUDGE0_RAPIDAPI_HOST
        self.client = httpx.AsyncClient(timeout=30.0)
    
    def _get_language_id(self, language: str) -> int:
        """
        언어 이름을 Judge0 언어 ID로 변환
        
        Args:
            language: 언어 이름 (예: "python", "java")
            
        Returns:
            언어 ID (기본값: 71 = Python 3)
        """
        return self.LANGUAGE_IDS.get(language.lower(), 71)
    
    def _get_headers(self) -> Dict[str, str]:
        """요청 헤더 생성"""
        headers = {
            "Content-Type": "application/json",
        }
        
        if self.use_rapidapi:
            # RapidAPI 형식
            if self.api_key:
                headers["x-rapidapi-key"] = self.api_key
            headers["x-rapidapi-host"] = self.rapidapi_host
        else:
            # 일반 Judge0 형식
            if self.api_key:
                headers["X-Auth-Token"] = self.api_key
        
        return headers
    
    async def submit_code(
        self,
        code: str,
        language: str,
        stdin: str = "",
        expected_output: Optional[str] = None,
        cpu_time_limit: int = 5,
        memory_limit: int = 128,  # MB
        wait: bool = False
    ) -> str:
        """
        코드 제출
        
        Args:
            code: 실행할 소스 코드
            language: 프로그래밍 언어 (예: "python", "java")
            stdin: 표준 입력 데이터 (테스트 케이스 입력)
            expected_output: 예상 출력 (정확성 평가용)
            cpu_time_limit: CPU 시간 제한 (초)
            memory_limit: 메모리 제한 (MB)
            wait: 동기 대기 여부 (True면 결과까지 대기)
            
        Returns:
            submission token
        """
        language_id = self._get_language_id(language)
        
        payload = {
            "source_code": code,
            "language_id": language_id,
            "stdin": stdin,
            "cpu_time_limit": cpu_time_limit,
            "memory_limit": memory_limit * 1024,  # MB -> KB
        }
        
        if expected_output:
            payload["expected_output"] = expected_output
        
        params = {
            "base64_encoded": "false",
            "wait": "true" if wait else "false"
        }
        
        try:
            response = await self.client.post(
                f"{self.api_url}/submissions",
                json=payload,
                params=params,
                headers=self._get_headers()
            )
            response.raise_for_status()
            
            result = response.json()
            token = result.get("token")
            
            if not token:
                raise ValueError(f"Judge0 API 응답에 token이 없습니다: {result}")
            
            logger.info(f"[Judge0] 코드 제출 완료 - token: {token}, language: {language}")
            return token
            
        except httpx.HTTPStatusError as e:
            logger.error(f"[Judge0] HTTP 에러 - status: {e.response.status_code}, response: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"[Judge0] 코드 제출 실패: {str(e)}")
            raise
    
    async def get_result(
        self,
        token: str,
        base64_encoded: bool = False
    ) -> Dict[str, Any]:
        """
        실행 결과 조회
        
        Args:
            token: submission token
            base64_encoded: 결과가 base64 인코딩되어 있는지 여부
            
        Returns:
            실행 결과 딕셔너리
        """
        try:
            response = await self.client.get(
                f"{self.api_url}/submissions/{token}",
                params={"base64_encoded": "true" if base64_encoded else "false"},
                headers=self._get_headers()
            )
            response.raise_for_status()
            
            result = response.json()
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"[Judge0] 결과 조회 HTTP 에러 - token: {token}, status: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"[Judge0] 결과 조회 실패 - token: {token}, error: {str(e)}")
            raise
    
    async def wait_for_result(
        self,
        token: str,
        max_wait: int = 30,
        poll_interval: float = 0.5
    ) -> Dict[str, Any]:
        """
        결과가 나올 때까지 대기 (폴링)
        
        Args:
            token: submission token
            max_wait: 최대 대기 시간 (초)
            poll_interval: 폴링 간격 (초)
            
        Returns:
            실행 결과 딕셔너리
        """
        start_time = datetime.now().timestamp()
        
        while True:
            result = await self.get_result(token)
            status_id = result.get("status", {}).get("id")
            
            # 상태 ID 설명:
            # 1: In Queue, 2: Processing
            # 3: Accepted (성공)
            # 4-15: 에러 (Wrong Answer, Time Limit, Runtime Error 등)
            
            if status_id == 3:  # Accepted
                logger.info(f"[Judge0] 실행 성공 - token: {token}")
                return result
            elif status_id >= 4:  # 에러
                logger.warning(f"[Judge0] 실행 실패 - token: {token}, status_id: {status_id}")
                return result
            
            # 타임아웃 체크
            elapsed = datetime.now().timestamp() - start_time
            if elapsed >= max_wait:
                logger.warning(f"[Judge0] 결과 대기 타임아웃 - token: {token}, elapsed: {elapsed}초")
                return result
            
            # 대기
            await asyncio.sleep(poll_interval)
    
    async def execute_code(
        self,
        code: str,
        language: str,
        stdin: str = "",
        expected_output: Optional[str] = None,
        cpu_time_limit: int = 5,
        memory_limit: int = 128,
        wait: bool = True
    ) -> Dict[str, Any]:
        """
        코드 실행 (제출 + 결과 대기)
        
        Args:
            code: 실행할 소스 코드
            language: 프로그래밍 언어
            stdin: 표준 입력
            expected_output: 예상 출력
            cpu_time_limit: CPU 시간 제한 (초)
            memory_limit: 메모리 제한 (MB)
            wait: 결과 대기 여부
            
        Returns:
            실행 결과 딕셔너리
        """
        token = await self.submit_code(
            code=code,
            language=language,
            stdin=stdin,
            expected_output=expected_output,
            cpu_time_limit=cpu_time_limit,
            memory_limit=memory_limit,
            wait=False  # 항상 비동기로 제출
        )
        
        if wait:
            return await self.wait_for_result(token)
        else:
            return {"token": token}
    
    async def execute_test_cases(
        self,
        code: str,
        language: str,
        test_cases: List[Dict[str, str]],
        cpu_time_limit: int = 5,
        memory_limit: int = 128
    ) -> List[Dict[str, Any]]:
        """
        여러 테스트 케이스 실행
        
        Args:
            code: 실행할 소스 코드
            language: 프로그래밍 언어
            test_cases: 테스트 케이스 리스트 [{"input": "...", "expected": "..."}, ...]
            cpu_time_limit: CPU 시간 제한 (초)
            memory_limit: 메모리 제한 (MB)
            
        Returns:
            각 테스트 케이스의 실행 결과 리스트
        """
        results = []
        
        for i, test_case in enumerate(test_cases):
            logger.info(f"[Judge0] 테스트 케이스 {i+1}/{len(test_cases)} 실행 중...")
            
            try:
                result = await self.execute_code(
                    code=code,
                    language=language,
                    stdin=test_case.get("input", ""),
                    expected_output=test_case.get("expected"),
                    cpu_time_limit=cpu_time_limit,
                    memory_limit=memory_limit,
                    wait=True
                )
                
                # 결과 분석
                status_id = result.get("status", {}).get("id")
                passed = (
                    status_id == 3 and  # Accepted
                    result.get("stdout", "").strip() == (test_case.get("expected", "").strip() if test_case.get("expected") else "")
                )
                
                results.append({
                    "test_case_index": i,
                    "input": test_case.get("input", ""),
                    "expected": test_case.get("expected", ""),
                    "actual": result.get("stdout", "").strip(),
                    "passed": passed,
                    "status_id": status_id,
                    "status_description": result.get("status", {}).get("description", ""),
                    "time": result.get("time", "0"),
                    "memory": result.get("memory", "0"),
                    "stderr": result.get("stderr"),
                    "compile_output": result.get("compile_output"),
                })
                
            except Exception as e:
                logger.error(f"[Judge0] 테스트 케이스 {i+1} 실행 실패: {str(e)}")
                results.append({
                    "test_case_index": i,
                    "input": test_case.get("input", ""),
                    "expected": test_case.get("expected", ""),
                    "actual": "",
                    "passed": False,
                    "status_id": 14,  # Internal Error
                    "status_description": f"Error: {str(e)}",
                    "time": "0",
                    "memory": "0",
                    "stderr": str(e),
                    "compile_output": None,
                })
        
        return results
    
    async def close(self):
        """클라이언트 종료"""
        await self.client.aclose()


