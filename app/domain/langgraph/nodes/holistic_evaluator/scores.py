import logging
from typing import Dict, Any
from datetime import datetime

from app.domain.langgraph.states import MainGraphState

logger = logging.getLogger(__name__)

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
        
        # Holistic Flow 분석 정보 포함
        holistic_flow_analysis = state.get("holistic_flow_analysis")
        
        final_scores = {
            "prompt_score": round(prompt_score, 2),
            "performance_score": round(perf_score, 2),
            "correctness_score": round(correctness_score, 2),
            "total_score": round(total_score, 2),
            "grade": grade,
        }
        
        # 피드백 정보 포함
        feedback = {}
        if holistic_flow_analysis:
            feedback["holistic_flow_analysis"] = holistic_flow_analysis
        
        logger.info(f"[7. Aggregate Final Scores] 완료 - session_id: {session_id}, 총점: {total_score:.2f}, 등급: {grade}")
        
        result = {
            "final_scores": final_scores,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # 피드백 정보가 있으면 포함
        if feedback:
            result["feedback"] = feedback
        
        return result
        
    except Exception as e:
        logger.error(f"[7. Aggregate Final Scores] 오류 - session_id: {session_id}, error: {str(e)}", exc_info=True)
        return {
            "final_scores": None,
            "error_message": f"최종 점수 집계 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }

