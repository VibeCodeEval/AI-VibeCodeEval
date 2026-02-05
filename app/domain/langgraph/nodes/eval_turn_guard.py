"""
노드 4: Eval Turn Guard (제출 시)
제출 시 모든 턴의 평가가 완료되었는지 확인하고, 누락된 턴을 재평가
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.domain.langgraph.states import MainGraphState
from app.infrastructure.cache.redis_client import redis_client

logger = logging.getLogger(__name__)


async def eval_turn_submit_guard(state: MainGraphState) -> Dict[str, Any]:
    """
    제출 시 4번 가드 노드

    역할:
    1. State의 messages에서 모든 턴 추출 (1 ~ current_turn-1)
    2. 각 턴에 대해 Eval Turn SubGraph를 동기적으로 실행
    3. 모든 턴 평가 완료 후 turn_scores 반환
    4. 다음 노드(평가 플로우)로 진행

    ⚠️ 중요: 일반 채팅에서는 평가를 하지 않으므로, 제출 시 모든 턴을 처음부터 평가합니다.
    """
    session_id = state.get("session_id", "unknown")
    current_turn = state.get("current_turn", 0)

    logger.info("")
    logger.info("=" * 80)
    logger.info(
        f"[4. Eval Turn Guard] 진입 - session_id: {session_id}, 현재 턴: {current_turn}"
    )
    logger.info("=" * 80)
    logger.info("")

    try:
        # ★ Submit 시 State의 messages에서 모든 턴을 추출하여 확실하게 평가
        # 일반 채팅에서는 평가를 하지 않으므로, 제출 시 모든 턴을 처음부터 평가
        logger.info(
            f"[4. Eval Turn Guard] State 기반 모든 턴 평가 시작 - session_id: {session_id}, current_turn: {current_turn}"
        )

        # State의 messages에서 모든 턴 추출
        messages = state.get("messages", [])
        logger.info(f"[4. Eval Turn Guard] 전체 messages 개수: {len(messages)}")

        # 디버깅: 메시지 구조 확인
        for idx, msg in enumerate(messages):
            if isinstance(msg, dict):
                logger.debug(
                    f"[4. Eval Turn Guard] 메시지 {idx} (dict): turn={msg.get('turn')}, role={msg.get('role')}, type={msg.get('type')}, content_len={len(str(msg.get('content', '')))}"
                )
            else:
                msg_turn = getattr(msg, "turn", None)
                msg_role = getattr(msg, "role", None)
                msg_type = getattr(msg, "type", None) if hasattr(msg, "type") else None
                msg_content = getattr(msg, "content", None)
                logger.debug(
                    f"[4. Eval Turn Guard] 메시지 {idx} (object): turn={msg_turn}, role={msg_role}, type={msg_type}, content_len={len(str(msg_content)) if msg_content else 0}"
                )

        # 제출 턴(current_turn)은 평가하지 않으므로, 1 ~ (current_turn - 1)만 평가
        turns_to_evaluate = list(range(1, current_turn))
        logger.info("")
        logger.info(f"[4. Eval Turn Guard] ⭐ 평가 대상 턴: {turns_to_evaluate}")
        logger.info(
            f"[4. Eval Turn Guard] ⭐ 총 {len(turns_to_evaluate)}개 턴 평가 예정"
        )
        logger.info("")

        if not turns_to_evaluate:
            logger.info(f"[4. Eval Turn Guard] 평가할 턴이 없음 (첫 제출)")
            logger.info("")
            return {
                "turn_scores": {},
                "updated_at": datetime.utcnow().isoformat(),
            }

        # 모든 턴 평가
        # State의 messages에서 turn 정보로 직접 메시지 찾기 (Redis turn_mapping 불필요)
        logger.info("-" * 80)
        for idx, turn in enumerate(turns_to_evaluate, 1):
            logger.info("")
            logger.info(
                f"[4. Eval Turn Guard] [{idx}/{len(turns_to_evaluate)}] 턴 {turn} 평가 시작..."
            )
            logger.info("")

            human_msg = None
            ai_msg = None

            # State의 messages에서 turn 정보로 직접 검색
            # dict 형태 또는 LangChain BaseMessage 객체 모두 지원
            for msg in messages:
                # turn 정보 추출
                msg_turn = None
                msg_role = None
                msg_content = None

                if isinstance(msg, dict):
                    msg_turn = msg.get("turn")
                    msg_role = msg.get("role") or msg.get(
                        "type"
                    )  # role 우선, 없으면 type
                    msg_content = msg.get("content")
                else:
                    # LangChain BaseMessage 객체
                    msg_turn = getattr(msg, "turn", None)
                    # role 속성 사용 (writer.py에서 role 속성을 추가함)
                    msg_role = getattr(msg, "role", None)
                    # content 추출
                    if hasattr(msg, "content"):
                        msg_content = msg.content
                    else:
                        msg_content = str(msg)

                # 디버깅: 메시지 정보 로깅
                logger.debug(
                    f"[4. Eval Turn Guard] 메시지 확인 - turn: {msg_turn}, role: {msg_role}, content_len: {len(msg_content) if msg_content else 0}"
                )

                # 해당 턴의 메시지인지 확인
                # turn이 None이면 메시지 순서로 추론 (인덱스 0,1 = turn 1, 인덱스 2,3 = turn 2, ...)
                msg_idx = messages.index(msg) if msg in messages else -1
                inferred_turn = (msg_idx // 2) + 1 if msg_idx >= 0 else None

                # turn이 일치하거나, turn이 None이고 추론된 turn이 일치하는 경우
                if msg_turn == turn or (msg_turn is None and inferred_turn == turn):
                    # role 매핑: "user"/"human" -> human, "assistant"/"ai" -> ai
                    if msg_role in ["user", "human"]:
                        human_msg = msg_content
                        logger.debug(
                            f"[4. Eval Turn Guard] 턴 {turn} Human 메시지 발견 (turn: {msg_turn}, 추론: {inferred_turn})"
                        )
                    elif msg_role in ["assistant", "ai"]:
                        ai_msg = msg_content
                        logger.debug(
                            f"[4. Eval Turn Guard] 턴 {turn} AI 메시지 발견 (turn: {msg_turn}, 추론: {inferred_turn})"
                        )

                    # 둘 다 찾았으면 중단
                    if human_msg and ai_msg:
                        break

            if human_msg and ai_msg:
                logger.info(
                    f"[4. Eval Turn Guard] 턴 {turn} 메시지 추출 성공 - State에서 직접 조회"
                )
            else:
                logger.warning(
                    f"[4. Eval Turn Guard] 턴 {turn} - State에서 메시지 찾기 실패 (human: {bool(human_msg)}, ai: {bool(ai_msg)})"
                )

            # 평가 실행
            if human_msg and ai_msg:
                logger.info(f"[4. Eval Turn Guard] ===== 턴 {turn} 평가 시작 =====")
                logger.info(f"[4. Eval Turn Guard] 사용자 메시지: {human_msg[:100]}...")
                logger.info(f"[4. Eval Turn Guard] AI 응답: {ai_msg[:100]}...")
                logger.info("")

                # 평가 실행 및 결과 받기
                eval_result = await _evaluate_turn_sync(
                    session_id=session_id,
                    turn=turn,
                    human_message=human_msg,
                    ai_message=ai_msg,
                    problem_context=state.get("problem_context"),
                )

                # 평가 결과 요약 출력
                logger.info("")
                logger.info("=" * 80)
                logger.info(f"[4. Eval Turn Guard] ===== 턴 {turn} 평가 완료 ✓ =====")

                if eval_result:
                    intent_type = eval_result.get("intent_type", "UNKNOWN")
                    turn_score = eval_result.get("turn_score", 0)
                    intent_confidence = eval_result.get("intent_confidence", 0.0)
                    rubrics = eval_result.get("rubrics", [])
                    comprehensive_reasoning = eval_result.get(
                        "comprehensive_reasoning", ""
                    )

                    logger.info(f"[4. Eval Turn Guard] 📊 턴 {turn} 평가 결과 요약:")
                    logger.info(
                        f"[4. Eval Turn Guard]   • 의도: {intent_type} (신뢰도: {intent_confidence:.2f})"
                    )
                    logger.info(f"[4. Eval Turn Guard]   • 점수: {turn_score:.2f}점")

                    if rubrics:
                        logger.info(
                            f"[4. Eval Turn Guard]   • 루브릭 평가 ({len(rubrics)}개):"
                        )
                        for rubric in rubrics[:5]:  # 최대 5개만 표시
                            rubric_name = rubric.get(
                                "name", rubric.get("criterion", "")
                            )
                            rubric_score = rubric.get("score", 0)
                            logger.info(
                                f"[4. Eval Turn Guard]     - {rubric_name}: {rubric_score:.2f}점"
                            )
                        if len(rubrics) > 5:
                            logger.info(
                                f"[4. Eval Turn Guard]     ... 외 {len(rubrics) - 5}개"
                            )

                    if comprehensive_reasoning:
                        reasoning_preview = (
                            comprehensive_reasoning[:200] + "..."
                            if len(comprehensive_reasoning) > 200
                            else comprehensive_reasoning
                        )
                        logger.info(
                            f"[4. Eval Turn Guard]   • 평가 내용: {reasoning_preview}"
                        )
                else:
                    logger.warning(f"[4. Eval Turn Guard]   ⚠️ 평가 결과 정보 없음")

                logger.info("=" * 80)
                logger.info("")
            else:
                logger.error("")
                logger.error(
                    f"[4. Eval Turn Guard] 턴 {turn} 메시지 추출 실패 - human: {bool(human_msg)}, ai: {bool(ai_msg)}"
                )
                logger.error(f"[4. Eval Turn Guard] 턴 {turn} - 평가 불가능 ✗")
                logger.error("")

        logger.info("")
        logger.info("-" * 80)
        logger.info(
            f"[4. Eval Turn Guard] ✅ 모든 턴 평가 완료 - session_id: {session_id}, 평가 완료: {len(turns_to_evaluate)}턴"
        )
        logger.info("-" * 80)
        logger.info("")

        # Redis에서 최신 turn_logs 조회 (평가 결과 반영)
        updated_turn_logs = await redis_client.get_all_turn_logs(session_id)

        # turn_logs를 turn_scores로 변환하여 state 업데이트
        # 6b 노드에서 {"turn_score": ...} 형식을 기대하므로 딕셔너리로 저장
        turn_scores = {}
        for turn_key, turn_log in updated_turn_logs.items():
            if isinstance(turn_log, dict) and "prompt_evaluation_details" in turn_log:
                score = turn_log["prompt_evaluation_details"].get("score", 0)
                turn_scores[turn_key] = {
                    "turn_score": score  # 6b 노드가 기대하는 형식으로 변경
                }

        logger.info(
            f"[4. Eval Turn Guard] 완료 - session_id: {session_id}, 최종 턴 로그 개수: {len(updated_turn_logs)}, turn_scores: {turn_scores}"
        )
        logger.info("")
        logger.info("=" * 80)
        logger.info(f"[4. Eval Turn Guard] 종료")
        logger.info("=" * 80)
        logger.info("")

        return {
            "turn_scores": turn_scores,
            "updated_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error("")
        logger.error(
            f"[4. Eval Turn Guard] 오류 - session_id: {session_id}, error: {str(e)}",
            exc_info=True,
        )
        logger.error("")
        return {
            "error_message": f"턴 평가 가드 오류: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


async def _evaluate_turn_sync(
    session_id: str,
    turn: int,
    human_message: str,
    ai_message: str,
    problem_context: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    특정 턴을 동기적으로 평가

    제출 시 모든 턴을 평가하기 위해 사용
    """
    try:
        from app.domain.langgraph.states import EvalTurnState
        from app.domain.langgraph.subgraph_eval_turn import \
            create_eval_turn_subgraph

        # Eval Turn SubGraph 생성
        eval_turn_subgraph = create_eval_turn_subgraph()

        # SubGraph 입력 준비
        turn_state: EvalTurnState = {
            "session_id": session_id,
            "turn": turn,
            "human_message": human_message,
            "ai_message": ai_message,
            "problem_context": problem_context,  # 문제 정보 전달
            "is_guardrail_failed": False,
            "guardrail_message": None,
            "intent_type": None,
            "intent_confidence": 0.0,
            "rule_setting_eval": None,
            "generation_eval": None,
            "optimization_eval": None,
            "debugging_eval": None,
            "test_case_eval": None,
            "hint_query_eval": None,
            "follow_up_eval": None,
            "answer_summary": None,
            "turn_log": None,
            "turn_score": None,
        }

        # SubGraph 실행 (동기)
        logger.info(f"[Eval Turn Sync] Eval Turn SubGraph 실행 시작 - turn: {turn}")
        result = await eval_turn_subgraph.ainvoke(turn_state)
        logger.info(f"[Eval Turn Sync] Eval Turn SubGraph 실행 완료 - turn: {turn}")

        intent_type = result.get("intent_type", "UNKNOWN")
        intent_types = result.get(
            "intent_types",
            [intent_type] if intent_type and intent_type != "UNKNOWN" else [],
        )
        intent_confidence = result.get("intent_confidence", 0.0)
        unified_intent = result.get("unified_intent")  # v2.1 4대 통합 의도
        turn_score = result.get("turn_score", 0)
        turn_log_data = result.get("turn_log", {})
        evaluations = turn_log_data.get("evaluations", {})
        detailed_feedback = turn_log_data.get("detailed_feedback", [])
        comprehensive_reasoning = turn_log_data.get("comprehensive_reasoning", "")

        # intent_type이 "UNKNOWN"이면 intent_types[0] 사용
        if intent_type == "UNKNOWN" and intent_types:
            intent_type = intent_types[0]

        # final_intent 정의 (JSON 출력에서 사용하기 위해 먼저 정의)
        final_intent = (
            intent_type
            if intent_type != "UNKNOWN"
            else (intent_types[0] if intent_types else "UNKNOWN")
        )

        logger.info(f"[Eval Turn Sync] 턴 {turn} 평가 결과:")
        logger.info(f"[Eval Turn Sync]   - Intent Type: {intent_type}")
        logger.info(f"[Eval Turn Sync]   - Intent Types: {intent_types}")
        logger.info(f"[Eval Turn Sync]   - Intent Confidence: {intent_confidence}")
        logger.info(f"[Eval Turn Sync]   - Turn Score: {turn_score}")

        # LLM 응답 요약 로그
        answer_summary = result.get("answer_summary", "")
        if answer_summary:
            logger.info(
                f"[Eval Turn Sync]   - Answer Summary: {answer_summary[:200]}..."
            )

        # 상세 평가 내용 로그 (루브릭, 분석 등)
        logger.info(f"[Eval Turn Sync] ===== 턴 {turn} 상세 평가 내용 =====")

        # comprehensive_reasoning 로그
        if comprehensive_reasoning:
            logger.info(f"[Eval Turn Sync]   - 종합 분석:")
            logger.info(
                f"[Eval Turn Sync]     {comprehensive_reasoning[:500]}{'...' if len(comprehensive_reasoning) > 500 else ''}"
            )

            # 전체 분석 텍스트 JSON 출력 (발표자료용)
            import json

            analysis_json = {
                "turn": turn,
                "intent": final_intent,
                "analysis_text": comprehensive_reasoning,
            }
            logger.info("")
            logger.info(
                f"[Eval Turn Sync] ===== 턴 {turn} 평가 분석 텍스트 (JSON) ====="
            )
            logger.info(json.dumps(analysis_json, indent=4, ensure_ascii=False))
            logger.info("")

        # evaluations 로그 (각 평가 타입별 결과)
        if evaluations:
            logger.info(f"[Eval Turn Sync]   - 평가 타입별 결과:")
            for eval_key, eval_result in evaluations.items():
                if isinstance(eval_result, dict):
                    eval_score = eval_result.get("score", eval_result.get("average", 0))
                    eval_feedback = eval_result.get(
                        "final_reasoning", eval_result.get("feedback", "")
                    )
                    logger.info(
                        f"[Eval Turn Sync]     * {eval_key}: {eval_score:.2f}점"
                    )
                    if eval_feedback:
                        logger.info(
                            f"[Eval Turn Sync]       {eval_feedback[:200]}{'...' if len(eval_feedback) > 200 else ''}"
                        )

        # detailed_feedback 로그
        if detailed_feedback:
            logger.info(
                f"[Eval Turn Sync]   - 상세 피드백 ({len(detailed_feedback)}개):"
            )
            for idx, feedback in enumerate(detailed_feedback, 1):
                feedback_intent = feedback.get("intent", "UNKNOWN")
                feedback_score = feedback.get("score", 0)
                logger.info(
                    f"[Eval Turn Sync]     [{idx}] Intent: {feedback_intent}, Score: {feedback_score:.2f}점"
                )
                feedback_rubrics = feedback.get("rubrics", [])
                if feedback_rubrics:
                    for rubric in feedback_rubrics:
                        if isinstance(rubric, dict):
                            rubric_name = rubric.get(
                                "criterion", rubric.get("name", "")
                            )
                            rubric_score = rubric.get("score", 0)
                            rubric_reasoning = rubric.get(
                                "reasoning", rubric.get("reason", "")
                            )
                            logger.info(
                                f"[Eval Turn Sync]       - {rubric_name}: {rubric_score:.2f}점"
                            )
                            if rubric_reasoning:
                                logger.info(
                                    f"[Eval Turn Sync]         이유: {rubric_reasoning[:150]}{'...' if len(rubric_reasoning) > 150 else ''}"
                                )

        # weights 정보 가져오기 (intent_type을 대문자로 변환)
        from app.domain.langgraph.nodes.turn_evaluator.weights import \
            get_weights_for_intent

        # intent_type이 소문자 형식("hint_or_query")이면 대문자로 변환
        intent_for_weights = (
            intent_type.upper().replace("-", "_") if intent_type else "UNKNOWN"
        )
        weights = get_weights_for_intent(intent_for_weights)

        # 상세 루브릭 정보 추출
        # 1순위: detailed_feedback에서 primary intent의 rubrics 사용
        # 2순위: evaluations에서 primary intent의 rubrics 사용
        # 3순위: result에서 직접 추출
        detailed_rubrics = []

        # detailed_feedback에서 primary intent의 rubrics 추출
        if detailed_feedback:
            # intent_type에 해당하는 피드백 찾기
            primary_feedback = None
            for feedback in detailed_feedback:
                feedback_intent = feedback.get("intent", "")
                # intent_type과 매칭 (예: "HINT_OR_QUERY" -> "hint_query_eval")
                if intent_type and (
                    intent_type in feedback_intent.upper()
                    or feedback_intent.upper() in intent_type
                ):
                    primary_feedback = feedback
                    break

            # 매칭되는 것이 없으면 첫 번째 피드백 사용
            if not primary_feedback and detailed_feedback:
                primary_feedback = detailed_feedback[0]

            if primary_feedback:
                feedback_rubrics = primary_feedback.get("rubrics", [])
                for rubric in feedback_rubrics:
                    if isinstance(rubric, dict):
                        detailed_rubrics.append(
                            {
                                "name": rubric.get("criterion", rubric.get("name", "")),
                                "score": rubric.get("score", 0.0),
                                "reasoning": rubric.get(
                                    "reasoning", rubric.get("reason", "평가 없음")
                                ),
                                "criterion": rubric.get(
                                    "criterion", rubric.get("name", "")
                                ),  # 호환성 유지
                            }
                        )

        # detailed_rubrics가 없으면 evaluations에서 추출
        if not detailed_rubrics and evaluations:
            # intent_type을 eval_key로 변환 시도
            intent_to_eval_key = {
                "GENERATION": "generation_eval",
                "OPTIMIZATION": "optimization_eval",
                "DEBUGGING": "debugging_eval",
                "TEST_CASE": "test_case_eval",
                "HINT_OR_QUERY": "hint_query_eval",
                "FOLLOW_UP": "follow_up_eval",
                "RULE_SETTING": "rule_setting_eval",
            }

            eval_key = intent_to_eval_key.get(intent_type)
            primary_eval = evaluations.get(eval_key) if eval_key else None

            if not primary_eval and evaluations:
                # 첫 번째 평가 결과 사용
                primary_eval = list(evaluations.values())[0] if evaluations else None

            if primary_eval and isinstance(primary_eval, dict):
                eval_rubrics = primary_eval.get("rubrics", [])
                for rubric in eval_rubrics:
                    if isinstance(rubric, dict):
                        detailed_rubrics.append(
                            {
                                "name": rubric.get("criterion", rubric.get("name", "")),
                                "score": rubric.get("score", 0.0),
                                "reasoning": rubric.get(
                                    "reasoning", rubric.get("reason", "평가 없음")
                                ),
                                "criterion": rubric.get(
                                    "criterion", rubric.get("name", "")
                                ),  # 호환성 유지
                            }
                        )

        # detailed_rubrics가 여전히 없으면 result에서 직접 추출 (fallback)
        if not detailed_rubrics:
            eval_mapping = {
                "rule_setting_eval": "규칙 설정 (Rules)",
                "generation_eval": "코드 생성 (Generation)",
                "optimization_eval": "최적화 (Optimization)",
                "debugging_eval": "디버깅 (Debugging)",
                "test_case_eval": "테스트 케이스 (Test Case)",
                "hint_query_eval": "힌트/질의 (Hint/Query)",
                "follow_up_eval": "후속 응답 (Follow-up)",
            }

            for eval_key, criterion_name in eval_mapping.items():
                eval_result = result.get(eval_key)
                if eval_result and isinstance(eval_result, dict):
                    # eval_result의 rubrics 사용 (상세 정보)
                    eval_rubrics = eval_result.get("rubrics", [])
                    if eval_rubrics:
                        for rubric in eval_rubrics:
                            if isinstance(rubric, dict):
                                detailed_rubrics.append(
                                    {
                                        "name": rubric.get("criterion", criterion_name),
                                        "score": rubric.get(
                                            "score", eval_result.get("average", 0)
                                        ),
                                        "reasoning": rubric.get(
                                            "reasoning",
                                            rubric.get("reason", "평가 없음"),
                                        ),
                                        "criterion": rubric.get(
                                            "criterion", criterion_name
                                        ),  # 호환성 유지
                                    }
                                )
                    else:
                        # rubrics가 없으면 간단한 형식
                        detailed_rubrics.append(
                            {
                                "name": criterion_name,
                                "score": eval_result.get("average", 0),
                                "reasoning": eval_result.get(
                                    "final_reasoning",
                                    eval_result.get("feedback", "평가 없음"),
                                ),
                                "criterion": criterion_name,  # 호환성 유지
                            }
                        )

        # 상세 turn_log 구조 생성 (중복 제거)
        # final_intent는 이미 위에서 정의됨 (288번 줄)

        # detailed_rubrics 로그 (최종 루브릭 정보)
        if detailed_rubrics:
            logger.info(
                f"[Eval Turn Sync]   - 최종 루브릭 평가 ({len(detailed_rubrics)}개):"
            )
            for rubric in detailed_rubrics:
                rubric_name = rubric.get("name", rubric.get("criterion", ""))
                rubric_score = rubric.get("score", 0)
                rubric_reasoning = rubric.get("reasoning", "")
                logger.info(
                    f"[Eval Turn Sync]     * {rubric_name}: {rubric_score:.2f}점"
                )
                if rubric_reasoning:
                    logger.info(
                        f"[Eval Turn Sync]       {rubric_reasoning[:150]}{'...' if len(rubric_reasoning) > 150 else ''}"
                    )

        # JSON 형식으로 점수와 가중치 출력 (발표자료용)
        import json

        if detailed_rubrics and weights:
            # 의도 타입을 대문자로 변환 (예: "hint_or_query" -> "HINT_OR_QUERY")
            intent_display = (
                final_intent.upper().replace("-", "_") if final_intent else "UNKNOWN"
            )

            # 루브릭 이름 매핑 사용 (weights.py의 RUBRIC_NAME_MAP)
            from app.domain.langgraph.nodes.turn_evaluator.weights import \
                RUBRIC_NAME_MAP

            # 루브릭 점수를 딕셔너리로 변환 (가중치 키 순서대로)
            rubric_scores = {}
            for rubric in detailed_rubrics:
                rubric_name = rubric.get("name", rubric.get("criterion", ""))
                rubric_score = rubric.get("score", 0)

                # RUBRIC_NAME_MAP을 사용하여 루브릭 이름을 가중치 키로 변환
                weight_key = RUBRIC_NAME_MAP.get(rubric_name)

                # 매핑이 없으면 부분 매칭 시도
                if not weight_key:
                    rubric_lower = rubric_name.lower()
                    for map_key, map_value in RUBRIC_NAME_MAP.items():
                        if map_key.lower() in rubric_lower or any(
                            word in rubric_lower for word in map_key.split()
                        ):
                            weight_key = map_value
                            break

                # 여전히 없으면 직접 매칭 시도
                if not weight_key:
                    if "명확성" in rubric_name or "clarity" in rubric_name.lower():
                        weight_key = "clarity"
                    elif (
                        "문제 적절성" in rubric_name
                        or "problem" in rubric_name.lower()
                        or "relevance" in rubric_name.lower()
                    ):
                        weight_key = "problem_relevance"
                    elif "예시" in rubric_name or "example" in rubric_name.lower():
                        weight_key = "examples"
                    elif "규칙" in rubric_name or "rule" in rubric_name.lower():
                        weight_key = "rules"
                    elif "문맥" in rubric_name or "context" in rubric_name.lower():
                        weight_key = "context"

                if weight_key:
                    rubric_scores[weight_key] = round(rubric_score, 2)

            # 가중치에 있는 모든 키를 점수에도 포함 (점수가 없으면 0으로 설정)
            for weight_key in weights.keys():
                if weight_key not in rubric_scores:
                    rubric_scores[weight_key] = 0.0

            # 점수 JSON 출력 (가중치 키 순서대로 정렬)
            if rubric_scores:
                # 가중치 키 순서대로 정렬된 딕셔너리 생성
                ordered_scores = {
                    key: rubric_scores.get(key, 0.0) for key in weights.keys()
                }
                scores_json = {intent_display: ordered_scores}
                logger.info("")
                logger.info(f"[Eval Turn Sync] ===== 턴 {turn} 평가 점수 (JSON) =====")
                logger.info(json.dumps(scores_json, indent=4, ensure_ascii=False))
                logger.info("")

            # 가중치 JSON 출력
            weights_json = {intent_display: weights}
            logger.info(f"[Eval Turn Sync] ===== 턴 {turn} 가중치 (JSON) =====")
            logger.info("## Weight")
            logger.info(json.dumps(weights_json, indent=4, ensure_ascii=False))
            logger.info("")

        # weights 로그 (기존 형식 유지)
        if weights:
            logger.info(f"[Eval Turn Sync]   - 가중치:")
            for weight_key, weight_value in weights.items():
                logger.info(f"[Eval Turn Sync]     * {weight_key}: {weight_value}")

        logger.info(f"[Eval Turn Sync] ===== 턴 {turn} 상세 평가 내용 종료 =====")

        detailed_turn_log = {
            "turn_number": turn,
            "user_prompt_summary": (
                human_message[:200] + "..."
                if len(human_message) > 200
                else human_message
            ),
            "prompt_evaluation_details": {
                "intent": final_intent,  # UNKNOWN 대신 실제 intent 사용
                "intent_types": intent_types,
                "unified_intent": unified_intent,  # v2.1 4대 통합 의도
                "intent_confidence": intent_confidence,
                "score": turn_score,
                "rubrics": detailed_rubrics,  # 상세 루브릭 정보 (중복 제거)
                "weights": weights,  # 가중치 정보 (올바른 intent로 가져온 값)
                "final_reasoning": comprehensive_reasoning
                or result.get("answer_summary", "재평가 완료"),
            },
            "llm_answer_summary": result.get("answer_summary", ""),
            "llm_answer_reasoning": comprehensive_reasoning
            or (
                detailed_rubrics[0].get("reasoning", "")
                if detailed_rubrics
                else "평가 없음"
            ),
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Redis에 상세 turn_log 저장
        await redis_client.save_turn_log(session_id, turn, detailed_turn_log)

        # PostgreSQL에 평가 결과 저장
        try:
            from app.application.services.evaluation_storage_service import \
                EvaluationStorageService
            from app.infrastructure.persistence.session import get_db_context

            # session_id를 PostgreSQL id로 변환 (Redis session_id: "session_123" -> PostgreSQL id: 123)
            postgres_session_id = (
                int(session_id.replace("session_", ""))
                if session_id.startswith("session_")
                else None
            )

            if postgres_session_id:
                async with get_db_context() as db:
                    storage_service = EvaluationStorageService(db)

                    # turn_log를 aggregate_turn_log 형식으로 변환 (상세 정보 포함)
                    turn_log_for_storage = {
                        "prompt_evaluation_details": detailed_turn_log.get(
                            "prompt_evaluation_details", {}
                        ),
                        "comprehensive_reasoning": comprehensive_reasoning
                        or detailed_turn_log.get("llm_answer_reasoning", ""),
                        "intent_types": intent_types,
                        "unified_intent": unified_intent,  # v2.1 4대 통합 의도
                        "intent_confidence": intent_confidence,
                        "evaluations": evaluations,  # 전체 평가 결과 (상세 정보 포함)
                        "detailed_feedback": detailed_feedback,  # 상세 피드백
                        "turn_score": turn_score,
                        "is_guardrail_failed": turn_log_data.get(
                            "is_guardrail_failed", False
                        ),
                        "guardrail_message": turn_log_data.get("guardrail_message"),
                    }

                    pg_evaluation = await storage_service.save_turn_evaluation(
                        session_id=postgres_session_id,
                        turn=turn,
                        turn_log=turn_log_for_storage,
                    )

                    if pg_evaluation:
                        await db.commit()
                        logger.info(
                            f"[Eval Turn Sync] PostgreSQL 턴 평가 저장 완료 - "
                            f"session_id: {postgres_session_id}, turn: {turn}"
                        )
                    else:
                        # 저장 실패 (None 반환)
                        await db.rollback()
                        logger.warning(
                            f"[Eval Turn Sync] PostgreSQL 턴 평가 저장 실패 (None 반환) - "
                            f"session_id: {postgres_session_id}, turn: {turn}"
                        )
        except Exception as pg_error:
            # PostgreSQL 저장 실패해도 Redis는 저장되었으므로 경고만
            logger.warning(
                f"[Eval Turn Sync] PostgreSQL 턴 평가 저장 실패 (Redis는 저장됨) - "
                f"session_id: {session_id}, turn: {turn}, error: {str(pg_error)}"
            )

        logger.info(
            f"[Eval Turn Sync] 턴 {turn} 평가 저장 완료 - session_id: {session_id}, score: {turn_score}"
        )

        # 평가 결과 반환 (요약 정보 포함)
        # result는 Eval Turn SubGraph의 결과 (dict), answer_summary는 이미 추출됨
        return {
            "intent_type": final_intent,
            "intent_types": intent_types,
            "intent_confidence": intent_confidence,
            "turn_score": turn_score,
            "rubrics": detailed_rubrics,
            "comprehensive_reasoning": comprehensive_reasoning or answer_summary,
            "answer_summary": answer_summary,
        }

    except Exception as e:
        logger.error(
            f"[Eval Turn Sync] 턴 {turn} 평가 실패 - session_id: {session_id}, error: {str(e)}",
            exc_info=True,
        )
        return None
