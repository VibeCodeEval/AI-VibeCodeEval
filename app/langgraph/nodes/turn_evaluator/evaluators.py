import logging
from typing import Dict, Any, List

from app.langgraph.states import EvalTurnState, TurnEvaluation
from app.langgraph.nodes.turn_evaluator.utils import get_llm

logger = logging.getLogger(__name__)

async def _evaluate_turn(state: EvalTurnState, eval_type: str, criteria: str) -> Dict[str, Any]:
    """
    공통 턴 평가 로직 (사용자 프롬프트 평가)
    
    Claude Prompt Engineering 기준:
    1. 명확성 (Clarity)
    2. 예시 사용 (Examples)
    3. 규칙 및 제약조건 (Rules)
    4. 사고 연쇄 유도 (Chain of Thought)
    """
    human_message = state.get("human_message", "")
    ai_message = state.get("ai_message", "")
    
    llm = get_llm()
    evaluator = llm.with_structured_output(TurnEvaluation)
    
    system_prompt = f"""당신은 '프롬프트 엔지니어링' 전문가입니다.
사용자가 작성한 프롬프트가 '{eval_type}' 의도를 얼마나 잘 전달하고 있는지 평가하세요.
AI의 응답은 참고용으로만 사용하고, 평가는 오직 '사용자의 프롬프트'에 집중하세요.

평가 기준 (Claude Prompt Engineering):
1. **명확성 (Clarity)**: 요청이 모호하지 않고 구체적인가? (직접적이고 명확하게)
2. **예시 (Examples)**: 원하는 입출력 예시나 상황을 제공했는가? (멀티샷)
3. **규칙 (Rules)**: {criteria} (XML 태그 사용, 제약조건 명시 등)
4. **문맥 (Context)**: 이전 대화나 배경 지식을 적절히 활용했는가?

위 기준을 바탕으로 0-100점 사이의 점수를 부여하고, 상세한 루브릭과 추론을 제공하세요."""

    prompt = f"""[사용자 프롬프트]
{human_message}

[AI 응답 (참고용)]
{ai_message}

위 사용자 프롬프트를 '{eval_type}' 관점에서 평가하세요."""
    
    try:
        result = await evaluator.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        
        return {
            "intent": result.intent,
            "score": result.score,
            "average": result.score,  # 호환성 유지
            "rubrics": [r.dict() for r in result.rubrics],
            "final_reasoning": result.final_reasoning
        }
        
    except Exception as e:
        logger.error(f"평가 중 오류 발생: {str(e)}")
        return {
            "intent": eval_type,
            "score": 0,
            "average": 0,
            "rubrics": [],
            "final_reasoning": f"평가 실패: {str(e)}"
        }


async def eval_system_prompt(state: EvalTurnState) -> Dict[str, Any]:
    """4.SP: System Prompt 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.SP 시스템 프롬프트 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "시스템 프롬프트 설정 (System Prompting)",
        "AI에게 구체적인 역할(Persona)을 부여하고, 임무의 범위(Scope)와 답변 스타일(Tone & Style)을 명확히 정의했는가?"
    )
    
    return {"system_prompt_eval": result}


async def eval_rule_setting(state: EvalTurnState) -> Dict[str, Any]:
    """4.R: Rule Setting 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.R Rule Setting 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state, 
        "규칙 설정 (Rule Setting)",
        "제약 조건(시간/공간 복잡도, 언어 등)을 명확히 XML 태그나 리스트로 명시했는가?"
    )
    
    return {"rule_setting_eval": result}


async def eval_generation(state: EvalTurnState) -> Dict[str, Any]:
    """4.G: Generation 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.G 코드 생성 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "코드 생성 요청 (Generation)",
        "원하는 기능의 입출력 예시(Input/Output Examples)를 제공하고, 구현 조건을 상세히 기술했는가?"
    )
    
    return {"generation_eval": result}


async def eval_optimization(state: EvalTurnState) -> Dict[str, Any]:
    """4.O: Optimization 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.O 최적화 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "최적화 요청 (Optimization)",
        "현재 코드의 문제점(병목)을 지적하고, 목표 성능(O(n) 등)이나 구체적인 최적화 전략을 제시했는가?"
    )
    
    return {"optimization_eval": result}


async def eval_debugging(state: EvalTurnState) -> Dict[str, Any]:
    """4.D: Debugging 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.D 디버깅 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "디버깅 요청 (Debugging)",
        "발생한 에러 메시지, 재현 단계, 또는 예상치 못한 동작을 구체적으로 설명했는가?"
    )
    
    return {"debugging_eval": result}


async def eval_test_case(state: EvalTurnState) -> Dict[str, Any]:
    """4.T: Test Case 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.T 테스트 케이스 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "테스트 케이스 요청 (Test Case)",
        "테스트하고 싶은 엣지 케이스(Edge Cases)나 경계 조건(Boundary Conditions)을 명시했는가?"
    )
    
    return {"test_case_eval": result}


async def eval_hint_query(state: EvalTurnState) -> Dict[str, Any]:
    """4.H: Hint/Query 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.H 힌트/질의 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "힌트/질의 요청 (Hint/Query)",
        "단순히 정답을 묻는 것이 아니라, 자신의 사고 과정(Chain of Thought)을 공유하고 막힌 부분을 구체적으로 질문했는가?"
    )
    
    return {"hint_query_eval": result}


async def eval_follow_up(state: EvalTurnState) -> Dict[str, Any]:
    """4.F: Follow Up 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.F 후속 질문 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "후속 질문 (Follow Up)",
        "이전 턴의 AI 답변을 기반으로, 추가적인 개선점이나 의문점을 논리적으로 연결하여 질문했는가?"
    )
    
    return {"follow_up_eval": result}
