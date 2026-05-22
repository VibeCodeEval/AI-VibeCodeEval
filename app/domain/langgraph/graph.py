"""
메인 LangGraph 정의
AI 바이브 코딩 테스트 평가 플로우

[목적]
- LangGraph를 사용하여 복잡한 AI 평가 플로우를 정의
- 상태 기반 워크플로우로 일관성 있는 평가 프로세스 구현

[그래프 구조]
START → N1 handle_request → N2 intent_analyzer ─┬→ N3 writer → END (일반 채팅)
                                                 ├→ handle_failure / summarize_memory
                                                 └→ N4 eval_turn_guard (제출)
                                                        → N5 eval_code_execution (Judge0)
                                                        → N6 eval_static_analysis (Radon)
                                                        → N7 eval_code_agent (코드 리뷰 LLM)
                                                        → N7 → (N4 turn_scores 있으면 N8 토론, 없으면 생략)
                                                        → N9 aggregate_final_scores → END

[노드 설명]
1. Handle Request: Redis 상태 로드, 턴 번호 증가
2. Intent Analyzer: 의도 분석 + 가드레일 체크 (v2.1: 4대 통합 의도 unified_intent)
3. Writer LLM: AI 답변 생성. v2.1: spec_id=20일 때 클린/스파게티 분기(구조적 용어 감지)
4. Eval Turn Guard: 제출 시 State의 messages에서 모든 턴 추출하여 동기 평가 실행
5. Eval Code Execution (N5): Judge0 코드 실행 평가
6. Eval Static Analysis (N6): Radon CC 정적 분석
7. Eval Code Agent (N7): 코드 리뷰 LLM (단일 에이전트)
8. Holistic Debate (N8): 다중 에이전트 토론 (검사/변호인/중재자 × 2라운드)
9. Final Scores (N9): 최종 점수·등급 집계 및 DB 저장[N4 서브그래프 — eval_turn_guard 내부, subgraph_eval_turn.py]
intent_analysis → intent_router → eval_* (의도별 루브릭 LLM) → summarize_answer → aggregate_turn_log

[노드 ID ↔ 역할 — create_main_graph() 주석과 동기화]
| 그래프 노드 ID          | 단계 | 구현 |
| handle_request          | N1   | Redis·턴 로드 |
| intent_analyzer         | N2   | 채팅 의도·가드레일 |
| writer                  | N3   | AI 답변 |
| eval_turn_guard         | N4   | 턴 평가 서브그래프 일괄 실행 |
| eval_code_execution     | N5   | Judge0 |
| eval_static_analysis    | N6   | Radon CC |
| eval_code_agent         | N7   | 코드 리뷰 LLM |
| holistic_debate         | N8   | 토론 (strict/advocate/neutral/verdict) |
| aggregate_final_scores  | N9   | 최종 점수·등급 |

[상태 관리]
- MainGraphState: 모든 노드가 공유하는 상태 객체
- Redis: 영구 저장소 (세션, 턴 로그 등)
- MemorySaver: LangGraph 체크포인트 (in-memory)
"""

from datetime import datetime
from typing import Any, Dict, Optional

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
from app.domain.langgraph.nodes.eval.routers import holistic_debate_router
from app.domain.langgraph.nodes.system.system_nodes import (handle_failure,
                                                             summarize_memory)
from app.domain.langgraph.eval_timeout_tracking import wrap_eval_node_tracking
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

    # ===== 노드 추가 (그래프 노드 ID → 구현 파일) =====
    #
    # [채팅 루프 N1~N3]
    # handle_request      n1_handle_request.py   Redis 세션 로드, current_turn 증가, 요청 타입 반영
    # intent_analyzer     n2_intent_analyzer.py  채팅 의도·가드레일(시험 규정 위반 등), unified_intent
    # writer              n3_writer.py           응시자용 AI 답변 생성(YAML 프롬프트, 최근 N턴 맥락)
    #
    # [시스템]
    # handle_failure      system_nodes.py        가드레일/오류 시 거절·안내 메시지, END 또는 재라우팅
    # summarize_memory    system_nodes.py        대화 메모리 요약 후 handle_request로 재진입(재시도)
    #
    # [제출·턴 평가 N4]
    # eval_turn_guard     n4_eval_turn_guard.py  제출 시 messages에서 1~(current_turn-1) 턴 추출,
    #                                              Eval Turn SubGraph(의도→루브릭→요약) 동기 실행
    #
    # [제출 후 통합 평가 N5~N9 — 순차 엣지]
    # eval_code_execution n5_integrated_evaluator.py  N5 Judge0 정확성·성능(TC 배치 실행)
    # eval_static_analysis n6_holistic_flow.py        N6 Radon CC·AST 패턴, v1/v2 메트릭
    # eval_code_agent     n7_aggregate_turn_scores.py N7 단일 LLM 코드 리뷰(정성 리포트)
    # holistic_debate     n8_code_execution.py      N8 검사/변호인/중재자 토론(subgraph_debate)
    # aggregate_final_scores n9_final_scores.py     N9 가중 합산·등급·DB/콜백용 final_scores

    builder.add_node(
        "handle_request",  # N1
        wrap_eval_node_tracking("handle_request", handle_request_load_state),
    )

    builder.add_node(
        "intent_analyzer",  # N2
        wrap_eval_node_tracking("intent_analyzer", intent_analyzer),
    )

    builder.add_node(
        "writer",  # N3
        wrap_eval_node_tracking("writer", writer_llm),
    )

    builder.add_node(
        "handle_failure",
        wrap_eval_node_tracking("handle_failure", handle_failure),
    )
    builder.add_node(
        "summarize_memory",
        wrap_eval_node_tracking("summarize_memory", summarize_memory),
    )

    builder.add_node(
        "eval_turn_guard",  # N4 (+ subgraph_eval_turn 내부: intent_analysis, eval_*, summarize_answer)
        wrap_eval_node_tracking("eval_turn_guard", eval_turn_submit_guard),
    )

    builder.add_node(
        "eval_code_execution",  # N5
        wrap_eval_node_tracking("eval_code_execution", eval_code_execution),
    )
    builder.add_node(
        "eval_static_analysis",  # N6
        wrap_eval_node_tracking("eval_static_analysis", eval_static_analysis),
    )
    builder.add_node(
        "eval_code_agent",  # N7
        wrap_eval_node_tracking("eval_code_agent", eval_code_agent),
    )
    builder.add_node(
        "holistic_debate",  # N8
        wrap_eval_node_tracking("holistic_debate", holistic_debate_flow),
    )
    builder.add_node(
        "aggregate_final_scores",  # N9
        wrap_eval_node_tracking("aggregate_final_scores", aggregate_final_scores),
    )

    # ===== 엣지 추가 =====

    builder.add_edge(START, "handle_request")

    builder.add_edge("handle_request", "intent_analyzer")

    # N2 → intent_router: writer | handle_failure | summarize_memory | eval_turn_guard(제출)
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

    # N3 → writer_router: 성공 시 END(일반 채팅 종료), 실패·요약·재요청 분기
    builder.add_conditional_edges(
        "writer",
        writer_router,
        {
            "end": END,
            "handle_failure": "handle_failure",
            "summarize_memory": "summarize_memory",
            "handle_request": "handle_request",
        },
    )

    # N4 완료 후 main_router → N5 시작 (키 eval_holistic_flow는 레거시 라우터 반환값)
    builder.add_conditional_edges(
        "eval_turn_guard",
        main_router,
        {
            "eval_holistic_flow": "eval_code_execution",
            "handle_request": "handle_request",
            "end": END,
        },
    )

    builder.add_conditional_edges(
        "handle_failure",
        main_router,
        {
            "eval_holistic_flow": "eval_code_execution",
            "handle_request": "handle_request",
            "end": END,
        },
    )

    builder.add_edge("summarize_memory", "handle_request")

    # 제출 평가 파이프라인: N5 → N6 → N7 → (N4 turn_scores 있으면 N8) → N9 → END
    builder.add_edge("eval_code_execution", "eval_static_analysis")
    builder.add_edge("eval_static_analysis", "eval_code_agent")
    builder.add_conditional_edges(
        "eval_code_agent",
        holistic_debate_router,
        {
            "holistic_debate": "holistic_debate",
            "aggregate_final_scores": "aggregate_final_scores",
        },
    )
    builder.add_edge("holistic_debate", "aggregate_final_scores")
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
    problem_context: Optional[Dict[str, Any]] = None,
) -> MainGraphState:
    """
    초기 상태 생성

    problem_context가 없으면 동기 경로(get_problem_info_sync)로 내장 스펙만 로드합니다.
    DB 스펙·checker_json이 필요하면 호출부에서 await get_problem_info(spec_id, db) 후 전달하세요.
    """
    now = datetime.utcnow().isoformat()

    if problem_context is None:
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
        test_case_results=None,
        correctness_reasoning=None,
        final_scores=None,
        be_scoring_callback=None,
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
        guardrail_flag_turns=None,
        guardrail_turn_reasons=None,
        # v2.1 Snapshot·평가 (제출 플로우에서 채워짐)
        v1_code=None,
        v2_code=None,
        v1_metrics=None,
        v2_metrics=None,
    )
