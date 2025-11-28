import logging
from typing import Dict, Any
from datetime import datetime

from app.langgraph.states import MainGraphState, HolisticFlowEvaluation
from app.langgraph.nodes.holistic_evaluator.utils import get_llm

logger = logging.getLogger(__name__)

async def eval_holistic_flow(state: MainGraphState) -> Dict[str, Any]:
    """
    6a: 전체 플로우 평가 - 전략 Chaining 분석
    
    평가 항목:
    1. 문제 분해 (Problem Decomposition)
    2. 피드백 수용성 (Feedback Integration)
    3. 주도성 및 오류 수정 (Proactiveness)
    4. 전략적 탐색 (Strategic Exploration)
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[6a. Eval Holistic Flow] 진입 - session_id: {session_id}")
    
    try:
        # Redis에서 모든 turn_logs 조회
        from app.db.redis_client import redis_client
        all_turn_logs = await redis_client.get_all_turn_logs(session_id)
        
        logger.info(f"[6a. Eval Holistic Flow] 턴 로그 조회 - session_id: {session_id}, 턴 개수: {len(all_turn_logs)}")
        
        # Chaining 평가를 위한 구조화된 로그 생성
        structured_logs = []
        for turn_num in sorted([int(k) for k in all_turn_logs.keys()]):
            log = all_turn_logs[str(turn_num)]
            structured_logs.append({
                "turn": turn_num,
                "intent": log.get("prompt_evaluation_details", {}).get("intent", "UNKNOWN"),
                "prompt_summary": log.get("user_prompt_summary", ""),
                "llm_reasoning": log.get("llm_answer_reasoning", ""),
                "score": log.get("prompt_evaluation_details", {}).get("score", 0),
                "rubrics": log.get("prompt_evaluation_details", {}).get("rubrics", [])
            })
        
        if not structured_logs:
            logger.warning(f"[6a. Eval Holistic Flow] 턴 로그 없음 - session_id: {session_id}")
            return {
                "holistic_flow_score": 0,
                "updated_at": datetime.utcnow().isoformat(),
            }
        
        llm = get_llm()
        evaluator = llm.with_structured_output(HolisticFlowEvaluation)
        
        # Chaining 평가 프롬프트
        system_prompt = """당신은 AI 코딩 테스트의 Chaining 전략을 평가하는 전문가입니다.

다음은 사용자의 턴별 대화 로그입니다. 각 턴의 의도, 프롬프트 요약, AI 추론을 분석하여 다음 항목을 평가하세요:

1. **문제 분해 (Problem Decomposition):**
   - 전체 코드가 아닌 부분 코드로 점진적으로 구성되는가?
   - 큰 문제를 작은 단계로 나누어 해결하는가?

2. **피드백 수용성 (Feedback Integration):**
   - 턴 N의 AI 힌트 내용이 턴 N+1의 사용자 요청에 반영되었는가?
   - 이전 턴의 제안을 다음 턴에서 활용하는가?

3. **주도성 및 오류 수정 (Proactiveness):**
   - 사용자가 AI의 이전 오류를 구체적으로 지적하는가?
   - 능동적으로 개선 방향을 제시하는가?

4. **전략적 탐색 (Strategic Exploration):**
   - 의도가 HINT_OR_QUERY에서 OPTIMIZATION으로 전환되는 등 능동적인 변화가 있는가?
   - DEBUGGING에서 TEST_CASE로 전환하는 등 전략적 탐색이 있는가?

각 항목은 0-100점으로 평가하고, overall_flow_score를 종합 점수로 반환하세요."""

        import json
        prompt = f"""턴별 대화 로그:

{json.dumps(structured_logs, ensure_ascii=False, indent=2)}

위 로그를 분석하여 Chaining 전략 점수를 평가하세요."""
    
        try:
            result = await evaluator.ainvoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ])
            
            logger.info(f"[6a. Eval Holistic Flow] 평가 완료 - session_id: {session_id}, score: {result.overall_flow_score}")
            
            return {
                "holistic_flow_score": result.overall_flow_score,
                "updated_at": datetime.utcnow().isoformat(),
            }
            
        except Exception as e:
            logger.error(f"[6a. Eval Holistic Flow] LLM 평가 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
            return {
                "holistic_flow_score": None,
                "error_message": f"Holistic flow 평가 실패: {str(e)}",
                "updated_at": datetime.utcnow().isoformat(),
            }
            
    except Exception as e:
        logger.error(f"[6a. Eval Holistic Flow] 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
        return {
            "holistic_flow_score": None,
            "error_message": f"Holistic flow 평가 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }

