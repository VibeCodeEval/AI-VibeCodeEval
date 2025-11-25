"""
평가 노드들
- 6a: Eval Holistic Flow (전략 Chaining 분석)
- 6b: Aggregate Turn Scores (누적 실시간 점수)
- 6c: Eval Code Performance (Judge0)
- 6d: Eval Code Correctness (Judge0)
- 7: Aggregate Final Scores (모든 점수 취합)
"""
from typing import Dict, Any
from datetime import datetime
from decimal import Decimal

from langchain_google_genai import ChatGoogleGenerativeAI

from app.langgraph.states import (
    MainGraphState, 
    HolisticFlowEvaluation,
    CodeQualityEvaluation,
    FinalScoreAggregation,
)
from app.core.config import settings


def get_llm():
    """LLM 인스턴스 생성"""
    return ChatGoogleGenerativeAI(
        model=settings.DEFAULT_LLM_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.1,
    )


async def eval_holistic_flow(state: MainGraphState) -> Dict[str, Any]:
    """
    6a: 전체 플로우 평가 - 전략 Chaining 분석
    
    평가 항목:
    - 문제 해결 전략의 일관성
    - 반복적 개선 과정
    - 코드 발전 흐름
    """
    messages = state.get("messages", [])
    memory_summary = state.get("memory_summary", "")
    
    llm = get_llm()
    evaluator = llm.with_structured_output(HolisticFlowEvaluation)
    
    # 대화 내용 구성
    conversation_text = ""
    for msg in messages:
        if hasattr(msg, 'content'):
            role = getattr(msg, 'type', 'user')
            if role == 'human':
                role = 'User'
            elif role == 'ai':
                role = 'Assistant'
            conversation_text += f"{role}: {msg.content[:500]}...\n\n" if len(msg.content) > 500 else f"{role}: {msg.content}\n\n"
    
    system_prompt = """당신은 AI 코딩 테스트 평가자입니다.
전체 대화 흐름을 분석하여 다음을 평가하세요:

1. 전략 일관성 (strategy_coherence): 문제 해결 접근법이 일관적인가?
2. 문제 해결 접근법 (problem_solving_approach): 체계적으로 문제를 해결했는가?
3. 반복 개선 품질 (iteration_quality): 피드백을 받아 개선했는가?
4. 전체 플로우 점수 (overall_flow_score): 종합 점수

각 항목은 0-100점으로 평가하고, 분석 내용을 작성하세요."""

    prompt = f"메모리 요약:\n{memory_summary}\n\n대화 내용:\n{conversation_text}"
    
    try:
        result = await evaluator.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ])
        
        return {
            "holistic_flow_score": result.overall_flow_score,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        return {
            "holistic_flow_score": None,
            "error_message": f"Holistic flow 평가 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


async def aggregate_turn_scores(state: MainGraphState) -> Dict[str, Any]:
    """
    6b: 누적 실시간 점수 집계
    
    각 턴별 점수를 집계하여 평균 계산
    """
    turn_scores = state.get("turn_scores", {})
    
    if not turn_scores:
        return {
            "aggregate_turn_score": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    # 모든 턴 점수 수집
    all_scores = []
    for turn, scores in turn_scores.items():
        if isinstance(scores, dict) and "turn_score" in scores:
            all_scores.append(scores["turn_score"])
    
    if not all_scores:
        return {
            "aggregate_turn_score": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    # 평균 계산
    avg_score = sum(all_scores) / len(all_scores)
    
    return {
        "aggregate_turn_score": round(avg_score, 2),
        "updated_at": datetime.utcnow().isoformat(),
    }


async def eval_code_performance(state: MainGraphState) -> Dict[str, Any]:
    """
    6c: 코드 성능 평가 (Judge0 연동)
    
    평가 항목:
    - 실행 시간
    - 메모리 사용량
    - 효율성 점수
    """
    code_content = state.get("code_content")
    submission_id = state.get("submission_id")
    
    if not code_content:
        return {
            "code_performance_score": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
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
        
        return {
            "code_performance_score": round(perf_score, 2),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        return {
            "code_performance_score": None,
            "error_message": f"성능 평가 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


async def eval_code_correctness(state: MainGraphState) -> Dict[str, Any]:
    """
    6d: 코드 정확성 평가 (Judge0 연동)
    
    평가 항목:
    - 테스트 케이스 통과율
    - 에지 케이스 처리
    - 정확성 점수
    """
    code_content = state.get("code_content")
    submission_id = state.get("submission_id")
    
    if not code_content:
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
        
        return {
            "code_correctness_score": round(correctness_score, 2),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        return {
            "code_correctness_score": None,
            "error_message": f"정확성 평가 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


async def aggregate_final_scores(state: MainGraphState) -> Dict[str, Any]:
    """
    7: 최종 점수 집계
    
    모든 평가 점수를 취합하여 최종 점수 계산
    """
    holistic_flow_score = state.get("holistic_flow_score")
    aggregate_turn_score = state.get("aggregate_turn_score")
    code_performance_score = state.get("code_performance_score")
    code_correctness_score = state.get("code_correctness_score")
    
    # 가중치 설정
    weights = {
        "prompt": 0.25,  # 프롬프트 활용 (턴 점수 + 플로우)
        "performance": 0.25,  # 성능
        "correctness": 0.50,  # 정확성
    }
    
    # 프롬프트 점수 계산
    prompt_scores = []
    if holistic_flow_score is not None:
        prompt_scores.append(holistic_flow_score)
    if aggregate_turn_score is not None:
        prompt_scores.append(aggregate_turn_score)
    
    prompt_score = sum(prompt_scores) / len(prompt_scores) if prompt_scores else 0
    
    # 성능 점수
    perf_score = code_performance_score if code_performance_score is not None else 0
    
    # 정확성 점수
    correctness_score = code_correctness_score if code_correctness_score is not None else 0
    
    # 총점 계산
    total_score = (
        prompt_score * weights["prompt"] +
        perf_score * weights["performance"] +
        correctness_score * weights["correctness"]
    )
    
    # 등급 계산
    if total_score >= 90:
        grade = "A"
    elif total_score >= 80:
        grade = "B"
    elif total_score >= 70:
        grade = "C"
    elif total_score >= 60:
        grade = "D"
    else:
        grade = "F"
    
    final_scores = {
        "prompt_score": round(prompt_score, 2),
        "performance_score": round(perf_score, 2),
        "correctness_score": round(correctness_score, 2),
        "total_score": round(total_score, 2),
        "grade": grade,
    }
    
    return {
        "final_scores": final_scores,
        "updated_at": datetime.utcnow().isoformat(),
    }



