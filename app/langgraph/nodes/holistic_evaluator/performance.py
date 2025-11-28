import logging
from typing import Dict, Any
from datetime import datetime

from app.langgraph.states import MainGraphState, CodeQualityEvaluation
from app.langgraph.nodes.holistic_evaluator.utils import get_llm

logger = logging.getLogger(__name__)

async def eval_code_performance(state: MainGraphState) -> Dict[str, Any]:
    """
    6c: 코드 성능 평가 (Judge0 연동)
    
    평가 항목:
    - 실행 시간
    - 메모리 사용량
    - 효율성 점수
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[6c. Eval Code Performance] 진입 - session_id: {session_id}")
    
    code_content = state.get("code_content")
    submission_id = state.get("submission_id")
    
    if not code_content:
        logger.warning(f"[6c. Eval Code Performance] 코드 없음 - session_id: {session_id}")
        return {
            "code_performance_score": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    logger.info(f"[6c. Eval Code Performance] 코드 평가 시작 - session_id: {session_id}, 코드 길이: {len(code_content)}")
    
    # TODO: Judge0 API 연동
    # 현재는 LLM 기반 평가로 대체
    
    llm = get_llm()
    evaluator = llm.with_structured_output(CodeQualityEvaluation)
    
    system_prompt = """당신은 코드 성능 평가자입니다.
주어진 코드의 성능을 평가하세요:

1. 시간 복잡도 분석
2. 공간 복잡도 분석
3. 최적화 가능성
4. 효율성 점수 (0-100)

correctness는 성능과 관련된 정확성을,
efficiency는 알고리즘 효율성을,
readability는 코드 가독성을,
best_practices는 성능 관련 모범 사례 준수를 평가하세요."""

    try:
        result = await evaluator.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"코드:\n```\n{code_content}\n```"}
        ])
        
        # 성능 점수 계산 (efficiency 위주)
        perf_score = (result.efficiency * 0.6 + result.correctness * 0.2 + result.best_practices * 0.2)
        
        logger.info(f"[6c. Eval Code Performance] 완료 - session_id: {session_id}, score: {perf_score:.2f}")
        
        return {
            "code_performance_score": round(perf_score, 2),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"[6c. Eval Code Performance] 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
        return {
            "code_performance_score": None,
            "error_message": f"성능 평가 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }

