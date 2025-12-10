import logging
from typing import Dict, Any, List, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda

from app.domain.langgraph.states import EvalTurnState, TurnEvaluation
from app.domain.langgraph.nodes.turn_evaluator.utils import get_llm
from app.domain.langgraph.utils.token_tracking import extract_token_usage, accumulate_tokens
from app.domain.langgraph.utils.structured_output_parser import parse_structured_output_async
from app.domain.langgraph.utils.prompt_metrics import calculate_all_metrics

logger = logging.getLogger(__name__)


def prepare_evaluation_input_internal(inputs: Dict[str, Any], eval_type: str, criteria: str) -> Dict[str, Any]:
    """평가 입력 준비 (문제 정보 포함) - 외부에서 재사용 가능"""
    state = inputs.get("state")
    human_message = state.get("human_message", "")
    ai_message = state.get("ai_message", "")
    problem_context = state.get("problem_context")
    
    # 문제 정보 추출
    problem_info_section = ""
    problem_algorithms = None
    if problem_context:
        basic_info = problem_context.get("basic_info", {})
        ai_guide = problem_context.get("ai_guide", {})
        
        problem_title = basic_info.get("title", "알 수 없음")
        key_algorithms = ai_guide.get("key_algorithms", [])
        problem_algorithms = key_algorithms
        algorithms_text = ", ".join(key_algorithms) if key_algorithms else "없음"
        
        problem_info_section = f"""
[문제 정보]
- 문제: {problem_title}
- 필수 알고리즘: {algorithms_text}

"""
    
    # 알고리즘 텍스트 미리 계산 (f-string 내부에서 조건식 사용 시 오류 방지)
    algorithms_display = algorithms_text if problem_context else "알 수 없음"
    
    # 정량적 메트릭 계산
    metrics = calculate_all_metrics(human_message, problem_algorithms)
    
    # 메트릭 정보 포맷팅
    metrics_section = f"""
[정량적 메트릭 (참고용)]
- 텍스트 길이: {metrics['text_length']}자, 단어 수: {metrics['word_count']}개, 문장 수: {metrics['sentence_count']}개
- 명확성 메트릭: 구체적 값 포함 {metrics['clarity']['has_specific_values']}, 값 개수 {metrics['clarity']['specific_value_count']}개
- 예시 메트릭: 예시 포함 {metrics['examples']['has_examples']}, 예시 개수 {metrics['examples']['example_count']}개
- 규칙 메트릭: XML 태그 {metrics['rules']['has_xml_tags']} ({metrics['rules']['xml_tag_count']}개), 제약조건 {metrics['rules']['has_constraints']} ({metrics['rules']['constraint_count']}개), 구조화 형식 {metrics['rules']['has_structured_format']}
- 문맥 메트릭: 이전 대화 참조 {metrics['context']['has_context_reference']} ({metrics['context']['context_reference_count']}회)
- 문제 적절성 메트릭: 기술 용어 {metrics['problem_relevance']['technical_term_count']}개
- 코드 블록: {metrics['has_code_blocks']} ({metrics['code_block_count']}개)

**참고**: 위 메트릭은 객관적 측정값입니다. LLM 평가 시 이 메트릭을 참고하되, 맥락과 의미를 종합적으로 고려하여 평가하세요.
"""
    
    system_prompt = f"""당신은 '프롬프트 엔지니어링' 전문가입니다.
사용자가 작성한 프롬프트가 '{eval_type}' 의도를 얼마나 잘 전달하고 있는지 평가하세요.
AI의 응답은 참고용으로만 사용하고, 평가는 오직 '사용자의 프롬프트'에 집중하세요.

{problem_info_section}{metrics_section}
평가 기준 (Claude Prompt Engineering):

1. **명확성 (Clarity)**: 요청이 모호하지 않고 구체적인가?
   - [가이드]: 단어 수가 적더라도(Short), 의도와 대상이 명확하다면(Specific) 만점을 부여하세요. 반대로 길기만 하고 핵심이 없으면 감점하세요.
   - (메트릭 '단어 수'는 참고용일 뿐, 절대적인 채점 기준이 아닙니다.)
   - 메트릭 참고: 단어 수 {metrics['word_count']}개, 문장 수 {metrics['sentence_count']}개, 구체적 값 {metrics['clarity']['specific_value_count']}개

2. **문제 적절성 (Problem Relevance)**: 
   - 요청이 문제 특성({algorithms_display})에 적합한가?
   - [가이드]: '기술 용어'의 개수보다는, 해당 용어가 문맥에 맞게 적절히 사용되었는지를 판단하세요. 핵심 키워드(예: DP) 하나만 있어도 적절하다면 충분합니다.
   - 메트릭 참고: 기술 용어 {metrics['problem_relevance']['technical_term_count']}개

3. **예시 (Examples)**: 원하는 입출력 예시나 상황을 제공했는가? (멀티샷)
   - [가이드]: 예시의 개수(N개)보다 '질'이 중요합니다. 단 하나의 예시라도 문제 상황을 잘 설명한다면 높은 점수를 주세요.
   - 메트릭 참고: 예시 포함 {metrics['examples']['has_examples']}, 예시 개수 {metrics['examples']['example_count']}개

4. **규칙 (Rules)**: {criteria} (XML 태그 사용, 제약조건 명시 등)
   - [가이드]: XML 태그나 제약조건이 '필요한 곳에' 적절히 쓰였는지 보세요. 불필요한 태그 남발은 오히려 감점 요인입니다.
   - 메트릭 참고: XML 태그 {metrics['rules']['xml_tag_count']}개, 제약조건 {metrics['rules']['constraint_count']}개, 구조화 형식 {metrics['rules']['has_structured_format']}

5. **문맥 (Context)**: 이전 대화나 배경 지식을 적절히 활용했는가?
   - [가이드]: 이전 대화 참조 횟수보다는, 참조가 맥락적으로 의미 있는지 판단하세요.
   - 메트릭 참고: 이전 대화 참조 {metrics['context']['has_context_reference']}, 참조 횟수 {metrics['context']['context_reference_count']}회

**[채점 원칙]**
- 메트릭(숫자)에 얽매이지 말고, **"사람이 보기에 유용한 프롬프트인가?"**를 최우선으로 판단하세요.
- 간결함(Conciseness)은 미덕입니다. 짧다고 해서 점수를 깎지 마십시오.
- 위 기준과 메트릭을 바탕으로 0-100점 사이의 점수를 부여하고, 상세한 루브릭과 추론을 제공하세요.
- 메트릭은 객관적 측정값이지만, 맥락과 의미를 종합적으로 고려하여 평가하세요."""

    user_prompt = f"""[사용자 프롬프트]
{human_message}

[AI 응답 (참고용)]
{ai_message}

위 사용자 프롬프트를 '{eval_type}' 관점에서 평가하세요."""
    
    return {
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }


def format_evaluation_messages(inputs: Dict[str, Any]) -> list:
    """메시지를 LangChain BaseMessage 객체로 변환 - 외부에서 재사용 가능"""
    from langchain_core.messages import HumanMessage, SystemMessage
    
    messages = []
    if inputs.get("system_prompt"):
        messages.append(SystemMessage(content=inputs["system_prompt"]))
    if inputs.get("user_prompt"):
        messages.append(HumanMessage(content=inputs["user_prompt"]))
    return messages


def create_evaluation_chain(eval_type: str, criteria: str):
    """
    평가 Chain 생성 (Runnable & Chain 구조)
    
    [토큰 추적 개선]
    - with_structured_output은 원본 응답 메타데이터를 보존하지 않음
    - Chain 내부에서 원본 LLM을 먼저 호출하여 메타데이터 추출 후, 구조화된 출력으로 파싱
    
    Args:
        eval_type: 평가 유형 (예: "코드 생성 요청")
        criteria: 평가 기준 설명
    
    Returns:
        평가 Chain
    """
    from app.domain.langgraph.nodes.turn_evaluator.utils import get_llm
    llm = get_llm()
    structured_llm = llm.with_structured_output(TurnEvaluation)
    
    def prepare_evaluation_input(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """평가 입력 준비 (문제 정보 포함) - Chain 내부용"""
        return prepare_evaluation_input_internal(inputs, eval_type, criteria)
    
    def format_messages(inputs: Dict[str, Any]) -> list:
        """메시지를 LangChain BaseMessage 객체로 변환 - Chain 내부용"""
        return format_evaluation_messages(inputs)
    
    async def call_llm_and_parse(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        원본 LLM 호출 및 구조화된 출력 파싱 (비동기)
        - 원본 LLM 응답에서 토큰 사용량 추출
        - 구조화된 출력으로 파싱
        """
        messages = inputs.get("messages", [])
        
        # 원본 LLM 호출 (토큰 사용량 추출용)
        # 주의: with_structured_output은 원본 응답 메타데이터를 보존하지 않으므로
        # 원본 LLM을 먼저 호출하여 메타데이터 추출
        # 하지만 이렇게 하면 LLM을 두 번 호출하게 되므로 비효율적
        # 실제로는 구조화된 출력이 내부적으로 LLM을 다시 호출하므로
        # LLM을 두 번 호출하게 됨 (비효율적이지만 토큰 추적을 위해 필요)
        
        # 원본 LLM 호출 (토큰 추출용)
        raw_response = await llm.ainvoke(messages)
        
        # 구조화된 출력 호출
        structured_result = await structured_llm.ainvoke(messages)
        
        return {
            "structured_result": structured_result,
            "raw_response": raw_response,  # 토큰 추출용
        }
    
    def process_output_with_response(inputs: Dict[str, Any]) -> Dict[str, Any]:
        """출력 처리 (LLM 응답 객체 포함)"""
        # Chain에서 전달되는 형태: {"llm_response": TurnEvaluation}
        # 또는 직접 TurnEvaluation 객체가 전달될 수 있음
        if isinstance(inputs, dict):
            structured_result = inputs.get("llm_response") or inputs.get("structured_result")
        else:
            # 직접 TurnEvaluation 객체가 전달된 경우
            structured_result = inputs
        
        if structured_result is None:
            logger.error(f"[Chain] process_output_with_response - structured_result가 None입니다. inputs 타입: {type(inputs)}, inputs: {inputs}")
            raise ValueError("평가 결과를 파싱할 수 없습니다.")
        
        result = structured_result  # structured_llm의 결과는 이미 TurnEvaluation 객체
        
        processed = {
            "intent": result.intent,
            "score": result.score,
            "average": result.score,  # 호환성 유지
            "rubrics": [r.dict() for r in result.rubrics],
            "final_reasoning": result.final_reasoning,
        }
        return processed
    
    # Chain 구성 (토큰 추출을 위해 원본 LLM 응답도 전달)
    # 주의: 비동기 함수를 Chain에 직접 사용할 수 없으므로
    # Chain 외부에서 비동기 처리를 수행해야 함
    chain = (
        RunnableLambda(prepare_evaluation_input)
        | RunnableLambda(format_messages)
        | structured_llm  # 일단 구조화된 출력만 사용 (토큰 추적은 Chain 외부에서)
        | RunnableLambda(lambda x: {"llm_response": x})
        | RunnableLambda(process_output_with_response)
    )
    
    return chain


async def _evaluate_turn(state: EvalTurnState, eval_type: str, criteria: str) -> Dict[str, Any]:
    """
    공통 턴 평가 로직 (사용자 프롬프트 평가) - Chain 구조 사용
    
    Claude Prompt Engineering 기준:
    1. 명확성 (Clarity)
    2. 예시 사용 (Examples)
    3. 규칙 및 제약조건 (Rules)
    4. 사고 연쇄 유도 (Chain of Thought)
    
    [토큰 추적 개선]
    - with_structured_output은 원본 응답 메타데이터를 보존하지 않음
    - Chain 실행 전에 원본 LLM을 호출하여 메타데이터 추출
    """
    try:
        # LLM 인스턴스 가져오기
        llm = get_llm()
        
        # 입력 준비 및 메시지 포맷팅
        chain_input = {"state": state}
        prepared_input = prepare_evaluation_input_internal(chain_input, eval_type, criteria)
        formatted_messages = format_evaluation_messages(prepared_input)
        
        # 원본 LLM 호출 (1회만 - 토큰 추출 + JSON 파싱)
        raw_response = await llm.ainvoke(formatted_messages)
        
        # 토큰 사용량 추출 및 State에 누적
        tokens = extract_token_usage(raw_response)
        if tokens:
            accumulate_tokens(state, tokens, token_type="eval")
            logger.debug(f"[{eval_type} 평가] 토큰 사용량 - prompt: {tokens.get('prompt_tokens')}, completion: {tokens.get('completion_tokens')}, total: {tokens.get('total_tokens')}")
        else:
            logger.warning(f"[{eval_type} 평가] 토큰 사용량 추출 실패 - raw_response 타입: {type(raw_response)}")
        
        # 원본 응답을 구조화된 출력으로 파싱
        try:
            structured_llm = llm.with_structured_output(TurnEvaluation)
            structured_result = await parse_structured_output_async(
                raw_response=raw_response,
                model_class=TurnEvaluation,
                fallback_llm=structured_llm,
                formatted_messages=formatted_messages
            )
        except Exception as parse_error:
            logger.error(f"[{eval_type} 평가] 구조화된 출력 파싱 실패: {str(parse_error)}", exc_info=True)
            # 파싱 실패 시 fallback으로 구조화된 출력 Chain 사용
            logger.info(f"[{eval_type} 평가] Fallback: 구조화된 출력 Chain 사용")
            structured_llm = llm.with_structured_output(TurnEvaluation)
            structured_result = await structured_llm.ainvoke(formatted_messages)
        
        # 출력 처리 (State 형식으로 변환)
        chain_result = {
            "intent": structured_result.intent,
            "score": structured_result.score,
            "average": structured_result.score,  # 호환성 유지
            "rubrics": [r.dict() for r in structured_result.rubrics],
            "final_reasoning": structured_result.final_reasoning,
        }
        
        # State에 누적된 토큰 정보를 result에 포함 (LangGraph 병합을 위해)
        if "eval_tokens" in state:
            chain_result["eval_tokens"] = state["eval_tokens"]
        
        return chain_result
        
    except Exception as e:
        logger.error(f"평가 중 오류 발생: {str(e)}")
        return {
            "intent": eval_type,
            "score": 0,
            "average": 0,
            "rubrics": [],
            "final_reasoning": f"평가 실패: {str(e)}"
        }


async def eval_system_prompt(state: EvalTurnState) -> Dict[str, Any]:
    """4.SP: System Prompt 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.SP 시스템 프롬프트 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "시스템 프롬프트 설정 (System Prompting)",
        "AI에게 구체적인 역할(Persona)을 부여하고, 임무의 범위(Scope)와 답변 스타일(Tone & Style)을 명확히 정의했는가?"
    )
    
    return {"system_prompt_eval": result}


async def eval_rule_setting(state: EvalTurnState) -> Dict[str, Any]:
    """4.R: Rule Setting 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.R Rule Setting 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state, 
        "규칙 설정 (Rule Setting)",
        "제약 조건(시간/공간 복잡도, 언어 등)을 명확히 XML 태그나 리스트로 명시했는가?"
    )
    
    return {"rule_setting_eval": result}


async def eval_generation(state: EvalTurnState) -> Dict[str, Any]:
    """4.G: Generation 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.G 코드 생성 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "코드 생성 요청 (Generation)",
        "원하는 기능의 입출력 예시(Input/Output Examples)를 제공하고, 구현 조건을 상세히 기술했는가?"
    )
    
    return {"generation_eval": result}


async def eval_optimization(state: EvalTurnState) -> Dict[str, Any]:
    """4.O: Optimization 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.O 최적화 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "최적화 요청 (Optimization)",
        "현재 코드의 문제점(병목)을 지적하고, 목표 성능(O(n) 등)이나 구체적인 최적화 전략을 제시했는가?"
    )
    
    return {"optimization_eval": result}


async def eval_debugging(state: EvalTurnState) -> Dict[str, Any]:
    """4.D: Debugging 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.D 디버깅 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "디버깅 요청 (Debugging)",
        "발생한 에러 메시지, 재현 단계, 또는 예상치 못한 동작을 구체적으로 설명했는가?"
    )
    
    return {"debugging_eval": result}


async def eval_test_case(state: EvalTurnState) -> Dict[str, Any]:
    """4.T: Test Case 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.T 테스트 케이스 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "테스트 케이스 요청 (Test Case)",
        "테스트하고 싶은 엣지 케이스(Edge Cases)나 경계 조건(Boundary Conditions)을 명시했는가?"
    )
    
    return {"test_case_eval": result}


async def eval_hint_query(state: EvalTurnState) -> Dict[str, Any]:
    """4.H: Hint/Query 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.H 힌트/질의 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "힌트/질의 요청 (Hint/Query)",
        "단순히 정답을 묻는 것이 아니라, 자신의 사고 과정(Chain of Thought)을 공유하고 막힌 부분을 구체적으로 질문했는가?"
    )
    
    return {"hint_query_eval": result}


async def eval_follow_up(state: EvalTurnState) -> Dict[str, Any]:
    """4.F: Follow Up 평가 (사용자 프롬프트)"""
    session_id = state.get("session_id", "unknown")
    turn = state.get("turn", 0)
    logger.info(f"[4.F 후속 질문 평가] 진입 - session_id: {session_id}, turn: {turn}")
    
    result = await _evaluate_turn(
        state,
        "후속 질문 (Follow Up)",
        "이전 턴의 AI 답변을 기반으로, 추가적인 개선점이나 의문점을 논리적으로 연결하여 질문했는가?"
    )
    
    return {"follow_up_eval": result}
