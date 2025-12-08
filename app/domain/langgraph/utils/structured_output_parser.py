"""
구조화된 출력 파싱 유틸리티

원본 LLM 응답을 JSON으로 파싱하여 Pydantic 모델로 변환
"""
import json
import re
import logging
from typing import TypeVar, Type, Optional, Any
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)


def extract_json_from_content(content: str) -> Optional[dict]:
    """
    LLM 응답에서 JSON 추출
    
    LLM이 마크다운 코드 블록(```json ... ```)으로 감싸서 응답할 수 있으므로
    다양한 형식에서 JSON을 추출합니다.
    
    Args:
        content: LLM 응답 내용
    
    Returns:
        파싱된 JSON 딕셔너리 또는 None
    """
    if not content:
        return None
    
    # 방법 1: 마크다운 코드 블록에서 JSON 추출
    json_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
    if json_block_match:
        try:
            return json.loads(json_block_match.group(1))
        except json.JSONDecodeError:
            pass
    
    # 방법 2: 첫 번째 { } 쌍 찾기
    json_match = re.search(r'\{.*\}', content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    # 방법 3: 전체 내용이 JSON인 경우
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError:
        pass
    
    return None


def parse_structured_output(
    raw_response: Any,
    model_class: Type[T],
    fallback_llm: Optional[Any] = None,
    formatted_messages: Optional[list] = None
) -> T:
    """
    원본 LLM 응답을 구조화된 출력(Pydantic 모델)으로 파싱
    
    Args:
        raw_response: 원본 LLM 응답 객체
        model_class: Pydantic 모델 클래스
        fallback_llm: 파싱 실패 시 사용할 구조화된 출력 LLM (선택)
        formatted_messages: 파싱 실패 시 재호출에 사용할 메시지 (선택)
    
    Returns:
        Pydantic 모델 인스턴스
    
    Raises:
        ValueError: 파싱 실패 및 fallback도 실패한 경우
    """
    # 원본 응답에서 content 추출
    if hasattr(raw_response, 'content'):
        content = raw_response.content
    elif isinstance(raw_response, str):
        content = raw_response
    else:
        content = str(raw_response)
    
    # JSON 추출
    parsed_json = extract_json_from_content(content)
    
    if parsed_json:
        try:
            # Pydantic 모델로 변환 (model_validator 포함)
            return model_class(**parsed_json)
        except ValidationError as e:
            logger.warning(f"[Structured Output Parser] Pydantic 검증 실패: {e}")
            # 검증 실패 시에도 fallback 시도
            if fallback_llm and formatted_messages:
                logger.info("[Structured Output Parser] Fallback: with_structured_output 사용")
                import asyncio
                if asyncio.iscoroutinefunction(fallback_llm.ainvoke):
                    # 비동기 함수인 경우 (실제로는 호출하지 않고 에러 발생)
                    raise ValueError(f"비동기 fallback은 지원하지 않습니다. 파싱 실패: {e}")
                else:
                    return fallback_llm.invoke(formatted_messages)
            raise ValueError(f"구조화된 출력 파싱 실패: {e}")
    else:
        # JSON 추출 실패
        logger.warning(f"[Structured Output Parser] JSON 추출 실패 - content: {content[:200]}...")
        if fallback_llm and formatted_messages:
            logger.info("[Structured Output Parser] Fallback: with_structured_output 사용")
            import asyncio
            if asyncio.iscoroutinefunction(fallback_llm.ainvoke):
                raise ValueError("비동기 fallback은 지원하지 않습니다. JSON 추출 실패")
            else:
                return fallback_llm.invoke(formatted_messages)
        raise ValueError("JSON 추출 실패 및 fallback 불가")


async def parse_structured_output_async(
    raw_response: Any,
    model_class: Type[T],
    fallback_llm: Optional[Any] = None,
    formatted_messages: Optional[list] = None
) -> T:
    """
    원본 LLM 응답을 구조화된 출력(Pydantic 모델)으로 파싱 (비동기 버전)
    
    Args:
        raw_response: 원본 LLM 응답 객체
        model_class: Pydantic 모델 클래스
        fallback_llm: 파싱 실패 시 사용할 구조화된 출력 LLM (선택)
        formatted_messages: 파싱 실패 시 재호출에 사용할 메시지 (선택)
    
    Returns:
        Pydantic 모델 인스턴스
    
    Raises:
        ValueError: 파싱 실패 및 fallback도 실패한 경우
    """
    # 원본 응답에서 content 추출
    if hasattr(raw_response, 'content'):
        content = raw_response.content
    elif isinstance(raw_response, str):
        content = raw_response
    else:
        content = str(raw_response)
    
    # JSON 추출
    parsed_json = extract_json_from_content(content)
    
    if parsed_json:
        try:
            # Pydantic 모델로 변환 (model_validator 포함)
            return model_class(**parsed_json)
        except ValidationError as e:
            logger.warning(f"[Structured Output Parser] Pydantic 검증 실패: {e}")
            # 검증 실패 시에도 fallback 시도
            if fallback_llm and formatted_messages:
                logger.info("[Structured Output Parser] Fallback: with_structured_output 사용 (비동기)")
                return await fallback_llm.ainvoke(formatted_messages)
            raise ValueError(f"구조화된 출력 파싱 실패: {e}")
    else:
        # JSON 추출 실패 (정상적인 경우: LLM이 일반 텍스트로 응답했지만 fallback으로 처리)
        logger.debug(f"[Structured Output Parser] JSON 추출 실패 (fallback 사용) - content: {content[:100]}...")
        if fallback_llm and formatted_messages:
            logger.debug("[Structured Output Parser] Fallback: with_structured_output 사용 (비동기)")
            return await fallback_llm.ainvoke(formatted_messages)
        raise ValueError("JSON 추출 실패 및 fallback 불가")

