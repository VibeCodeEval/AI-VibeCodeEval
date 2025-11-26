"""
Eval Turn SubGraph
실시간 턴 품질 평가
"""
import logging
from typing import Dict, Any, Literal
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.langgraph.states import EvalTurnState, IntentClassification, TurnEvaluation
from app.core.config import settings
from app.db.models.enums import CodeIntentType

logger = logging.getLogger(__name__)


def get_llm():
    """LLM 인스턴스 생성"""
    return ChatGoogleGenerativeAI(
        model=settings.DEFAULT_LLM_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.1,
    )


# ===== 노드 정의 =====

async def intent_analysis(state: EvalTurnState) -> Dict[str, Any]:
    """
    4.0: Intent Analysis
    7가지 코드 패턴 분류
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.0 Intent Analysis] 진입 - session_id: {session_id}, turn: {turn}")
    
    human_message = state.get("human_message", "")
    ai_message = state.get("ai_message", "")
    
    llm = get_llm()
    classifier = llm.with_structured_output(IntentClassification)
    
    system_prompt = """당신은 코딩 대화의 의도를 분류하는 전문가입니다.
사용자와 AI의 대화를 분석하여 다음 7가지 중 하나로 분류하세요:

1. RULE_SETTING: 규칙 설정, 요구사항 정의, 제약조건 설명
2. GENERATION: 새로운 코드 생성 요청
3. OPTIMIZATION: 기존 코드 최적화, 성능 개선
4. DEBUGGING: 버그 수정, 오류 해결
5. TEST_CASE: 테스트 케이스 작성, 테스트 관련
6. HINT_OR_QUERY: 힌트 요청, 질문, 설명 요청
7. FOLLOW_UP: 후속 질문, 추가 요청, 확인

대화 맥락을 고려하여 가장 적절한 의도를 선택하세요."""

    prompt = f"사용자: {human_message}\n\nAI 응답: {ai_message}"
    
    try:
        result = await classifier.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        
        logger.info(f"[4.0 Intent Analysis] 완료 - session_id: {session_id}, turn: {turn}, 의도: {result.intent_type.value}, 신뢰도: {result.confidence:.2f}")
        
        return {
            "intent_type": result.intent_type.value,
            "intent_confidence": result.confidence,
        }
        
    except Exception as e:
        logger.error(f"[4.0 Intent Analysis] 오류 - session_id: {session_id}, turn: {turn}, error: {str(e)}", exc_info=True)
        return {
            "intent_type": CodeIntentType.HINT_OR_QUERY.value,
            "intent_confidence": 0.0,
        }


def intent_router(state: EvalTurnState) -> str:
    """
    4.0.1: Intent Router
    의도에 따라 개별 평가 노드로 분기
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    intent_type = state.get("intent_type", CodeIntentType.HINT_OR_QUERY.value)
    
    logger.info(f"[4.0.1 Intent Router] 의도별 라우팅 - session_id: {session_id}, turn: {turn}, 의도: {intent_type}")
    
    routing_map = {
        CodeIntentType.RULE_SETTING.value: "eval_rule_setting",
        CodeIntentType.GENERATION.value: "eval_generation",
        CodeIntentType.OPTIMIZATION.value: "eval_optimization",
        CodeIntentType.DEBUGGING.value: "eval_debugging",
        CodeIntentType.TEST_CASE.value: "eval_test_case",
        CodeIntentType.HINT_OR_QUERY.value: "eval_hint_query",
        CodeIntentType.FOLLOW_UP.value: "eval_follow_up",
    }
    
    return routing_map.get(intent_type, "eval_hint_query")


# 각 의도별 평가 노드들
async def _evaluate_turn(state: EvalTurnState, eval_type: str, criteria: str) -> Dict[str, Any]:
    """공통 턴 평가 로직"""
    human_message = state.get("human_message", "")
    ai_message = state.get("ai_message", "")
    
    llm = get_llm()
    evaluator = llm.with_structured_output(TurnEvaluation)
    
    system_prompt = f"""당신은 AI 코딩 어시스턴트의 응답을 평가합니다.
평가 유형: {eval_type}
평가 기준: {criteria}

각 항목은 0-10점으로 평가하세요:
- quality_score: 응답 품질
- relevance_score: 요청과의 관련성
- helpfulness_score: 유용성"""

    prompt = f"사용자 요청:\n{human_message}\n\nAI 응답:\n{ai_message}"
    
    try:
        result = await evaluator.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        
        avg_score = (result.quality_score + result.relevance_score + result.helpfulness_score) / 3
        
        return {
            "quality": result.quality_score,
            "relevance": result.relevance_score,
            "helpfulness": result.helpfulness_score,
            "average": round(avg_score, 2),
            "feedback": result.feedback,
        }
        
    except Exception as e:
        return {
            "quality": 0,
            "relevance": 0,
            "helpfulness": 0,
            "average": 0,
            "feedback": f"평가 실패: {str(e)}",
        }


async def eval_rule_setting(state: EvalTurnState) -> Dict[str, Any]:
    """4.R: Rule Setting 평가"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.R Rule Setting 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state, 
        "규칙 설정",
        "요구사항을 정확히 이해하고 적절한 규칙/제약을 설정했는가"
    )
    
    logger.info(f"[4.R Rule Setting 평가] 완료 - session_id: {session_id}, turn: {turn}, 평균: {result.get('average', 0)}")
    return {"rule_setting_eval": result}


async def eval_generation(state: EvalTurnState) -> Dict[str, Any]:
    """4.G: Generation 평가"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.G 코드 생성 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "코드 생성",
        "요청에 맞는 정확하고 효율적인 코드를 생성했는가"
    )
    
    logger.info(f"[4.G 코드 생성 평가] 완료 - session_id: {session_id}, turn: {turn}, 평균: {result.get('average', 0)}")
    return {"generation_eval": result}


async def eval_optimization(state: EvalTurnState) -> Dict[str, Any]:
    """4.O: Optimization 평가"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.O 최적화 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "최적화",
        "성능을 효과적으로 개선했는가, 최적화 설명이 적절한가"
    )
    
    logger.info(f"[4.O 최적화 평가] 완료 - session_id: {session_id}, turn: {turn}, 평균: {result.get('average', 0)}")
    return {"optimization_eval": result}


async def eval_debugging(state: EvalTurnState) -> Dict[str, Any]:
    """4.D: Debugging 평가"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.D 디버깅 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "디버깅",
        "버그를 정확히 식별하고 해결했는가"
    )
    
    logger.info(f"[4.D 디버깅 평가] 완료 - session_id: {session_id}, turn: {turn}, 평균: {result.get('average', 0)}")
    return {"debugging_eval": result}


async def eval_test_case(state: EvalTurnState) -> Dict[str, Any]:
    """4.T: Test Case 평가"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.T 테스트 케이스 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "테스트 케이스",
        "적절한 테스트 케이스를 제공했는가, 에지 케이스 고려했는가"
    )
    
    logger.info(f"[4.T 테스트 케이스 평가] 완료 - session_id: {session_id}, turn: {turn}, 평균: {result.get('average', 0)}")
    return {"test_case_eval": result}


async def eval_hint_query(state: EvalTurnState) -> Dict[str, Any]:
    """4.H: Hint/Query 평가"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.H 힌트/질의 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "힌트/질의 응답",
        "적절한 힌트를 제공했는가, 질문에 정확히 답변했는가"
    )
    
    logger.info(f"[4.H 힌트/질의 평가] 완료 - session_id: {session_id}, turn: {turn}, 평균: {result.get('average', 0)}")
    return {"hint_query_eval": result}


async def eval_follow_up(state: EvalTurnState) -> Dict[str, Any]:
    """4.F: Follow Up 평가"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.F 후속 응답 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "후속 응답",
        "이전 맥락을 고려하여 적절히 응답했는가"
    )
    
    logger.info(f"[4.F 후속 응답 평가] 완료 - session_id: {session_id}, turn: {turn}, 평균: {result.get('average', 0)}")
    return {"follow_up_eval": result}


async def summarize_answer(state: EvalTurnState) -> Dict[str, Any]:
    """
    4.X: Summarize Answer
    LLM 답변 요약/추론
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.X 답변 요약] 진입 - session_id: {session_id}, turn: {turn}")
    
    ai_message = state.get("ai_message", "")
    
    if not ai_message:
        logger.warning(f"[4.X 답변 요약] AI 메시지 없음 - session_id: {session_id}, turn: {turn}")
        return {"answer_summary": None}
    
    llm = get_llm()
    
    system_prompt = """AI 응답을 3줄 이내로 핵심만 요약하세요.
- 제공된 코드의 핵심 기능
- 주요 알고리즘/접근 방식
- 핵심 설명 포인트"""

    try:
        result = await llm.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": ai_message}
        ])
        
        logger.info(f"[4.X 답변 요약] 완료 - session_id: {session_id}, turn: {turn}, 요약 길이: {len(result.content)}")
        return {"answer_summary": result.content}
        
    except Exception as e:
        logger.error(f"[4.X 답변 요약] 오류 - session_id: {session_id}, turn: {turn}, error: {str(e)}", exc_info=True)
        return {"answer_summary": None}


async def aggregate_turn_log(state: EvalTurnState) -> Dict[str, Any]:
    """
    4.4: Aggregate Turn Log
    최종 턴 로그 JSON 생성
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.4 턴 로그 집계] 진입 - session_id: {session_id}, turn: {turn}")
    
    # 평가 결과 수집
    eval_results = {}
    
    for eval_key in [
        "rule_setting_eval", "generation_eval", "optimization_eval",
        "debugging_eval", "test_case_eval", "hint_query_eval", "follow_up_eval"
    ]:
        if state.get(eval_key):
            eval_results[eval_key] = state.get(eval_key)
    
    # 평균 점수 계산
    all_averages = []
    for eval_data in eval_results.values():
        if isinstance(eval_data, dict) and "average" in eval_data:
            all_averages.append(eval_data["average"])
    
    # 가드레일 위반 시 점수 처리
    is_guardrail_failed = state.get("is_guardrail_failed", False)
    
    if is_guardrail_failed:
        # 가드레일 위반 시: 평가 점수는 0점 처리
        turn_score = 0
        logger.warning(f"[4.4 턴 로그 집계] 가드레일 위반 - session_id: {session_id}, turn: {turn}, 점수: 0점")
    else:
        turn_score = sum(all_averages) / len(all_averages) if all_averages else 0
    
    # 턴 로그 생성
    turn_log = {
        "session_id": state.get("session_id"),
        "turn": state.get("turn"),
        "intent_type": state.get("intent_type"),
        "intent_confidence": state.get("intent_confidence"),
        "is_guardrail_failed": is_guardrail_failed,
        "guardrail_message": state.get("guardrail_message"),
        "evaluations": eval_results,
        "answer_summary": state.get("answer_summary"),
        "turn_score": round(turn_score * 10, 2),  # 0-100 스케일로 변환
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    logger.info(f"[4.4 턴 로그 집계] 완료 - session_id: {session_id}, turn: {turn}, 턴 점수: {turn_score * 10:.2f}, 평가 개수: {len(eval_results)}")
    
    return {
        "turn_log": turn_log,
        "turn_score": round(turn_score * 10, 2),
    }


def create_eval_turn_subgraph() -> StateGraph:
    """
    Eval Turn SubGraph 생성
    
    플로우:
    START -> Intent Analysis -> Intent Router -> 개별 평가 노드
         -> Summarize Answer -> Aggregate Turn Log -> END
    """
    builder = StateGraph(EvalTurnState)
    
    # 노드 추가
    builder.add_node("intent_analysis", intent_analysis)
    builder.add_node("eval_rule_setting", eval_rule_setting)
    builder.add_node("eval_generation", eval_generation)
    builder.add_node("eval_optimization", eval_optimization)
    builder.add_node("eval_debugging", eval_debugging)
    builder.add_node("eval_test_case", eval_test_case)
    builder.add_node("eval_hint_query", eval_hint_query)
    builder.add_node("eval_follow_up", eval_follow_up)
    builder.add_node("summarize_answer", summarize_answer)
    builder.add_node("aggregate_turn_log", aggregate_turn_log)
    
    # 엣지 추가
    builder.add_edge(START, "intent_analysis")
    
    # Intent Router 조건부 분기
    builder.add_conditional_edges(
        "intent_analysis",
        intent_router,
        {
            "eval_rule_setting": "eval_rule_setting",
            "eval_generation": "eval_generation",
            "eval_optimization": "eval_optimization",
            "eval_debugging": "eval_debugging",
            "eval_test_case": "eval_test_case",
            "eval_hint_query": "eval_hint_query",
            "eval_follow_up": "eval_follow_up",
        }
    )
    
    # 각 평가 노드 -> Summarize Answer
    for node in [
        "eval_rule_setting", "eval_generation", "eval_optimization",
        "eval_debugging", "eval_test_case", "eval_hint_query", "eval_follow_up"
    ]:
        builder.add_edge(node, "summarize_answer")
    
    # Summarize Answer -> Aggregate Turn Log
    builder.add_edge("summarize_answer", "aggregate_turn_log")
    
    # Aggregate Turn Log -> END
    builder.add_edge("aggregate_turn_log", END)
    
    return builder.compile()



