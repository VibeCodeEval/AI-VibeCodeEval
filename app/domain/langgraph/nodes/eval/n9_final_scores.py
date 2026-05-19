import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.core.config import settings
from app.domain.langgraph.nodes.eval.rubric_json_serializers import (
    build_correctness_details,
    build_performance_details,
    build_reference_cc_summary,
    build_tc_summary,
)
from app.domain.langgraph.nodes.eval.turn_evaluation_details import (
    build_turn_evaluation_details,
)
from app.domain.langgraph.states import MainGraphState

logger = logging.getLogger(__name__)


def _submission_avg_cc(code_quality_metrics: Optional[Dict[str, Any]]) -> float:
    """N6 code_quality_metrics에서 제출 코드 avg_cc (레거시 v2_metrics 경로 폴백)."""
    if not code_quality_metrics:
        return 0.0
    radon = code_quality_metrics.get("radon_cc")
    if isinstance(radon, dict) and radon.get("avg_cc") is not None:
        try:
            return float(radon["avg_cc"])
        except (TypeError, ValueError):
            pass
    legacy = (code_quality_metrics.get("v2_metrics") or {}).get("radon_cc")
    if isinstance(legacy, dict) and legacy.get("avg_cc") is not None:
        try:
            return float(legacy["avg_cc"])
        except (TypeError, ValueError):
            pass
    delta = code_quality_metrics.get("delta_cc") or {}
    if delta.get("v2_avg_cc") is not None:
        try:
            return float(delta["v2_avg_cc"])
        except (TypeError, ValueError):
            pass
    return 0.0


async def _load_turn_evaluations_for_rubric(
    db: Any,
    postgres_session_id: int,
    redis_session_id: str,
) -> list:
    """prompt_evaluations(TURN_EVAL) 행과 동일한 details → rubric_json.turn_evaluations."""
    from sqlalchemy import select, text

    from app.infrastructure.persistence.models.enums import EvaluationTypeEnum
    from app.infrastructure.persistence.models.sessions import PromptEvaluation

    query = (
        select(PromptEvaluation)
        .where(
            PromptEvaluation.session_id == postgres_session_id,
            text("prompt_evaluations.evaluation_type::text = :eval_type"),
        )
        .order_by(PromptEvaluation.turn)
    )
    result = await db.execute(
        query.params(eval_type=EvaluationTypeEnum.TURN_EVAL.value)
    )
    rows = result.scalars().all()
    if rows:
        return [
            {
                "turn": row.turn,
                "evaluation_type": EvaluationTypeEnum.TURN_EVAL.value,
                "details": row.details if isinstance(row.details, dict) else {},
            }
            for row in rows
            if row.turn is not None
        ]

    try:
        from app.infrastructure.cache.redis_client import RedisClient

        redis_client = RedisClient()
        turn_logs = await redis_client.get_all_turn_logs(redis_session_id)
    except Exception as e:
        logger.warning(
            f"[N9. Final Scores] turn_evaluations Redis 폴백 실패 - {e}"
        )
        return []

    out = []
    for turn_key in sorted(turn_logs.keys(), key=lambda k: int(k) if str(k).isdigit() else 0):
        turn_log = turn_logs.get(turn_key)
        if not isinstance(turn_log, dict):
            continue
        try:
            turn_num = int(turn_key)
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "turn": turn_num,
                "evaluation_type": EvaluationTypeEnum.TURN_EVAL.value,
                "details": build_turn_evaluation_details(turn_log),
            }
        )
    return out


async def aggregate_final_scores(state: MainGraphState) -> Dict[str, Any]:
    """
    Node 9: 최종 점수 집계

    모든 평가 점수를 취합하여 최종 점수 계산
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[N9. Final Scores] ===== 최종 점수 집계 시작 =====")
    logger.info(f"[N9. Final Scores] session_id: {session_id}")

    try:
        holistic_flow_score = state.get("holistic_flow_score")
        r4_context_maintenance_score = state.get("r4_context_maintenance_score")
        aggregate_turn_score = state.get("aggregate_turn_score")
        
        # aggregate_turn_score가 없으면 turn_scores에서 턴 점수 평균 계산 (임시 N8 동작용)
        if aggregate_turn_score is None:
            turn_scores = state.get("turn_scores", {})
            if turn_scores:
                valid_scores = [s.get("turn_score", 0) for s in turn_scores.values() if isinstance(s, dict) and "turn_score" in s]
                if valid_scores:
                    aggregate_turn_score = sum(valid_scores) / len(valid_scores)
                    
        code_performance_score = state.get("code_performance_score")
        code_correctness_score = state.get("code_correctness_score")

        cc_max = float(settings.CODE_CORRECTNESS_MAX_POINTS)
        try:
            correctness_raw_pre = float(
                code_correctness_score if code_correctness_score is not None else 0.0
            )
        except (TypeError, ValueError):
            correctness_raw_pre = 0.0
        # 구버전 N5(0~100) 체크포인트: 값이 CODE_CORRECTNESS_MAX_POINTS를 넘으면 이미 0~100 스케일로 간주
        if correctness_raw_pre > cc_max + 1e-6:
            correctness_normalized_pre = min(100.0, correctness_raw_pre)
        else:
            correctness_normalized_pre = (
                (correctness_raw_pre / cc_max) * 100.0 if cc_max > 0 else 0.0
            )

        integrated_score = state.get("integrated_score")
        integrated_evaluation = state.get("integrated_evaluation")
        code_quality_metrics = state.get("code_quality_metrics")
        code_eval_report = state.get("code_eval_report")

        logger.info(f"[N9. Final Scores] 입력 점수:")
        logger.info(f"[N9. Final Scores]   - Holistic Flow Score: {holistic_flow_score}")
        logger.info(
            f"[N9. Final Scores]   - R4 Context Maintenance: {r4_context_maintenance_score}"
        )
        logger.info(f"[N9. Final Scores]   - Aggregate Turn Score: {aggregate_turn_score}")
        logger.info(f"[N9. Final Scores]   - Code Performance Score: {code_performance_score}")
        logger.info(
            f"[N9. Final Scores]   - Code Correctness Score: {code_correctness_score} "
            f"(만점 {cc_max}, 가중용 환산 {correctness_normalized_pre:.2f}/100)"
        )
        logger.info(f"[N9. Final Scores]   - Integrated Score: {integrated_score}")

        weights = {
            "prompt": 0.40,
            "correctness": 0.40,
            "performance": 0.20,
        }

        prompt_score = 0
        if holistic_flow_score is not None and aggregate_turn_score is not None:
            prompt_score = holistic_flow_score * 0.60 + aggregate_turn_score * 0.40
        elif holistic_flow_score is not None:
            prompt_score = holistic_flow_score
        elif aggregate_turn_score is not None:
            prompt_score = aggregate_turn_score

        if integrated_score is not None and integrated_score >= 0:
            if prompt_score > 0:
                prompt_score = prompt_score * 0.5 + integrated_score * 0.5
            else:
                prompt_score = integrated_score

        # N8 R4(맥락 유지) — 루브릭 가중 20%를 프롬프트 축에 반영 (.maestro/RUBRIC_MIGRATION_PLAN.md)
        if r4_context_maintenance_score is not None:
            try:
                r4 = float(r4_context_maintenance_score)
            except (TypeError, ValueError):
                r4 = None
            if r4 is not None:
                prompt_score = prompt_score * 0.8 + r4 * 0.2

        perf_score = code_performance_score if code_performance_score is not None else 0

        correctness_raw = correctness_raw_pre
        correctness_normalized = correctness_normalized_pre
        if correctness_raw_pre > cc_max + 1e-6:
            correctness_score = round((correctness_raw_pre / 100.0) * cc_max, 2)
        else:
            correctness_score = correctness_raw_pre

        # legacy 호환성 (구조 변경 전 N5에서 올라온 데이터)
        if not code_quality_metrics:
            code_quality_metrics = (
                (integrated_evaluation or {}).get("code_quality_metrics")
                if isinstance(integrated_evaluation, dict)
                else None
            )

        rubric_breakdown = (
            (integrated_evaluation or {}).get("rubric_breakdown")
            if isinstance(integrated_evaluation, dict)
            else None
        )
        delta_cc_pct = 0.0
        ast_ok = False
        ast_applicable = False
        avg_cc = 0.0
        junior_grade = False
        if code_quality_metrics:
            delta_cc = code_quality_metrics.get("delta_cc", {})
            delta_cc_pct = delta_cc.get("delta_cc_pct", 0.0)
            ast_ok = code_quality_metrics.get("ast_pattern_matched", False)
            ast_applicable = code_quality_metrics.get("ast_applicable", False)
            junior_grade = code_quality_metrics.get("junior_grade", False)
            avg_cc = _submission_avg_cc(code_quality_metrics)

        if code_quality_metrics is not None and perf_score > 0:
            cc_bonus = (
                1.0
                if avg_cc <= 5
                else (0.6 if avg_cc <= 8 else 0.2)
            )
            perf_score = round(perf_score * (0.8 + 0.2 * cc_bonus), 2)

        total_score = (
            prompt_score * weights["prompt"]
            + correctness_normalized * weights["correctness"]
            + perf_score * weights["performance"]
        )

        if correctness_normalized < 100:
            grade = "F" if correctness_normalized < 60 else "D"
        else:
            if code_quality_metrics is not None:
                if delta_cc_pct <= 10 and ast_ok:
                    grade = "A"
                elif delta_cc_pct <= 30 and avg_cc < 8:
                    grade = "B"
                elif delta_cc_pct > 60 or (ast_applicable and not ast_ok):
                    grade = "C"
                else:
                    grade = "C"
            else:
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

        holistic_flow_analysis = state.get("holistic_flow_analysis")

        test_cases_passed = state.get("test_cases_passed")
        test_cases_total = state.get("test_cases_total")
        execution_time = state.get("execution_time")
        memory_used_mb = state.get("memory_used_mb")
        time_limit_sec = state.get("time_limit_sec")
        memory_limit_mb = state.get("memory_limit_mb")
        skip_performance = state.get("skip_performance", False)
        skip_reason = state.get("skip_reason")
        test_case_results = state.get("test_case_results")
        tc_summary = build_tc_summary(
            test_cases_passed=test_cases_passed,
            test_cases_total=test_cases_total,
            test_case_results=test_case_results,
        )
        reference_cc_summary = build_reference_cc_summary(code_quality_metrics)

        v21_summary = None
        if rubric_breakdown or code_quality_metrics:
            v21_summary = {}
            if rubric_breakdown:
                v21_summary["rubric_breakdown"] = rubric_breakdown
            if code_quality_metrics:
                v21_summary["code_quality_metrics"] = {
                    "delta_cc_pct": (code_quality_metrics.get("delta_cc") or {}).get("delta_cc_pct"),
                    "ast_pattern_matched": code_quality_metrics.get("ast_pattern_matched"),
                    "ast_applicable": code_quality_metrics.get("ast_applicable"),
                    "junior_grade": code_quality_metrics.get("junior_grade"),
                    "has_v1": code_quality_metrics.get("has_v1"),
                }

        final_scores = {
            "prompt_score": round(prompt_score, 2),
            "performance_score": round(perf_score, 2),
            "correctness_score": round(correctness_score, 2),
            "total_score": round(total_score, 2),
            "grade": grade,
            "v21_summary": v21_summary,
            "correctness_details": build_correctness_details(
                test_cases_passed=test_cases_passed,
                test_cases_total=test_cases_total,
                correctness_reasoning=state.get("correctness_reasoning"),
                test_case_results=test_case_results,
            ),
            "performance_details": build_performance_details(
                execution_time=execution_time,
                memory_used_mb=memory_used_mb,
                time_limit_sec=time_limit_sec,
                memory_limit_mb=memory_limit_mb,
                skip_performance=bool(skip_performance),
                skip_reason=skip_reason,
                test_case_results=test_case_results,
            ),
            "tc_summary": tc_summary,
            "reference_cc_summary": reference_cc_summary,
        }

        feedback = {}
        if holistic_flow_analysis:
            feedback["holistic_flow_analysis"] = holistic_flow_analysis

        logger.info(f"[N9. Final Scores] ===== 최종 점수 집계 완료 =====")
        logger.info(f"[N9. Final Scores] Prompt Score: {prompt_score:.2f} (40%)")
        logger.info(
            f"[N9. Final Scores] Correctness Score: {correctness_score:.2f}/{cc_max} "
            f"(가중 반영 {correctness_normalized:.2f}/100) (40%)"
        )
        logger.info(f"[N9. Final Scores] Performance Score: {perf_score:.2f} (20%)")
        logger.info(f"[N9. Final Scores] Total Score: {total_score:.2f}")
        logger.info(f"[N9. Final Scores] Grade: {grade}")

        submission_id = state.get("submission_id")
        exam_id = state.get("exam_id")
        participant_id = state.get("participant_id")
        spec_id = state.get("spec_id")
        code_content = state.get("code_content")

        try:
            import hashlib
            from decimal import Decimal

            from app.infrastructure.persistence.models.enums import \
                SubmissionStatusEnum
            from app.infrastructure.persistence.session import get_db_context
            from app.infrastructure.repositories.session_repository import \
                SessionRepository
            from app.infrastructure.repositories.submission_repository import \
                SubmissionRepository

            postgres_session_id = (
                int(session_id.replace("session_", ""))
                if session_id.startswith("session_")
                else None
            )

            if (
                postgres_session_id
                and exam_id
                and participant_id
                and spec_id
                and code_content
            ):
                async with get_db_context() as db:
                    submission_repo = SubmissionRepository(db)
                    session_repo = SessionRepository(db)

                    if not submission_id:
                        logger.error(
                            f"[N9. Final Scores] Submission ID가 없습니다 - "
                            f"exam_id: {exam_id}, participant_id: {participant_id}"
                        )
                        raise ValueError(
                            "Submission ID is required. BE에서 생성한 submission ID가 전달되어야 합니다."
                        )

                    submission = await submission_repo.get_submission_by_id(
                        submission_id
                    )
                    if not submission:
                        logger.error(
                            f"[N9. Final Scores] Submission을 찾을 수 없습니다 - "
                            f"submission_id: {submission_id}, exam_id: {exam_id}, participant_id: {participant_id}"
                        )
                        raise ValueError(
                            f"Submission not found: submission_id={submission_id}"
                        )

                    await submission_repo.update_submission_status(
                        submission_id=submission_id, status=SubmissionStatusEnum.DONE
                    )
                    logger.info(
                        f"[N9. Final Scores] Submission 상태 업데이트 완료 - "
                        f"submission_id: {submission_id}, status: DONE"
                    )

                    turn_evaluations = await _load_turn_evaluations_for_rubric(
                        db,
                        postgres_session_id,
                        session_id,
                    )

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
                            "r4_context_maintenance_score": r4_context_maintenance_score,
                            "aggregate_turn_score": aggregate_turn_score,
                            "code_performance_score": code_performance_score,
                            "code_correctness_score": code_correctness_score,
                            "correctness_details": final_scores.get(
                                "correctness_details"
                            ),
                            "performance_details": final_scores.get(
                                "performance_details"
                            ),
                            "tc_summary": final_scores.get("tc_summary"),
                            "reference_cc_summary": final_scores.get(
                                "reference_cc_summary"
                            ),
                            "turn_evaluations": turn_evaluations,
                            "holistic_flow_analysis": holistic_flow_analysis,
                            "integrated_score": integrated_score,
                            "integrated_evaluation": integrated_evaluation,
                            "code_quality_metrics": code_quality_metrics,
                            "code_eval_report": code_eval_report,
                            "session_id": postgres_session_id,
                            # 토론·턴별 맥락 (Debate 결론 해석용 — DB 단일 조회로 추적 가능)
                            "debate_log": state.get("debate_log"),
                            "debate_initial_opinions": state.get(
                                "debate_initial_opinions"
                            ),
                            "debate_rebuttals": state.get("debate_rebuttals"),
                            "turn_scores": state.get("turn_scores"),
                        },
                    )
                    logger.info(
                        f"[N9. Final Scores] Score 저장 완료 - "
                        f"submission_id: {submission_id}, total_score: {total_score:.2f}"
                    )

                    await session_repo.end_session(postgres_session_id)

                    await db.commit()
                    logger.info(
                        f"[N9. Final Scores] 세션 종료 완료 - "
                        f"session_id: {postgres_session_id}, ended_at 설정됨"
                    )
            else:
                logger.warning(
                    f"[N9. Final Scores] Submission/Score 저장 건너뜀 - "
                    f"필수 정보 부족: postgres_session_id={postgres_session_id}, "
                    f"exam_id={exam_id}, participant_id={participant_id}, spec_id={spec_id}, code_content={'있음' if code_content else '없음'}"
                )
        except Exception as e:
            logger.warning(
                f"[N9. Final Scores] Submission/Score 저장 실패 (평가는 완료됨) - "
                f"session_id: {session_id}, error: {str(e)}",
                exc_info=True,
            )

        result = {
            "final_scores": final_scores,
            "updated_at": datetime.utcnow().isoformat(),
        }

        if submission_id:
            result["submission_id"] = submission_id

        if feedback:
            result["feedback"] = feedback

        return result

    except Exception as e:
        logger.error(
            f"[N9. Final Scores] 오류 - session_id: {session_id}, error: {str(e)}",
            exc_info=True,
        )
        return {
            "final_scores": None,
            "error_message": f"최종 점수 집계 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }
