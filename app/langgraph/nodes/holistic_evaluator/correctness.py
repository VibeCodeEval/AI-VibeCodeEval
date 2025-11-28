import logging
from typing import Dict, Any
from datetime import datetime

from app.langgraph.states import MainGraphState, CodeQualityEvaluation
from app.langgraph.nodes.holistic_evaluator.utils import get_llm

logger = logging.getLogger(__name__)

async def eval_code_correctness(state: MainGraphState) -> Dict[str, Any]:
    """
    6d: 코드 정확성 평가 (Judge0 연동)
    
    평가 항목:
    - 테스트 케이스 통과율
    - 에지 케이스 처리
    - 정확성 점수
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[6d. Eval Code Correctness] 진입 - session_id: {session_id}")
    
    code_content = state.get("code_content")
    submission_id = state.get("submission_id")
    
    if not code_content:
        logger.warning(f"[6d. Eval Code Correctness] 코드 없음 - session_id: {session_id}")
        return {
            "code_correctness_score": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    # TODO: Judge0 API 연동하여 실제 테스트 케이스 실행
    # 현재는 LLM 기반 평가로 대체
    
    llm = get_llm()
    evaluator = llm.with_structured_output(CodeQualityEvaluation)
    
    system_prompt = """당신은 코드 정확성 평가자입니다.
주어진 코드의 정확성을 평가하세요:

1. 로직 정확성
2. 에지 케이스 처리
3. 입출력 형식 준수
4. 정확성 점수 (0-100)

correctness는 로직 정확성을,
efficiency는 이 경우 에지 케이스 처리를,
readability는 코드 명확성을,
best_practices는 정확성 관련 모범 사례를 평가하세요."""

    try:
        result = await evaluator.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"코드:\n```\n{code_content}\n```"}
        ])
        
        # 정확성 점수 계산 (correctness 위주)
        correctness_score = (result.correctness * 0.7 + result.efficiency * 0.2 + result.best_practices * 0.1)
        
        logger.info(f"[6d. Eval Code Correctness] 완료 - session_id: {session_id}, score: {correctness_score:.2f}")
        
        return {
            "code_correctness_score": round(correctness_score, 2),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"[6d. Eval Code Correctness] 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
        return {
            "code_correctness_score": None,
            "error_message": f"정확성 평가 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }

