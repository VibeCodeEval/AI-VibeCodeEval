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
    logger.info(f"[7. Aggregate Final Scores] ===== 최종 점수 집계 시작 =====")
    logger.info(f"[7. Aggregate Final Scores] session_id: {session_id}")
    
    try:
        holistic_flow_score = state.get("holistic_flow_score")
        aggregate_turn_score = state.get("aggregate_turn_score")
        code_performance_score = state.get("code_performance_score")
        code_correctness_score = state.get("code_correctness_score")
        
        logger.info(f"[7. Aggregate Final Scores] 입력 점수:")
        logger.info(f"[7. Aggregate Final Scores]   - Holistic Flow Score: {holistic_flow_score}")
        logger.info(f"[7. Aggregate Final Scores]   - Aggregate Turn Score: {aggregate_turn_score}")
        logger.info(f"[7. Aggregate Final Scores]   - Code Performance Score: {code_performance_score}")
        logger.info(f"[7. Aggregate Final Scores]   - Code Correctness Score: {code_correctness_score}")
        
        # 가중치 설정
        weights = {
            "prompt": 0.40,  # 프롬프트 활용 (턴 점수 + 플로우)
            "performance": 0.30,  # 성능
            "correctness": 0.30,  # 정확성
        }
        
        # 프롬프트 점수 계산 (가중 평균)
        # holistic_flow_score: 60%, aggregate_turn_score: 40%
        prompt_score = 0
        if holistic_flow_score is not None and aggregate_turn_score is not None:
            # 둘 다 있는 경우: 가중 평균
            prompt_score = holistic_flow_score * 0.60 + aggregate_turn_score * 0.40
        elif holistic_flow_score is not None:
            # holistic_flow_score만 있는 경우
            prompt_score = holistic_flow_score
        elif aggregate_turn_score is not None:
            # aggregate_turn_score만 있는 경우
            prompt_score = aggregate_turn_score
        
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
        
        # 6c 노드 상세 정보 (Correctness & Performance)
        test_cases_passed = state.get("test_cases_passed")
        test_cases_total = state.get("test_cases_total")
        execution_time = state.get("execution_time")
        memory_used_mb = state.get("memory_used_mb")
        skip_performance = state.get("skip_performance", False)
        skip_reason = state.get("skip_reason")
        
        final_scores = {
            "prompt_score": round(prompt_score, 2),
            "performance_score": round(perf_score, 2),
            "correctness_score": round(correctness_score, 2),
            "total_score": round(total_score, 2),
            "grade": grade,
            # 6c 노드 상세 정보
            "correctness_details": {
                "test_cases_passed": test_cases_passed,
                "test_cases_total": test_cases_total,
                "pass_rate": round((test_cases_passed / test_cases_total * 100) if test_cases_total and test_cases_total > 0 else 0, 1),
            } if test_cases_total is not None else None,
            "performance_details": {
                "execution_time": execution_time,
                "memory_used_mb": memory_used_mb,
                "skip_performance": skip_performance,
                "skip_reason": skip_reason,
            } if not skip_performance or execution_time is not None else None,
        }
        
        # 피드백 정보 포함
        feedback = {}
        if holistic_flow_analysis:
            feedback["holistic_flow_analysis"] = holistic_flow_analysis
        
        logger.info(f"[7. Aggregate Final Scores] ===== 최종 점수 집계 완료 =====")
        logger.info(f"[7. Aggregate Final Scores] Prompt Score: {prompt_score:.2f} (가중치: 40%)")
        logger.info(f"[7. Aggregate Final Scores] Performance Score: {perf_score:.2f} (가중치: 30%)")
        logger.info(f"[7. Aggregate Final Scores] Correctness Score: {correctness_score:.2f} (가중치: 30%)")
        logger.info(f"[7. Aggregate Final Scores] Total Score: {total_score:.2f}")
        logger.info(f"[7. Aggregate Final Scores] Grade: {grade}")
        
        # 제출 완료 시 Submission 생성 및 Score 저장
        submission_id = state.get("submission_id")
        exam_id = state.get("exam_id")
        participant_id = state.get("participant_id")
        spec_id = state.get("spec_id")
        code_content = state.get("code_content")
        
        try:
            from app.infrastructure.persistence.session import get_db_context
            from app.infrastructure.repositories.session_repository import SessionRepository
            from app.infrastructure.repositories.submission_repository import SubmissionRepository
            from app.infrastructure.persistence.models.enums import SubmissionStatusEnum
            from decimal import Decimal
            import hashlib
            
            # session_id를 PostgreSQL id로 변환 (Redis session_id: "session_123" -> PostgreSQL id: 123)
            postgres_session_id = int(session_id.replace("session_", "")) if session_id.startswith("session_") else None
            
            if postgres_session_id and exam_id and participant_id and spec_id and code_content:
                async with get_db_context() as db:
                    submission_repo = SubmissionRepository(db)
                    session_repo = SessionRepository(db)
                    
                    # 1. Submission 조회 및 업데이트
                    # BE에서 생성한 submission을 사용하므로, submission_id가 반드시 있어야 함
                    if not submission_id:
                        logger.error(
                            f"[7. Aggregate Final Scores] Submission ID가 없습니다 - "
                            f"exam_id: {exam_id}, participant_id: {participant_id}"
                        )
                        raise ValueError("Submission ID is required. BE에서 생성한 submission ID가 전달되어야 합니다.")
                    
                    # 기존 submission 조회 및 상태 업데이트
                    submission = await submission_repo.get_submission_by_id(submission_id)
                    if not submission:
                        logger.error(
                            f"[7. Aggregate Final Scores] Submission을 찾을 수 없습니다 - "
                            f"submission_id: {submission_id}, exam_id: {exam_id}, participant_id: {participant_id}"
                        )
                        raise ValueError(f"Submission not found: submission_id={submission_id}")
                    
                    # submission 상태 업데이트
                    await submission_repo.update_submission_status(
                        submission_id=submission_id,
                        status=SubmissionStatusEnum.DONE
                    )
                    logger.info(
                        f"[7. Aggregate Final Scores] Submission 상태 업데이트 완료 - "
                        f"submission_id: {submission_id}, status: DONE"
                    )
                    
                    # 2. Score 저장
                    score = await submission_repo.create_or_update_score(
                        submission_id=submission_id,
                        prompt_score=Decimal(str(round(prompt_score, 2))),
                        perf_score=Decimal(str(round(perf_score, 2))),
                        correctness_score=Decimal(str(round(correctness_score, 2))),
                        total_score=Decimal(str(round(total_score, 2))),
                        rubric_json={
                            "prompt_score": round(prompt_score, 2),
                            "performance_score": round(perf_score, 2),
                            "correctness_score": round(correctness_score, 2),
                            "total_score": round(total_score, 2),
                            "grade": grade,
                            "weights": weights,
                            "holistic_flow_score": holistic_flow_score,
                            "aggregate_turn_score": aggregate_turn_score,
                            "code_performance_score": code_performance_score,
                            "code_correctness_score": code_correctness_score,
                            "correctness_details": final_scores.get("correctness_details"),
                            "performance_details": final_scores.get("performance_details"),
                            "holistic_flow_analysis": holistic_flow_analysis,
                        }
                    )
                    logger.info(
                        f"[7. Aggregate Final Scores] Score 저장 완료 - "
                        f"submission_id: {submission_id}, total_score: {total_score:.2f}"
                    )
                    
                    # 3. 세션 종료 (ended_at 설정)
                    await session_repo.end_session(postgres_session_id)
                    
                    await db.commit()
                    logger.info(
                        f"[7. Aggregate Final Scores] 세션 종료 완료 - "
                        f"session_id: {postgres_session_id}, ended_at 설정됨"
                    )
            else:
                logger.warning(
                    f"[7. Aggregate Final Scores] Submission/Score 저장 건너뜀 - "
                    f"필수 정보 부족: postgres_session_id={postgres_session_id}, "
                    f"exam_id={exam_id}, participant_id={participant_id}, spec_id={spec_id}, code_content={'있음' if code_content else '없음'}"
                )
        except Exception as e:
            # Submission/Score 저장 실패해도 평가는 완료되었으므로 경고만
            logger.warning(
                f"[7. Aggregate Final Scores] Submission/Score 저장 실패 (평가는 완료됨) - "
                f"session_id: {session_id}, error: {str(e)}",
                exc_info=True
            )
        
        result = {
            "final_scores": final_scores,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # submission_id를 State에 저장
        if submission_id:
            result["submission_id"] = submission_id
        
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

