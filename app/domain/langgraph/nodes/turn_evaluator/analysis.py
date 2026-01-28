import logging
import re
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from app.domain.langgraph.nodes.turn_evaluator.utils import get_llm
from app.domain.langgraph.states import EvalTurnState, IntentClassification
from app.domain.langgraph.utils.structured_output_parser import \
    parse_structured_output_async
from app.domain.langgraph.utils.token_tracking import (accumulate_tokens,
                                                       extract_token_usage)
from app.infrastructure.persistence.models.enums import CodeIntentType

logger = logging.getLogger(__name__)


def has_xml_tags(text: str) -> bool:
    """XML 태그 사용 여부 확인"""
    xml_pattern = r"<[^>]+>"
    return bool(re.search(xml_pattern, text))


def has_role_content_tags(text: str) -> bool:
    """<Role> 또는 <Content> 태그가 있는지 확인"""
    return bool(re.search(r"<Role>|<Content>", text, re.IGNORECASE))


async def intent_analysis(state: EvalTurnState) -> Dict[str, Any]:
    """
    4.0: Intent Analysis
    8가지 코드 패턴 분류

    [토큰 추적 개선]
    - with_structured_output은 원본 응답 메타데이터를 보존하지 않음
    - 원본 LLM을 먼저 호출하여 메타데이터 추출 후, 수동으로 파싱
    """
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.0 Intent Analysis] 진입 - session_id: {session_id}, turn: {turn}")

    human_message = state.get("human_message", "")
    ai_message = state.get("ai_message", "")

    llm = get_llm()
    structured_llm = llm.with_structured_output(IntentClassification)

    # 턴 번호와 XML 태그 정보 추출
    is_first_turn = turn == 1
    has_xml = has_xml_tags(human_message)
    has_role_content = has_role_content_tags(human_message)

    # 첫 턴 및 XML 태그 기반 우선순위 조정 - YAML에서 로드
    from app.domain.langgraph.prompts import load_prompt, render_prompt

    yaml_data = load_prompt("eval_intent_analysis")

    if is_first_turn:
        priority_note = yaml_data.get("first_turn_priority_note", "")
    else:
        priority_note = ""

    if has_role_content:
        xml_hint = yaml_data.get("xml_tag_hint", "")
    else:
        xml_hint = ""

    system_prompt = render_prompt(
        "eval_intent_analysis",
        priority_note=priority_note,
        xml_hint=xml_hint,
    )

    prompt = f"사용자: {human_message}\n\nAI 응답: {ai_message}"

    try:
        # 원본 LLM 호출 (메타데이터 보존을 위해)
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=prompt)]

        # 원본 LLM 호출 (1회만 - 토큰 추출 + JSON 파싱)
        raw_response = await llm.ainvoke(messages)

        # 토큰 사용량 추출 및 State에 누적
        tokens = extract_token_usage(raw_response)
        if tokens:
            accumulate_tokens(state, tokens, token_type="eval")
            logger.debug(
                f"[4.0 Intent Analysis] 토큰 사용량 - prompt: {tokens.get('prompt_tokens')}, completion: {tokens.get('completion_tokens')}, total: {tokens.get('total_tokens')}"
            )
        else:
            logger.warning(
                f"[4.0 Intent Analysis] 토큰 사용량 추출 실패 - raw_response 타입: {type(raw_response)}"
            )

        # 원본 응답을 구조화된 출력으로 파싱
        try:
            parsed_response = await parse_structured_output_async(
                raw_response=raw_response,
                model_class=IntentClassification,
                fallback_llm=structured_llm,
                formatted_messages=messages,
            )
        except Exception as parse_error:
            logger.error(
                f"[4.0 Intent Analysis] 구조화된 출력 파싱 실패: {str(parse_error)}",
                exc_info=True,
            )
            # 파싱 실패 시 fallback으로 구조화된 출력 Chain 사용
            logger.info("[4.0 Intent Analysis] Fallback: 구조화된 출력 Chain 사용")
            parsed_response = await structured_llm.ainvoke(messages)

        # 리스트 형태의 값 추출
        intent_values = [intent.value for intent in parsed_response.intent_types]

        # 첫 턴 검증: 첫 턴이 FOLLOW_UP이면 재분류
        if is_first_turn and CodeIntentType.FOLLOW_UP.value in intent_values:
            logger.warning(
                f"[4.0 Intent Analysis] 첫 턴에서 FOLLOW_UP 감지 - 재분류 필요. 원본 의도: {intent_values}"
            )
            # FOLLOW_UP 제거하고 다른 의도 선택
            intent_values = [
                intent
                for intent in intent_values
                if intent != CodeIntentType.FOLLOW_UP.value
            ]
            if not intent_values:
                # 대체 의도 선택 (XML 태그 기반)
                if has_role_content:
                    intent_values = [CodeIntentType.SYSTEM_PROMPT.value]
                    logger.info(
                        f"[4.0 Intent Analysis] 첫 턴 FOLLOW_UP → XML 태그 기반으로 SYSTEM_PROMPT로 재분류"
                    )
                else:
                    intent_values = [CodeIntentType.RULE_SETTING.value]
                    logger.info(
                        f"[4.0 Intent Analysis] 첫 턴 FOLLOW_UP → RULE_SETTING으로 재분류"
                    )

        # 우선순위 기반 단일 선택 (복수 선택 시)
        if len(intent_values) > 1:
            # 의도 우선순위 정의 (첫 턴에서는 RULE_SETTING/SYSTEM_PROMPT 우선순위 상향)
            if is_first_turn:
                # 첫 턴 우선순위: RULE_SETTING/SYSTEM_PROMPT 우선
                intent_priority = {
                    CodeIntentType.SYSTEM_PROMPT.value: 1,  # 첫 턴 최우선
                    CodeIntentType.RULE_SETTING.value: 2,  # 첫 턴 최우선
                    CodeIntentType.GENERATION.value: 3,
                    CodeIntentType.OPTIMIZATION.value: 4,
                    CodeIntentType.DEBUGGING.value: 5,
                    CodeIntentType.TEST_CASE.value: 6,
                    CodeIntentType.HINT_OR_QUERY.value: 7,
                    CodeIntentType.FOLLOW_UP.value: 999,  # 첫 턴에서는 선택 불가
                }
            else:
                # 일반 우선순위
                intent_priority = {
                    CodeIntentType.GENERATION.value: 1,  # 최우선
                    CodeIntentType.OPTIMIZATION.value: 2,
                    CodeIntentType.DEBUGGING.value: 3,
                    CodeIntentType.TEST_CASE.value: 4,
                    CodeIntentType.RULE_SETTING.value: 5,
                    CodeIntentType.SYSTEM_PROMPT.value: 6,
                    CodeIntentType.HINT_OR_QUERY.value: 7,
                    CodeIntentType.FOLLOW_UP.value: 8,  # 최하위
                }

            # XML 태그가 있으면 SYSTEM_PROMPT/RULE_SETTING 우선순위 추가 상향
            if has_role_content:
                if CodeIntentType.SYSTEM_PROMPT.value in intent_values:
                    intent_priority[CodeIntentType.SYSTEM_PROMPT.value] = 0  # 최최우선
                if CodeIntentType.RULE_SETTING.value in intent_values:
                    intent_priority[CodeIntentType.RULE_SETTING.value] = 0  # 최최우선

            # 우선순위가 가장 높은 의도 선택
            selected_intent = min(
                intent_values, key=lambda x: intent_priority.get(x, 999)
            )
            intent_values = [selected_intent]

            logger.info(
                f"[4.0 Intent Analysis] 복수 의도 감지 - 원본: {parsed_response.intent_types}, 우선순위 기반 단일 선택: {selected_intent}"
            )

        # 단일 의도 선택 후 추가 검증
        if len(intent_values) == 1:
            selected_intent = intent_values[0]

            # 첫 턴 + FOLLOW_UP 최종 검증
            if is_first_turn and selected_intent == CodeIntentType.FOLLOW_UP.value:
                logger.warning(
                    f"[4.0 Intent Analysis] 첫 턴에서 FOLLOW_UP 최종 검증 실패 - RULE_SETTING으로 강제 변경"
                )
                intent_values = [CodeIntentType.RULE_SETTING.value]

            # XML 태그 기반 힌트 적용
            if has_role_content and selected_intent not in [
                CodeIntentType.SYSTEM_PROMPT.value,
                CodeIntentType.RULE_SETTING.value,
            ]:
                logger.info(
                    f"[4.0 Intent Analysis] XML 태그 감지되었으나 {selected_intent} 선택됨 - 유지 (LLM 판단 존중)"
                )

        logger.info(
            f"[4.0 Intent Analysis] 완료 - session_id: {session_id}, turn: {turn}, 의도: {intent_values}, 신뢰도: {parsed_response.confidence:.2f}"
        )

        result = {
            "intent_types": intent_values,
            "intent_confidence": parsed_response.confidence,
        }

        # State에 누적된 토큰 정보를 result에 포함 (LangGraph 병합을 위해)
        if "eval_tokens" in state:
            result["eval_tokens"] = state["eval_tokens"]

        return result

    except Exception as e:
        logger.error(
            f"[4.0 Intent Analysis] 오류 - session_id: {session_id}, turn: {turn}, error: {str(e)}",
            exc_info=True,
        )
        return {
            "intent_types": [CodeIntentType.HINT_OR_QUERY.value],
            "intent_confidence": 0.0,
        }
