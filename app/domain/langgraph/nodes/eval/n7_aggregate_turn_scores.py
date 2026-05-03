"""
N7: 코드 리뷰 에이전트 (단일 LLM 호출)
제출된 코드와 객관적 지표(Judge0, Radon CC)를 바탕으로 정성(Qualitative) 리뷰를 생성합니다.
"""

import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.domain.langgraph.prompts import render_prompt
from app.domain.langgraph.nodes.eval_turn.utils import get_llm
from app.domain.langgraph.states import MainGraphState

logger = logging.getLogger(__name__)

class CodeEvalReport(BaseModel):
    """코드 심층 분석 결과 모델"""
    efficiency_review: str = Field(..., description="코드 효율성(속도, 메모리, 알고리즘)에 대한 구체적 수치 연계 리뷰")
    readability_review: str = Field(..., description="코드 가독성(기명, 모듈화, CC)에 대한 리뷰")
    error_handling_review: str = Field(..., description="엣지 케이스 및 예외 처리 견고성에 대한 리뷰")
    overall_summary: str = Field(..., description="코드 리뷰 종합 요약")
    score_adjustment_note: str = Field(..., description="구체적 개선 방식 및 학점 산정 시 고려해야 할 정성적 패널티 또는 가산점 의견지")


async def eval_code_agent(state: MainGraphState) -> Dict[str, Any]:
    session_id = state.get("session_id", "unknown")
    logger.info(f"[N7. Eval Code Agent] 코드 리뷰 생성 시작 - session_id: {session_id}")
    
    code_content = state.get("code_content", "")
    code_correctness_score = state.get("code_correctness_score")
    code_performance_score = state.get("code_performance_score")
    execution_time = state.get("execution_time")
    memory_used_mb = state.get("memory_used_mb")
    
    code_quality_metrics = state.get("code_quality_metrics", {})
    problem_context = state.get("problem_context", {})
    
    if not code_content:
        logger.warning(f"[N7] 코드 내용이 없습니다. 평가 스킵.")
        return {"code_eval_report": None}

    # N5 -> N7 전달값 검증 로그 (Judge0 지표 누락 원인 추적용)
    logger.info(
        f"[N7] 입력 메트릭 - session_id: {session_id}, "
        f"code_correctness_score={code_correctness_score}, "
        f"code_performance_score={code_performance_score}, "
        f"execution_time={execution_time}, memory_used_mb={memory_used_mb}"
    )
        
    system_prompt = render_prompt("eval_code_agent", section="system")
    human_msg_content = render_prompt(
        "eval_code_agent",
        section="human",
        problem_description=problem_context.get("basic_info", {}).get("description", "설명 없음"),
        code_content=code_content,
        code_correctness_score=code_correctness_score,
        code_performance_score=code_performance_score,
        execution_time=execution_time,
        memory_used_mb=memory_used_mb,
        avg_cc=code_quality_metrics.get("radon_cc", {}).get("avg_cc", "N/A"),
        max_cc=code_quality_metrics.get("radon_cc", {}).get("max_cc", "N/A"),
        delta_cc_pct=code_quality_metrics.get("delta_cc", {}).get("delta_cc_pct", "N/A"),
        junior_grade=code_quality_metrics.get("junior_grade", False),
    )
    logger.info(
        f"[N7] 렌더 프롬프트 요약 - "
        f"Execution Time: {execution_time}초, Memory Used: {memory_used_mb}MB"
    )
    
    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(CodeEvalReport)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_msg_content)
        ]
        
        result = await structured_llm.ainvoke(messages)
        report_dict = result.dict()
        
        logger.info(f"[N7. Eval Code Agent] 리뷰 완성")
        return {"code_eval_report": report_dict}
        
    except Exception as e:
        logger.error(f"[N7. Eval Code Agent] 코드 리뷰 생성 실패: {e}", exc_info=True)
        return {"code_eval_report": None}
