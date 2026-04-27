"""
메인 LangGraph 정의
AI 바이브 코딩 테스트 평가 플로우

[목적]
- LangGraph를 사용하여 복잡한 AI 평가 플로우를 정의
- 상태 기반 워크플로우로 일관성 있는 평가 프로세스 구현

[그래프 구조]
START → 1. Handle Request → 2. Intent Analyzer → 3. Writer LLM → END
                                      ↓ (제출)
                           4. Eval Turn Guard → 5. Main Router
                                                       ↓
                                           6a-6d. 평가 노드들
                                                       ↓
                                          7. Final Score Aggregation
                                                       ↓
                                                      END

[노드 설명]
1. Handle Request: Redis 상태 로드, 턴 번호 증가
2. Intent Analyzer: 의도 분석 + 가드레일 체크 (v2.1: 4대 통합 의도 unified_intent)
3. Writer LLM: AI 답변 생성. v2.1: spec_id=20일 때 클린/스파게티 분기(구조적 용어 감지)
4. Eval Turn Guard: 제출 시 State의 messages에서 모든 턴 추출하여 동기 평가 실행
5. Main Router: 제출 여부에 따른 분기
5. Eval Code Execution (N5): Judge0 코드 실행 평가
6. Eval Static Analysis (N6): Radon CC 정적 분석
7. Eval Code Agent (N7): 코드 리뷰 LLM (단일 에이전트)
8. Holistic Debate (N8): 다중 에이전트 토론 (검사/변호인/중재자 × 2라운드)
9. Final Scores (N9): 최종 점수·등급 집계 및 DB 저장

[상태 관리]
- MainGraphState: 모든 노드가 공유하는 상태 객체
- Redis: 영구 저장소 (세션, 턴 로그 등)
- MemorySaver: LangGraph 체크포인트 (in-memory)
"""

from datetime import datetime
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from app.domain.langgraph.nodes.chat.n1_handle_request import \
    handle_request_load_state
from app.domain.langgraph.nodes.chat.n2_intent_analyzer import intent_analyzer
from app.domain.langgraph.nodes.chat.n3_writer import writer_llm
from app.domain.langgraph.nodes.chat.routers import (intent_router,
                                                      main_router,
                                                      writer_router)
from app.domain.langgraph.nodes.eval.n4_eval_turn_guard import \
    eval_turn_submit_guard
from app.domain.langgraph.nodes.eval.n5_integrated_evaluator import \
    eval_code_execution
from app.domain.langgraph.nodes.eval.n6_holistic_flow import eval_static_analysis
from app.domain.langgraph.nodes.eval.n7_aggregate_turn_scores import \
    eval_code_agent
from app.domain.langgraph.nodes.eval.n8_code_execution import \
    holistic_debate_flow
import logging
from app.domain.langgraph.nodes.eval.n9_final_scores import \
    aggregate_final_scores
from app.domain.langgraph.nodes.system.system_nodes import (handle_failure,
                                                             summarize_memory)
from app.domain.langgraph.states import MainGraphState
from app.domain.langgraph.subgraph_eval_turn import create_eval_turn_subgraph
from app.domain.langgraph.utils.problem_info import get_problem_info_sync


def create_main_graph(checkpointer: Optional[MemorySaver] = None) -> StateGraph:
    """
    메인 그래프 생성

    [역할]
    - LangGraph 메인 플로우를 정의하고 컴파일
    - 노드 추가 및 엣지 연결
    - 조건부 분기 설정

    [플로우 상세]
    ┌─────────────────────────────────────────────────────────┐
    │ 일반 채팅 플로우                                          │
    │ START → Handle Request → Intent Analyzer → Writer LLM    │
    │         ↓                         ↓ (가드레일 위반)      │
    │    Redis 상태 로드         Handle Failure → END          │
    │                                                          │
    │ ⚠️ 일반 채팅에서는 평가를 실행하지 않음 (응답만 반환)     │
    └─────────────────────────────────────────────────────────┘

    ┌─────────────────────────────────────────────────────────┐
    │ 제출 플로우                                               │
    │ START → Handle Request → Intent Analyzer                 │
    │                              ↓ (PASSED_SUBMIT)           │
    │                   Eval Turn Guard                        │
    │                    - State의 messages에서 모든 턴 추출   │
    │                    - 각 턴에 대해 Eval Turn SubGraph 실행│
    │                    - 모든 턴 평가 완료                    │
    │                              ↓                           │
    │                   Main Router (제출 확인)                │
    │                              ↓                           │
    │         ┌────────────────────┴──────────────────┐       │
    │         ↓                    ↓                  ↓       │
    │  Holistic Flow    Aggregate Scores    Code Eval        │
    │         └────────────────────┬──────────────────┘       │
    │                              ↓                          │
    │                   Final Score Aggregation               │
    │                              ↓                          │
    │                             END                         │
    └─────────────────────────────────────────────────────────┘

    [노드 종류]
    1. 처리 노드: handle_request, intent_analyzer, writer
    2. 시스템 노드: handle_failure, summarize_memory
    3. 가드 노드: eval_turn_guard
    4. 평가 노드: eval_holistic_flow, aggregate_turn_scores,
                 eval_code_performance, eval_code_correctness
    5. 집계 노드: aggregate_final_scores

    [조건부 분기]
    - Intent Router: 의도에 따라 writer/failure/guard로 분기
    - Writer Router: 응답 상태에 따라 end/failure로 분기
    - Main Router: 제출 여부에 따라 평가/end로 분기

    Args:
        checkpointer: LangGraph 체크포인트 (선택, 기본 None)

    Returns:
        StateGraph: 컴파일된 메인 그래프
    """

    # Eval Turn SubGraph는 제출 시 Eval Turn Guard에서 동기적으로 실행
    # 일반 채팅에서는 평가를 하지 않음
    # eval_turn_subgraph = create_eval_turn_subgraph()  # Guard에서 직접 생성하여 사용

    # 메인 그래프 빌더 초기화
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

    # 4. Eval Turn Guard (제출 시 State의 messages에서 모든 턴 추출하여 동기 평가 실행)
    builder.add_node("eval_turn_guard", eval_turn_submit_guard)

    # 5. Main Router (조건부 분기 함수로 처리)

    # 신규 평가 파이프라인 (N5~N8)
    builder.add_node("eval_code_execution", eval_code_execution)      # N5 Judge0
    builder.add_node("eval_static_analysis", eval_static_analysis)    # N6 Radon CC
    builder.add_node("eval_code_agent", eval_code_agent)              # N7 Code Review LLM
    builder.add_node("holistic_debate", holistic_debate_flow)         # N8 다중 에이전트 토론

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
        },
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
        },
    )

    # 제출 시 eval_turn_guard 통과 후 N5(eval_code_execution)로 진입
    # "eval_holistic_flow" 키는 main_router가 반환하는 레거시 값으로, 실제 노드는 eval_code_execution(N5)으로 매핑
    builder.add_conditional_edges(
        "eval_turn_guard",
        main_router,
        {
            "eval_holistic_flow": "eval_code_execution",
            "handle_request": "handle_request",
            "end": END,
        },
    )

    # Handle Failure -> Main Router
    builder.add_conditional_edges(
        "handle_failure",
        main_router,
        {
            "eval_holistic_flow": "eval_code_execution",
            "handle_request": "handle_request",
            "end": END,
        },
    )

    # Summarize Memory -> Handle Request (재시도)
    builder.add_edge("summarize_memory", "handle_request")

    # N5 -> N6 -> N7 -> N8 -> N9 순차 실행
    builder.add_edge("eval_code_execution", "eval_static_analysis")   # N5 -> N6
    builder.add_edge("eval_static_analysis", "eval_code_agent")       # N6 -> N7
    builder.add_edge("eval_code_agent", "holistic_debate")            # N7 -> N8
    builder.add_edge("holistic_debate", "aggregate_final_scores")     # N8 -> N9

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
    spec_id: Optional[int],
    human_message: str = "",
    request_type: str = "CHAT",
) -> MainGraphState:
    """
    초기 상태 생성

    문제 정보를 하드코딩 딕셔너리에서 가져와서 State에 추가
    추후 DB 조회로 전환 가능
    """
    now = datetime.utcnow().isoformat()

    # 문제 정보 가져오기 (하드코딩 딕셔너리)
    problem_context = get_problem_info_sync(spec_id)

    # 개별 필드 추출 (하위 호환성 유지)
    basic_info = problem_context.get("basic_info", {})
    ai_guide = problem_context.get("ai_guide", {})

    return MainGraphState(
        session_id=session_id,
        exam_id=exam_id,
        participant_id=participant_id,
        spec_id=spec_id,
        problem_context=problem_context,  # 새 구조
        problem_id=basic_info.get("problem_id"),
        problem_name=basic_info.get("title"),
        problem_algorithm=(
            ai_guide.get("key_algorithms", [None])[0]
            if ai_guide.get("key_algorithms")
            else None
        ),
        problem_keywords=problem_context.get("keywords", []),
        messages=[],
        current_turn=0,
        human_message=human_message,
        ai_message=None,
        intent_status=None,
        is_guardrail_failed=False,
        guardrail_message=None,
        guide_strategy=None,
        keywords=None,
        intent_llm_ran=None,
        writer_status=None,
        writer_error=None,
        request_type=request_type,
        is_submitted=False,
        submission_id=None,
        code_content=None,
        turn_scores={},
        holistic_flow_score=None,
        r4_context_maintenance_score=None,
        holistic_flow_analysis=None,
        aggregate_turn_score=None,
        code_performance_score=None,
        code_correctness_score=None,
        execution_time=None,
        memory_used_mb=None,
        time_limit_sec=None,
        memory_limit_mb=None,
        skip_performance=None,
        skip_reason=None,
        test_cases_passed=None,
        test_cases_total=None,
        correctness_reasoning=None,
        final_scores=None,
        memory_summary=None,
        error_message=None,
        retry_count=0,
        created_at=now,
        updated_at=now,
        enable_langsmith_tracing=None,  # None이면 환경 변수 사용
        # 토큰 사용량 초기화 (키가 없으면 노드에서 조건부 추가 안 됨)
        chat_tokens={},
        eval_tokens={},
        # Phase 6B: Spec 중심 통합 평가
        turn_analysis=None,
        integrated_score=None,
        integrated_evaluation=None,
        # Phase 6E: 다중 에이전트 토론 로그
        debate_log=None,
        debate_initial_opinions=None,
        debate_rebuttals=None,
        # v2.1 Snapshot·평가 (제출 플로우에서 채워짐)
        v1_code=None,
        v2_code=None,
        v1_metrics=None,
        v2_metrics=None,
    )
