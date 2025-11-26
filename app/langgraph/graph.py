"""
메인 LangGraph 정의
AI 바이브 코딩 테스트 평가 플로우
"""
from typing import Optional
from datetime import datetime

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.langgraph.states import MainGraphState
from app.langgraph.nodes.handle_request import handle_request_load_state
from app.langgraph.nodes.intent_analyzer import intent_analyzer
from app.langgraph.nodes.writer import writer_llm
from app.langgraph.nodes.writer_router import writer_router, intent_router, main_router
from app.langgraph.nodes.system_nodes import handle_failure, summarize_memory
from app.langgraph.nodes.eval_turn_guard import eval_turn_submit_guard
from app.langgraph.nodes.evaluators import (
    eval_holistic_flow,
    aggregate_turn_scores,
    eval_code_performance,
    eval_code_correctness,
    aggregate_final_scores,
)
from app.langgraph.subgraph_eval_turn import create_eval_turn_subgraph


def create_main_graph(checkpointer: Optional[MemorySaver] = None) -> StateGraph:
    """
    메인 그래프 생성
    
    플로우:
    1. Handle Request Load State: 요청 처리 및 상태 로드
    2. Intent Analyzer: 의도 분석 및 가드레일
    3. Writer LLM: AI 답변 생성
    3.5. Writer Router: 응답 상태에 따른 라우팅
    4. Eval Turn SubGraph: 실시간 턴 품질 평가
    5. Main Router: 제출 여부 확인
    6a. Eval Holistic Flow: 전략 분석
    6b. Aggregate Turn Scores: 턴 점수 집계
    6c. Eval Code Performance: 성능 평가
    6d. Eval Code Correctness: 정확성 평가
    7. Aggregate Final Scores: 최종 점수 계산
    """
    
    # SubGraph 생성
    eval_turn_subgraph = create_eval_turn_subgraph()
    
    # 메인 그래프 빌더
    builder = StateGraph(MainGraphState)
    
    # ===== 노드 추가 =====
    
    # 1. Handle Request Load State
    builder.add_node("handle_request", handle_request_load_state)
    
    # 2. Intent Analyzer
    builder.add_node("intent_analyzer", intent_analyzer)
    
    # 3. Writer LLM
    builder.add_node("writer", writer_llm)
    
    # SYSTEM 노드들
    builder.add_node("handle_failure", handle_failure)
    builder.add_node("summarize_memory", summarize_memory)
    
    # 4. Eval Turn Guard (제출 시 모든 턴 평가 완료 확인)
    builder.add_node("eval_turn_guard", eval_turn_submit_guard)
    
    # 5. Main Router (조건부 분기 함수로 처리)
    
    # 6a-6d. 평가 노드들
    builder.add_node("eval_holistic_flow", eval_holistic_flow)
    builder.add_node("aggregate_turn_scores", aggregate_turn_scores)
    builder.add_node("eval_code_performance", eval_code_performance)
    builder.add_node("eval_code_correctness", eval_code_correctness)
    
    # 7. Aggregate Final Scores
    builder.add_node("aggregate_final_scores", aggregate_final_scores)
    
    # ===== 엣지 추가 =====
    
    # START -> Handle Request
    builder.add_edge(START, "handle_request")
    
    # Handle Request -> Intent Analyzer
    builder.add_edge("handle_request", "intent_analyzer")
    
    # Intent Analyzer -> 조건부 분기
    builder.add_conditional_edges(
        "intent_analyzer",
        intent_router,
        {
            "writer": "writer",
            "handle_failure": "handle_failure",
            "summarize_memory": "summarize_memory",
            "handle_request": "handle_request",
            "eval_turn_guard": "eval_turn_guard",  # 제출 시 4번 가드로
        }
    )
    
    # Writer -> 조건부 분기
    builder.add_conditional_edges(
        "writer",
        writer_router,
        {
            "end": END,  # 답변 생성 성공 시 바로 종료
            "handle_failure": "handle_failure",
            "summarize_memory": "summarize_memory",
            "handle_request": "handle_request",
        }
    )
    
    # Eval Turn Guard -> Main Router (조건부)
    # 제출 시 모든 턴 평가 완료 후 5번 Router로 진행
    builder.add_conditional_edges(
        "eval_turn_guard",
        main_router,
        {
            "eval_holistic_flow": "eval_holistic_flow",  # 제출 시 평가 진행
            "handle_request": "handle_request",
            "end": END,
        }
    )
    
    # Handle Failure -> Main Router
    builder.add_conditional_edges(
        "handle_failure",
        main_router,
        {
            "eval_holistic_flow": "eval_holistic_flow",
            "handle_request": "handle_request",
            "end": END,
        }
    )
    
    # Summarize Memory -> Handle Request (재시도)
    builder.add_edge("summarize_memory", "handle_request")
    
    # 평가 노드들 (병렬 실행 후 최종 집계)
    # 6a -> 7
    builder.add_edge("eval_holistic_flow", "aggregate_turn_scores")
    
    # 6b -> 6c
    builder.add_edge("aggregate_turn_scores", "eval_code_performance")
    
    # 6c -> 6d
    builder.add_edge("eval_code_performance", "eval_code_correctness")
    
    # 6d -> 7
    builder.add_edge("eval_code_correctness", "aggregate_final_scores")
    
    # 7 -> END
    builder.add_edge("aggregate_final_scores", END)
    
    # 그래프 컴파일
    if checkpointer:
        graph = builder.compile(checkpointer=checkpointer)
    else:
        graph = builder.compile()
    
    return graph


def get_initial_state(
    session_id: str,
    exam_id: int,
    participant_id: int,
    spec_id: int,
    human_message: str = "",
) -> MainGraphState:
    """초기 상태 생성"""
    now = datetime.utcnow().isoformat()
    
    return MainGraphState(
        session_id=session_id,
        exam_id=exam_id,
        participant_id=participant_id,
        spec_id=spec_id,
        messages=[],
        current_turn=0,
        human_message=human_message,
        ai_message=None,
        intent_status=None,
        is_guardrail_failed=False,
        guardrail_message=None,
        writer_status=None,
        writer_error=None,
        is_submitted=False,
        submission_id=None,
        code_content=None,
        turn_scores={},
        holistic_flow_score=None,
        aggregate_turn_score=None,
        code_performance_score=None,
        code_correctness_score=None,
        final_scores=None,
        memory_summary=None,
        error_message=None,
        retry_count=0,
        created_at=now,
        updated_at=now,
    )



