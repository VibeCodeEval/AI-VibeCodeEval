"""
노드 3.5: Writer Router
LLM 응답 상태에 따른 라우팅
"""
from typing import Literal

from app.langgraph.states import MainGraphState
from app.db.models.enums import WriterResponseStatus


def writer_router(state: MainGraphState) -> Literal[
    "end",
    "eval_turn",
    "handle_failure",
    "summarize_memory",
    "handle_request"
]:
    """
    Writer LLM 응답 상태에 따른 라우팅
    
    라우팅 규칙:
    - SUCCESS: end (답변 생성 완료, 바로 응답 반환)
    - FAILED_TECHNICAL: handle_failure (오류 처리)
    - FAILED_GUARDRAIL: handle_failure (가드레일 위반)
    - FAILED_THRESHOLD: summarize_memory (메모리 요약 후 재시도)
    - FAILED_RATE_LIMIT: handle_request로 돌아가서 재시도
    - FAILED_WRITING: handle_failure
    """
    import logging
    logger = logging.getLogger(__name__)
    
    writer_status = state.get("writer_status")
    is_submitted = state.get("is_submitted", False)
    
    # 제출 요청인 경우에만 평가 진행
    if writer_status == WriterResponseStatus.SUCCESS.value:
        if is_submitted:
            logger.info("[Writer Router] 제출 요청 - eval_turn으로 진행")
            return "eval_turn"
        else:
            logger.info("[Writer Router] 답변 생성 성공 - 바로 응답 반환 (END)")
            return "end"
    
    if writer_status == WriterResponseStatus.FAILED_RATE_LIMIT.value:
        # Rate limit 시 재시도 (일정 대기 후)
        retry_count = state.get("retry_count", 0)
        if retry_count < 3:
            return "handle_request"
        return "handle_failure"
    
    if writer_status == WriterResponseStatus.FAILED_THRESHOLD.value:
        # 토큰 임계값 초과 시 메모리 요약
        return "summarize_memory"
    
    if writer_status in [
        WriterResponseStatus.FAILED_TECHNICAL.value,
        WriterResponseStatus.FAILED_GUARDRAIL.value,
        WriterResponseStatus.FAILED_WRITING.value,
    ]:
        return "handle_failure"
    
    # 기본값
    return "handle_failure"


def intent_router(state: MainGraphState) -> Literal[
    "writer",
    "handle_failure",
    "summarize_memory",
    "handle_request",
    "eval_turn_guard"
]:
    """
    Intent Analyzer 결과에 따른 라우팅
    
    라우팅 규칙:
    - PASSED_HINT: writer (답변 생성)
    - PASSED_SUBMIT: eval_turn_guard (제출 시 4번 가드로)
    - FAILED_GUARDRAIL: handle_failure (가드레일 위반)
    - FAILED_RATE_LIMIT: handle_request (재시도)
    """
    from app.db.models.enums import IntentAnalyzerStatus
    import logging
    logger = logging.getLogger(__name__)
    
    intent_status = state.get("intent_status")
    is_submitted = state.get("is_submitted", False)
    
    # 제출 요청인 경우 4번 가드로
    if is_submitted or intent_status == IntentAnalyzerStatus.PASSED_SUBMIT.value:
        logger.info("[Intent Router] 제출 요청 감지 - eval_turn_guard로 진행")
        return "eval_turn_guard"
    
    if intent_status == IntentAnalyzerStatus.PASSED_HINT.value:
        logger.info("[Intent Router] 일반 채팅 - writer로 진행")
        return "writer"
    
    if intent_status == IntentAnalyzerStatus.FAILED_GUARDRAIL.value:
        logger.warning("[Intent Router] 가드레일 위반 감지 - writer로 교육적 메시지 생성")
        # 가드레일 위반도 writer로 보내서 교육적 거절 메시지 생성
        # 이후 백그라운드 4번 평가로 위반 사실 기록
        return "writer"
    
    if intent_status == IntentAnalyzerStatus.FAILED_RATE_LIMIT.value:
        logger.warning("[Intent Router] Rate limit - handle_request로 재시도")
        return "handle_request"
    
    # 기본값
    logger.info("[Intent Router] 기본값 - writer로 진행")
    return "writer"


def main_router(state: MainGraphState) -> Literal[
    "eval_holistic_flow",
    "handle_request",
    "end"
]:
    """
    메인 라우터 - 제출 여부에 따른 라우팅
    
    라우팅 규칙:
    - 이 라우터는 제출 요청일 때만 실행됨 (eval_turn 이후)
    - is_submitted=True: 평가 진행 (eval_holistic_flow)
    - 일반 채팅은 이 라우터를 거치지 않음
    """
    import logging
    logger = logging.getLogger(__name__)
    
    is_submitted = state.get("is_submitted", False)
    
    if is_submitted:
        logger.info("[Main Router] 제출 요청 확인 - eval_holistic_flow로 진행")
        return "eval_holistic_flow"
    
    # 제출이 아닌데 여기 온 경우는 예외 상황
    logger.warning("[Main Router] 제출이 아닌데 main_router 실행됨 - end로 처리")
    return "end"



