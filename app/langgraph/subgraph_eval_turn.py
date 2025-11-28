"""
Eval Turn SubGraph
실시간 턴 품질 평가
"""
from langgraph.graph import StateGraph, START, END
from app.langgraph.states import EvalTurnState
from app.langgraph.nodes.turn_evaluator import (
    intent_analysis,
    intent_router,
    eval_system_prompt,  # 신규 추가
    eval_rule_setting,
    eval_generation,
    eval_optimization,
    eval_debugging,
    eval_test_case,
    eval_hint_query,
    eval_follow_up,
    summarize_answer,
    aggregate_turn_log
)


def create_eval_turn_subgraph() -> StateGraph:
    """
    Eval Turn SubGraph 생성
    
    플로우:
    START -> Intent Analysis -> Intent Router -> 개별 평가 노드
         -> Summarize Answer -> Aggregate Turn Log -> END
    """
    builder = StateGraph(EvalTurnState)
    
    # 노드 추가 (8가지 의도)
    builder.add_node("intent_analysis", intent_analysis)
    builder.add_node("eval_system_prompt", eval_system_prompt)  # 신규 추가
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
    
    # Intent Router 조건부 분기 (다중 의도 병렬 실행)
    # intent_router가 리스트를 반환하면 LangGraph가 자동으로 병렬 실행함
    builder.add_conditional_edges(
        "intent_analysis",
        intent_router
    )
    
    # 각 평가 노드 -> Summarize Answer (8가지 의도)
    for node in [
        "eval_system_prompt",  # 신규 추가
        "eval_rule_setting", "eval_generation", "eval_optimization",
        "eval_debugging", "eval_test_case", "eval_hint_query", "eval_follow_up"
    ]:
        builder.add_edge(node, "summarize_answer")
    
    # Summarize Answer -> Aggregate Turn Log
    builder.add_edge("summarize_answer", "aggregate_turn_log")
    
    # Aggregate Turn Log -> END
    builder.add_edge("aggregate_turn_log", END)
    
    return builder.compile()
