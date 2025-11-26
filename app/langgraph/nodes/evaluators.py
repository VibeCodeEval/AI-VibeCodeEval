"""
평가 노드들
- 6a: Eval Holistic Flow (전략 Chaining 분석)
- 6b: Aggregate Turn Scores (누적 실시간 점수)
- 6c: Eval Code Performance (Judge0)
- 6d: Eval Code Correctness (Judge0)
- 7: Aggregate Final Scores (모든 점수 취합)
"""
import logging
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

logger = logging.getLogger(__name__)


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

다음은 사용자의 턴별 대화 로그입니다. 각 턴의 의도, 프롬프트 요약, AI 추론을 분석하세요.

평가 척도 (Chaining 평가 - 전략):

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


async def aggregate_turn_scores(state: MainGraphState) -> Dict[str, Any]:
    """
    6b: 누적 실시간 점수 집계
    
    각 턴별 점수를 집계하여 평균 계산
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[6b. Aggregate Turn Scores] 진입 - session_id: {session_id}")
    
    try:
        turn_scores = state.get("turn_scores", {})
        
        if not turn_scores:
            logger.warning(f"[6b. Aggregate Turn Scores] 턴 점수 없음 - session_id: {session_id}")
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
            logger.warning(f"[6b. Aggregate Turn Scores] 유효한 점수 없음 - session_id: {session_id}")
            return {
                "aggregate_turn_score": None,
                "updated_at": datetime.utcnow().isoformat(),
            }
        
        # 평균 계산
        avg_score = sum(all_scores) / len(all_scores)
        
        logger.info(f"[6b. Aggregate Turn Scores] 완료 - session_id: {session_id}, 턴 개수: {len(all_scores)}, 평균: {avg_score:.2f}")
        
        return {
            "aggregate_turn_score": round(avg_score, 2),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"[6b. Aggregate Turn Scores] 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
        return {
            "aggregate_turn_score": None,
            "error_message": f"턴 점수 집계 실패: {str(e)}",
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


async def aggregate_final_scores(state: MainGraphState) -> Dict[str, Any]:
    """
    7: 최종 점수 집계
    
    모든 평가 점수를 취합하여 최종 점수 계산
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[7. Aggregate Final Scores] 진입 - session_id: {session_id}")
    
    try:
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
        
        logger.info(f"[7. Aggregate Final Scores] 완료 - session_id: {session_id}, 총점: {total_score:.2f}, 등급: {grade}")
        
        return {
            "final_scores": final_scores,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"[7. Aggregate Final Scores] 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
        return {
            "final_scores": None,
            "error_message": f"최종 점수 집계 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }



