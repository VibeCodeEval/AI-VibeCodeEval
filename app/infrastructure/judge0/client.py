"""
Judge0 API 클라이언트
코드 실행 및 결과 조회
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.infrastructure.judge0.utils import (
    judge0_decode_submission_result,
    judge0_encode_submission_payload,
)

logger = logging.getLogger(__name__)

# Judge0 CE: 제어 문자·JSON 깨짐 방지 — 전송/수신 모두 Base64, 앱 내부·DB는 평문
_BASE64_PARAMS = {"base64_encoded": "true"}

# Judge0 status_id: 1=In Queue, 2=Processing, 3=Accepted, 4+=terminal errors
_STATUS_IN_QUEUE = 1
_STATUS_PROCESSING = 2
_STATUS_ACCEPTED = 3


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
        rapidapi_host: Optional[str] = None,
    ):
        """
        Args:
            api_url: Judge0 API URL (기본값: settings.JUDGE0_API_URL)
            api_key: Judge0 API Key (기본값: settings.JUDGE0_API_KEY)
            use_rapidapi: RapidAPI 사용 여부 (기본값: settings.JUDGE0_USE_RAPIDAPI)
            rapidapi_host: RapidAPI Host (기본값: settings.JUDGE0_RAPIDAPI_HOST)
        """
        self.api_url = (api_url or settings.JUDGE0_API_URL).rstrip("/")
        self.api_key = api_key or settings.JUDGE0_API_KEY
        self.use_rapidapi = (
            use_rapidapi if use_rapidapi is not None else settings.JUDGE0_USE_RAPIDAPI
        )
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

    @staticmethod
    def _status_id_from_result(result: Dict[str, Any]) -> Optional[int]:
        """단건/배치 응답에서 status_id 추출 (status.id 또는 status_id)."""
        if not result:
            return None
        if result.get("status_id") is not None:
            try:
                return int(result["status_id"])
            except (TypeError, ValueError):
                pass
        status = result.get("status")
        if isinstance(status, dict) and status.get("id") is not None:
            try:
                return int(status["id"])
            except (TypeError, ValueError):
                pass
        return None

    @staticmethod
    def _is_terminal_status(status_id: Optional[int]) -> bool:
        if status_id is None:
            return False
        return status_id not in (_STATUS_IN_QUEUE, _STATUS_PROCESSING)

    def _build_submission_payload(
        self,
        code: str,
        language_id: int,
        stdin: str,
        expected_output: Optional[str],
        cpu_time_limit: int,
        memory_limit: int,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "source_code": code,
            "language_id": language_id,
            "stdin": stdin or "",
            "cpu_time_limit": cpu_time_limit,
            "memory_limit": memory_limit * 1024,  # MB -> KB
        }
        if expected_output is not None and expected_output != "":
            payload["expected_output"] = expected_output
        return payload

    def _encode_payload_for_api(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return judge0_encode_submission_payload(payload)

    def _decode_api_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        return judge0_decode_submission_result(result)

    def _map_judge0_result_to_test_case(
        self,
        test_case: Dict[str, str],
        test_case_index: int,
        result: Optional[Dict[str, Any]],
        *,
        error_message: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Judge0 실행 결과 → Worker/judge_worker가 기대하는 TC 결과 dict."""
        if error_message or result is None:
            msg = error_message or "Judge0 결과 없음"
            return {
                "test_case_index": test_case_index,
                "input": test_case.get("input", ""),
                "expected": test_case.get("expected", ""),
                "actual": "",
                "passed": False,
                "status_id": 14,
                "status_description": f"Error: {msg}",
                "time": "0",
                "memory": "0",
                "stderr": msg,
                "compile_output": None,
            }

        status_id = self._status_id_from_result(result)
        actual_stdout = (result.get("stdout") or "").strip()
        expected_stdout = (
            (test_case.get("expected") or "").strip()
            if test_case.get("expected")
            else ""
        )
        passed = status_id == _STATUS_ACCEPTED and actual_stdout == expected_stdout
        status_obj = result.get("status") if isinstance(result.get("status"), dict) else {}
        status_description = status_obj.get("description") or result.get("message") or ""

        return {
            "test_case_index": test_case_index,
            "input": test_case.get("input", ""),
            "expected": test_case.get("expected", ""),
            "actual": actual_stdout,
            "passed": passed,
            "status_id": status_id if status_id is not None else 14,
            "status_description": status_description,
            "time": result.get("time", "0"),
            "memory": result.get("memory", "0"),
            "stderr": result.get("stderr"),
            "compile_output": result.get("compile_output"),
        }

    async def submit_code(
        self,
        code: str,
        language: str,
        stdin: str = "",
        expected_output: Optional[str] = None,
        cpu_time_limit: int = 5,
        memory_limit: int = 128,  # MB
        wait: bool = False,
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

        payload = self._encode_payload_for_api(
            self._build_submission_payload(
                code=code,
                language_id=language_id,
                stdin=stdin,
                expected_output=expected_output,
                cpu_time_limit=cpu_time_limit,
                memory_limit=memory_limit,
            )
        )

        params = {**_BASE64_PARAMS, "wait": "true" if wait else "false"}

        try:
            response = await self.client.post(
                f"{self.api_url}/submissions",
                json=payload,
                params=params,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            result = response.json()
            if wait and isinstance(result, dict):
                result = self._decode_api_result(result)

            token = result.get("token") if isinstance(result, dict) else None

            if not token:
                raise ValueError(f"Judge0 API 응답에 token이 없습니다: {result}")

            logger.info(
                f"[Judge0] 코드 제출 완료 - token: {token}, language: {language}"
            )
            return token

        except httpx.HTTPStatusError as e:
            logger.error(
                f"[Judge0] HTTP 에러 - status: {e.response.status_code}, response: {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"[Judge0] 코드 제출 실패: {str(e)}")
            raise

    async def submit_batch(
        self,
        code: str,
        language: str,
        test_cases: List[Dict[str, str]],
        cpu_time_limit: int = 5,
        memory_limit: int = 128,
    ) -> List[Optional[str]]:
        """
        POST /submissions/batch — TC마다 submission 1개, HTTP 요청 1회.

        Returns:
            test_cases와 동일 순서의 token 리스트 (생성 실패 시 None)
        """
        language_id = self._get_language_id(language)
        submissions = [
            self._encode_payload_for_api(
                self._build_submission_payload(
                    code=code,
                    language_id=language_id,
                    stdin=tc.get("input", "") or "",
                    expected_output=tc.get("expected") or None,
                    cpu_time_limit=cpu_time_limit,
                    memory_limit=memory_limit,
                )
            )
            for tc in test_cases
        ]

        try:
            response = await self.client.post(
                f"{self.api_url}/submissions/batch",
                json={"submissions": submissions},
                params=_BASE64_PARAMS,
                headers=self._get_headers(),
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as e:
            logger.error(
                f"[Judge0] Batch 제출 HTTP 에러 - status: {e.response.status_code}, "
                f"response: {e.response.text}"
            )
            raise
        except Exception as e:
            logger.error(f"[Judge0] Batch 제출 실패: {str(e)}")
            raise

        if not isinstance(body, list):
            raise ValueError(f"Judge0 batch 응답 형식 오류 (list 기대): {body}")

        tokens: List[Optional[str]] = []
        for idx, item in enumerate(body):
            if isinstance(item, dict) and item.get("token"):
                tokens.append(str(item["token"]))
            else:
                tokens.append(None)
                logger.warning(
                    f"[Judge0] Batch 항목 {idx + 1} token 없음 - 응답: {item}"
                )

        while len(tokens) < len(test_cases):
            tokens.append(None)

        logger.info(
            f"[Judge0] Batch 제출 완료 - {len(test_cases)}건, "
            f"token 확보 {sum(1 for t in tokens if t)}/{len(test_cases)}"
        )
        return tokens[: len(test_cases)]

    async def get_batch_results(self, tokens: List[str]) -> Dict[str, Dict[str, Any]]:
        """GET /submissions/batch — token별 최신 submission 결과."""
        if not tokens:
            return {}

        fields = (
            "token,stdout,stderr,status_id,status,time,memory,"
            "compile_output,message,expected_output"
        )
        params = {
            "tokens": ",".join(tokens),
            "fields": fields,
            **_BASE64_PARAMS,
        }

        response = await self.client.get(
            f"{self.api_url}/submissions/batch",
            params=params,
            headers=self._get_headers(),
        )
        response.raise_for_status()
        body = response.json()

        submissions = body.get("submissions") if isinstance(body, dict) else body
        if not isinstance(submissions, list):
            raise ValueError(f"Judge0 batch 조회 응답 형식 오류: {body}")

        by_token: Dict[str, Dict[str, Any]] = {}
        for item in submissions:
            if isinstance(item, dict) and item.get("token"):
                by_token[str(item["token"])] = self._decode_api_result(item)
        return by_token

    async def wait_for_batch_results(
        self,
        tokens: List[str],
        max_wait: int = 30,
        poll_interval: float = 0.5,
    ) -> Dict[str, Dict[str, Any]]:
        """배치 토큰 전부 terminal status가 될 때까지 GET /submissions/batch 폴링."""
        valid_tokens = [t for t in tokens if t]
        if not valid_tokens:
            return {}

        pending = set(valid_tokens)
        results_by_token: Dict[str, Dict[str, Any]] = {}
        start_time = datetime.now().timestamp()

        while pending and (datetime.now().timestamp() - start_time) < max_wait:
            try:
                batch_map = await self.get_batch_results(list(pending))
            except Exception as e:
                logger.warning(f"[Judge0] Batch 조회 실패: {e}")
                await asyncio.sleep(poll_interval)
                continue

            for token in list(pending):
                result = batch_map.get(token)
                if not result:
                    continue
                status_id = self._status_id_from_result(result)
                if self._is_terminal_status(status_id):
                    results_by_token[token] = result
                    pending.discard(token)

            if pending:
                await asyncio.sleep(poll_interval)

        if pending:
            logger.warning(
                f"[Judge0] Batch 결과 대기 타임아웃 - 미완료 {len(pending)}건, "
                f"max_wait={max_wait}s"
            )
            try:
                batch_map = await self.get_batch_results(list(pending))
                for token in pending:
                    if token in batch_map:
                        results_by_token[token] = batch_map[token]
            except Exception as e:
                logger.warning(f"[Judge0] 타임아웃 후 Batch 조회 실패: {e}")

        return results_by_token

    async def get_result(self, token: str) -> Dict[str, Any]:
        """
        실행 결과 조회 (항상 base64_encoded=true, 반환값은 평문 디코딩됨).
        """
        try:
            response = await self.client.get(
                f"{self.api_url}/submissions/{token}",
                params=_BASE64_PARAMS,
                headers=self._get_headers(),
            )
            response.raise_for_status()

            result = response.json()
            return self._decode_api_result(result) if isinstance(result, dict) else result

        except httpx.HTTPStatusError as e:
            logger.error(
                f"[Judge0] 결과 조회 HTTP 에러 - token: {token}, status: {e.response.status_code}"
            )
            raise
        except Exception as e:
            logger.error(f"[Judge0] 결과 조회 실패 - token: {token}, error: {str(e)}")
            raise

    async def wait_for_result(
        self, token: str, max_wait: int = 30, poll_interval: float = 0.5
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
            status_id = self._status_id_from_result(result)

            if status_id == _STATUS_ACCEPTED:
                logger.info(f"[Judge0] 실행 성공 - token: {token}")
                return result
            if status_id is not None and status_id >= 4:
                logger.warning(
                    f"[Judge0] 실행 실패 - token: {token}, status_id: {status_id}"
                )
                return result

            elapsed = datetime.now().timestamp() - start_time
            if elapsed >= max_wait:
                logger.warning(
                    f"[Judge0] 결과 대기 타임아웃 - token: {token}, elapsed: {elapsed}초"
                )
                return result

            await asyncio.sleep(poll_interval)

    async def execute_code(
        self,
        code: str,
        language: str,
        stdin: str = "",
        expected_output: Optional[str] = None,
        cpu_time_limit: int = 5,
        memory_limit: int = 128,
        wait: bool = True,
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
            wait=False,
        )

        if wait:
            return await self.wait_for_result(token)
        return {"token": token}

    async def _execute_single_test_case(
        self,
        code: str,
        language: str,
        test_case: Dict[str, str],
        test_case_index: int,
        cpu_time_limit: int,
        memory_limit: int,
    ) -> Dict[str, Any]:
        """TC 1건 — POST /submissions 단건 + 폴링."""
        try:
            result = await self.execute_code(
                code=code,
                language=language,
                stdin=test_case.get("input", ""),
                expected_output=test_case.get("expected"),
                cpu_time_limit=cpu_time_limit,
                memory_limit=memory_limit,
                wait=True,
            )
            return self._map_judge0_result_to_test_case(
                test_case, test_case_index, result
            )
        except Exception as e:
            logger.error(
                f"[Judge0] 테스트 케이스 {test_case_index + 1} 실행 실패: {str(e)}"
            )
            return self._map_judge0_result_to_test_case(
                test_case,
                test_case_index,
                None,
                error_message=str(e),
            )

    async def _execute_test_cases_batch_chunk(
        self,
        code: str,
        language: str,
        test_cases: List[Dict[str, str]],
        global_index_offset: int,
        cpu_time_limit: int,
        memory_limit: int,
        max_wait: int = 30,
        poll_interval: float = 0.5,
    ) -> List[Dict[str, Any]]:
        """TC 2건 이상 청크 — POST/GET /submissions/batch 각 1회(폴링 포함)."""
        logger.info(
            f"[Judge0] Batch 실행 — TC {len(test_cases)}건 "
            f"(인덱스 {global_index_offset}~{global_index_offset + len(test_cases) - 1})"
        )

        try:
            tokens = await self.submit_batch(
                code=code,
                language=language,
                test_cases=test_cases,
                cpu_time_limit=cpu_time_limit,
                memory_limit=memory_limit,
            )
        except Exception as e:
            return [
                self._map_judge0_result_to_test_case(
                    tc,
                    global_index_offset + i,
                    None,
                    error_message=str(e),
                )
                for i, tc in enumerate(test_cases)
            ]

        results_by_token = await self.wait_for_batch_results(
            [t for t in tokens if t],
            max_wait=max_wait,
            poll_interval=poll_interval,
        )

        chunk_results: List[Dict[str, Any]] = []
        for i, (test_case, token) in enumerate(zip(test_cases, tokens)):
            idx = global_index_offset + i
            if not token:
                chunk_results.append(
                    self._map_judge0_result_to_test_case(
                        test_case,
                        idx,
                        None,
                        error_message="Batch submission token 없음",
                    )
                )
                continue
            raw = results_by_token.get(token)
            chunk_results.append(
                self._map_judge0_result_to_test_case(test_case, idx, raw)
            )
        return chunk_results

    async def execute_test_cases(
        self,
        code: str,
        language: str,
        test_cases: List[Dict[str, str]],
        cpu_time_limit: int = 5,
        memory_limit: int = 128,
    ) -> List[Dict[str, Any]]:
        """
        여러 테스트 케이스 실행.

        - TC 0건: []
        - TC 1건: POST /submissions (Submissions quota)
        - TC 2건 이상: POST/GET /submissions/batch (Batched Submissions quota)

        Returns:
            judge_worker 집계와 동일한 per-TC 결과 리스트 (passed, time, memory, ...)
        """
        if not test_cases:
            return []

        n = len(test_cases)
        if n == 1:
            logger.info("[Judge0] TC 1건 — 단일 submission API 사용")
            return [
                await self._execute_single_test_case(
                    code,
                    language,
                    test_cases[0],
                    0,
                    cpu_time_limit,
                    memory_limit,
                )
            ]

        max_batch = int(settings.JUDGE0_MAX_BATCH_SIZE)
        logger.info(
            f"[Judge0] TC {n}건 — Batched Submissions API 사용 "
            f"(청크 상한 {max_batch})"
        )

        all_results: List[Dict[str, Any]] = []
        for offset in range(0, n, max_batch):
            chunk = test_cases[offset : offset + max_batch]
            chunk_results = await self._execute_test_cases_batch_chunk(
                code=code,
                language=language,
                test_cases=chunk,
                global_index_offset=offset,
                cpu_time_limit=cpu_time_limit,
                memory_limit=memory_limit,
            )
            all_results.extend(chunk_results)
        return all_results

    async def close(self):
        """클라이언트 종료"""
        await self.client.aclose()
