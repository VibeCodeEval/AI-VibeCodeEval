"""
노드: Spec Extractor
사용자 프롬프트에서 명시된/누락된/모호한 요구사항을 추출하는 노드

[Phase 6-a Task 6a-1]
- 입력: 사용자 프롬프트 + 문제 정보
- 출력: 구조화된 Spec 결과 (specified, missing, ambiguous requirements)

[역할]
- LLM을 사용하여 사용자 프롬프트 분석
- 문제 정보와 비교하여 누락된 요구사항 식별
- AST Analyzer와 Error Injector의 입력 생성
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.domain.langgraph.states import MainGraphState
from app.domain.langgraph.utils.llm_factory import get_llm
from app.domain.langgraph.utils.token_tracking import (
    accumulate_tokens,
    estimate_user_text_tokens,
    extract_token_usage,
)

logger = logging.getLogger(__name__)


# ===== Pydantic 모델 (LLM 구조화 출력용) =====


class MissingSpec(BaseModel):
    """누락된 요구사항 상세"""
    
    category: str = Field(
        ...,
        description="누락된 요구사항 카테고리 (예: 알고리즘, 자료구조, 기저조건, 메모이제이션, 비트마스킹, 점화식, 시간복잡도)"
    )
    description: str = Field(
        ...,
        description="누락된 요구사항에 대한 설명"
    )
    importance: str = Field(
        ...,
        description="중요도 (HIGH, MEDIUM, LOW)"
    )
    related_component: Optional[str] = Field(
        None,
        description="관련 코드 구성 요소 (BASE_CASE, MEMOIZATION, BIT_OPERATION, STATE_TRANSITION, LOOP_STRUCTURE 등)"
    )


class SpecResult(BaseModel):
    """Spec 추출 결과"""
    
    specified_requirements: List[str] = Field(
        default_factory=list,
        description="사용자가 명시한 요구사항 목록"
    )
    missing_requirements: List[MissingSpec] = Field(
        default_factory=list,
        description="누락된 요구사항 목록"
    )
    ambiguous_requirements: List[str] = Field(
        default_factory=list,
        description="모호한 요구사항 목록"
    )
    prompt_quality_score: float = Field(
        default=50.0,
        ge=0.0,
        le=100.0,
        description="프롬프트 품질 점수 (0-100)"
    )
    analysis_reasoning: str = Field(
        default="",
        description="분석 근거"
    )


# ===== 알고리즘별 필수 Spec 매핑 =====

ALGORITHM_REQUIRED_SPECS = {
    "Dynamic Programming": [
        {"category": "상태정의", "importance": "HIGH", "component": "STATE_TRANSITION"},
        {"category": "점화식", "importance": "HIGH", "component": "STATE_TRANSITION"},
        {"category": "기저조건", "importance": "HIGH", "component": "BASE_CASE"},
        {"category": "메모이제이션", "importance": "MEDIUM", "component": "MEMOIZATION"},
        {"category": "시간복잡도", "importance": "MEDIUM", "component": "LOOP_STRUCTURE"},
    ],
    "Bitmasking": [
        {"category": "비트연산", "importance": "HIGH", "component": "BIT_OPERATION"},
        {"category": "비트마스크상태", "importance": "HIGH", "component": "BIT_OPERATION"},
    ],
    "DFS": [
        {"category": "재귀호출", "importance": "HIGH", "component": "RECURSIVE_CALL"},
        {"category": "기저조건", "importance": "HIGH", "component": "BASE_CASE"},
        {"category": "방문체크", "importance": "MEDIUM", "component": "FUNCTION_DEF"},
    ],
    "BFS": [
        {"category": "큐자료구조", "importance": "HIGH", "component": "FUNCTION_DEF"},
        {"category": "방문체크", "importance": "HIGH", "component": "FUNCTION_DEF"},
        {"category": "탐색순서", "importance": "MEDIUM", "component": "LOOP_STRUCTURE"},
    ],
    "TSP": [
        {"category": "외판원순회전략", "importance": "HIGH", "component": "FUNCTION_DEF"},
        {"category": "비트마스킹DP", "importance": "HIGH", "component": "BIT_OPERATION"},
        {"category": "출발점복귀", "importance": "MEDIUM", "component": "BASE_CASE"},
    ],
}


def get_required_specs_for_problem(problem_context: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    문제 정보에서 필수 Spec 목록 추출
    
    Args:
        problem_context: 문제 정보 딕셔너리
        
    Returns:
        필수 Spec 목록
    """
    required_specs = []
    
    ai_guide = problem_context.get("ai_guide", {})
    key_algorithms = ai_guide.get("key_algorithms", [])
    
    for algorithm in key_algorithms:
        if algorithm in ALGORITHM_REQUIRED_SPECS:
            required_specs.extend(ALGORITHM_REQUIRED_SPECS[algorithm])
    
    # 중복 제거 (category 기준)
    seen_categories = set()
    unique_specs = []
    for spec in required_specs:
        if spec["category"] not in seen_categories:
            seen_categories.add(spec["category"])
            unique_specs.append(spec)
    
    return unique_specs


def create_spec_extractor_prompt(
    user_prompt: str,
    problem_context: Dict[str, Any],
    required_specs: List[Dict[str, str]]
) -> str:
    """
    Spec Extractor용 시스템 프롬프트 생성
    
    Args:
        user_prompt: 사용자 프롬프트
        problem_context: 문제 정보
        required_specs: 필수 Spec 목록
        
    Returns:
        시스템 프롬프트 문자열
    """
    from app.domain.langgraph.prompts import render_prompt
    
    # 문제 정보 추출
    basic_info = problem_context.get("basic_info", {})
    ai_guide = problem_context.get("ai_guide", {})
    constraints = problem_context.get("constraints", {})
    
    problem_title = basic_info.get("title", "알 수 없음")
    key_algorithms = ai_guide.get("key_algorithms", [])
    algorithms_text = ", ".join(key_algorithms) if key_algorithms else "없음"
    
    # 필수 Spec 목록 텍스트 생성
    required_specs_text = "\n".join([
        f"- {spec['category']} (중요도: {spec['importance']}, 관련 컴포넌트: {spec.get('component', 'N/A')})"
        for spec in required_specs
    ])
    
    # 힌트 로드맵 정보
    hint_roadmap = ai_guide.get("hint_roadmap", {})
    hint_roadmap_text = ""
    if hint_roadmap:
        hint_roadmap_text = "\n".join([
            f"- {key}: {value}"
            for key, value in hint_roadmap.items()
        ])
    
    try:
        return render_prompt(
            "spec_extractor",
            problem_title=problem_title,
            algorithms=algorithms_text,
            required_specs=required_specs_text,
            hint_roadmap=hint_roadmap_text,
            user_prompt=user_prompt,
        )
    except Exception as e:
        logger.warning(f"[Spec Extractor] 프롬프트 렌더링 실패, 기본 프롬프트 사용: {e}")
        return _get_fallback_prompt(
            problem_title, algorithms_text, required_specs_text, hint_roadmap_text, user_prompt
        )


def _get_fallback_prompt(
    problem_title: str,
    algorithms: str,
    required_specs: str,
    hint_roadmap: str,
    user_prompt: str
) -> str:
    """YAML 로드 실패 시 사용하는 기본 프롬프트"""
    return f"""# Role: Spec Extractor

당신은 프로그래밍 문제 해결 요청에서 요구사항(Spec)을 추출하는 분석가입니다.

## 문제 정보
- 문제: {problem_title}
- 필수 알고리즘: {algorithms}

## 이 문제의 필수 요구사항
{required_specs}

## 힌트 로드맵 참고
{hint_roadmap}

## 사용자 프롬프트
{user_prompt}

## 분석 지침

1. **명시된 요구사항 (specified_requirements)**
   - 사용자가 명확하게 언급한 알고리즘, 자료구조, 접근 방식
   - 명시적으로 요청한 시간/공간 복잡도
   - 구체적인 구현 방식 요청

2. **누락된 요구사항 (missing_requirements)**
   - 필수 요구사항 중 사용자가 언급하지 않은 항목
   - 각 누락 항목의 중요도 평가 (HIGH/MEDIUM/LOW)
   - 관련 코드 구성 요소 매핑

3. **모호한 요구사항 (ambiguous_requirements)**
   - 해석이 불분명한 요청
   - 여러 가지로 해석 가능한 표현
   - 추가 명확화가 필요한 부분

4. **프롬프트 품질 점수 (prompt_quality_score)**
   - 0-100 점 척도
   - 높은 점수: 구체적, 명확, 완전한 요구사항 명시
   - 낮은 점수: 모호, 불완전, "정답 알려줘" 류의 요청

## 출력 형식

JSON 형식으로 SpecResult 모델에 맞게 응답하세요.
"""


async def spec_extractor(state: MainGraphState) -> Dict[str, Any]:
    """
    사용자 프롬프트에서 요구사항을 추출하는 노드
    
    Args:
        state: 메인 그래프 상태
        
    Returns:
        spec_result를 포함한 상태 업데이트 딕셔너리
    """
    human_message = state.get("human_message", "")
    problem_context = state.get("problem_context", {})
    
    logger.info(f"[Spec Extractor] 시작 - prompt: {human_message[:100]}...")
    
    # 가드레일 위반 시 건너뛰기
    if state.get("is_guardrail_failed", False):
        logger.info("[Spec Extractor] 가드레일 위반으로 건너뜀")
        return {
            "spec_result": None,
            "turn_analysis": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    # 문제 정보가 없으면 기본 분석만 수행
    if not problem_context:
        logger.warning("[Spec Extractor] 문제 정보 없음, 기본 분석 수행")
        basic_spec_result = {
            "specified_requirements": [],
            "missing_requirements": [],
            "ambiguous_requirements": ["문제 정보가 제공되지 않아 상세 분석 불가"],
            "prompt_quality_score": 50.0,
            "analysis_reasoning": "문제 정보가 없어 기본 분석만 수행됨",
        }
        # Phase 6B: 기본 TurnAnalysis 생성
        basic_turn_analysis = create_turn_analysis(state, basic_spec_result, human_message)
        return {
            "spec_result": basic_spec_result,
            "turn_analysis": basic_turn_analysis,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    try:
        # 필수 Spec 목록 생성
        required_specs = get_required_specs_for_problem(problem_context)
        
        # 시스템 프롬프트 생성
        system_prompt = create_spec_extractor_prompt(
            user_prompt=human_message,
            problem_context=problem_context,
            required_specs=required_specs,
        )
        
        # LLM 호출
        llm = get_llm(node_name="spec_extractor", temperature=0.2)  # 낮은 temperature로 일관된 분석
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"다음 사용자 프롬프트를 분석하세요:\n\n{human_message}"),
        ]
        
        # 구조화된 출력으로 LLM 호출
        structured_llm = llm.with_structured_output(SpecResult)
        response = await structured_llm.ainvoke(messages)
        
        # 토큰 사용량 추적
        if hasattr(response, "_llm_response"):
            tokens = extract_token_usage(response._llm_response)
            if tokens:
                accumulate_tokens(
                    state,
                    tokens,
                    token_type="chat",
                    chat_prompt_token_override=estimate_user_text_tokens(
                        human_message
                    ),
                )
        
        # SpecResult를 딕셔너리로 변환
        spec_result = {
            "specified_requirements": response.specified_requirements,
            "missing_requirements": [
                {
                    "category": mr.category,
                    "description": mr.description,
                    "importance": mr.importance,
                    "related_component": mr.related_component,
                }
                for mr in response.missing_requirements
            ],
            "ambiguous_requirements": response.ambiguous_requirements,
            "prompt_quality_score": response.prompt_quality_score,
            "analysis_reasoning": response.analysis_reasoning,
        }
        
        logger.info(
            f"[Spec Extractor] 완료 - "
            f"명시: {len(spec_result['specified_requirements'])}, "
            f"누락: {len(spec_result['missing_requirements'])}, "
            f"모호: {len(spec_result['ambiguous_requirements'])}, "
            f"품질점수: {spec_result['prompt_quality_score']}"
        )
        
        # Phase 6B: TurnAnalysis 생성
        turn_analysis = create_turn_analysis(state, spec_result, human_message)
        
        return {
            "spec_result": spec_result,
            "turn_analysis": turn_analysis,  # Phase 6B: 통합 평가용
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"[Spec Extractor] 에러 발생: {str(e)}", exc_info=True)
        
        # 에러 시 기본 분석 결과 반환
        error_spec_result = {
            "specified_requirements": [],
            "missing_requirements": [],
            "ambiguous_requirements": [],
            "prompt_quality_score": 50.0,
            "analysis_reasoning": f"분석 중 오류 발생: {str(e)}",
        }
        # Phase 6B: 에러 시에도 기본 TurnAnalysis 생성
        error_turn_analysis = create_turn_analysis(state, error_spec_result, human_message)
        return {
            "spec_result": error_spec_result,
            "turn_analysis": error_turn_analysis,
            "error_message": f"Spec 추출 중 오류: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


# ===== Phase 6B: TurnAnalysis 생성 함수 =====


def calculate_clarity_score(user_prompt: str) -> float:
    """
    프롬프트 명확성 점수 계산 (규칙 기반)
    
    명확성 기준:
    - 구체적인 알고리즘/자료구조 언급
    - 명확한 요구사항 표현
    - 질문의 명확성
    
    Args:
        user_prompt: 사용자 프롬프트
        
    Returns:
        명확성 점수 (0-100)
    """
    score = 30.0  # 기본 점수
    prompt_lower = user_prompt.lower()
    
    # 명확한 알고리즘/자료구조 언급 (+점수)
    algorithm_keywords = [
        ("dp", 8), ("dynamic programming", 10), ("동적 프로그래밍", 10),
        ("bfs", 8), ("dfs", 8), ("이진탐색", 8), ("binary search", 8),
        ("그리디", 8), ("greedy", 8), ("분할정복", 8), ("divide and conquer", 8),
        ("백트래킹", 8), ("backtracking", 8), ("비트마스킹", 10), ("bitmask", 10),
        ("메모이제이션", 10), ("memoization", 10), ("재귀", 5), ("recursion", 5),
    ]
    
    # 구체적인 요구사항 표현 (+점수)
    specific_keywords = [
        ("시간복잡도", 10), ("time complexity", 10), ("o(", 8),
        ("공간복잡도", 8), ("space complexity", 8),
        ("점화식", 10), ("상태정의", 10), ("state", 5),
        ("기저조건", 10), ("base case", 10),
        ("입력", 5), ("출력", 5), ("예시", 8), ("example", 8),
    ]
    
    # 모호한 표현 (-점수)
    vague_keywords = [
        ("그냥", -10), ("대충", -10), ("뭔가", -5),
        ("어떻게든", -8), ("아무거나", -10),
    ]
    
    for keyword, points in algorithm_keywords:
        if keyword in prompt_lower:
            score += points
    
    for keyword, points in specific_keywords:
        if keyword in prompt_lower:
            score += points
    
    for keyword, points in vague_keywords:
        if keyword in prompt_lower:
            score += points
    
    # 프롬프트 길이 보너스 (적절한 길이)
    length = len(user_prompt)
    if 50 <= length <= 500:
        score += 10
    elif length > 500:
        score += 5  # 너무 길면 보너스 감소
    
    return max(0.0, min(100.0, score))


def has_structure(user_prompt: str) -> bool:
    """
    프롬프트 구조화 여부 확인
    
    구조화 기준:
    - XML/HTML 태그 사용
    - 마크다운 문법 사용
    - 번호/불릿 리스트 사용
    - 명확한 섹션 구분
    
    Args:
        user_prompt: 사용자 프롬프트
        
    Returns:
        구조화 여부 (True/False)
    """
    import re
    
    # XML/HTML 태그 패턴
    xml_pattern = r'<[^>]+>'
    if re.search(xml_pattern, user_prompt):
        return True
    
    # 마크다운 헤더 (#, ##, ###)
    if re.search(r'^#{1,3}\s', user_prompt, re.MULTILINE):
        return True
    
    # 마크다운 코드 블록
    if '```' in user_prompt or '`' in user_prompt:
        return True
    
    # 번호 리스트 (1. 2. 3. 또는 1) 2) 3))
    if re.search(r'^\s*\d+[\.\)]\s', user_prompt, re.MULTILINE):
        return True
    
    # 불릿 리스트 (-, *, •)
    if re.search(r'^\s*[-*•]\s', user_prompt, re.MULTILINE):
        return True
    
    # 명확한 섹션 구분 (===, ---, 등)
    if re.search(r'^[-=]{3,}', user_prompt, re.MULTILINE):
        return True
    
    # 대괄호 구조 ([조건], [입력], [출력] 등)
    if re.search(r'\[[^\]]+\]', user_prompt):
        return True
    
    return False


def has_examples(user_prompt: str) -> bool:
    """
    프롬프트에 예시 포함 여부 확인
    
    예시 기준:
    - I/O 예시 (입력/출력 샘플)
    - 구체적인 테스트 케이스
    - 엣지 케이스 언급
    
    Args:
        user_prompt: 사용자 프롬프트
        
    Returns:
        예시 포함 여부 (True/False)
    """
    import re
    
    prompt_lower = user_prompt.lower()
    
    # I/O 예시 패턴
    io_patterns = [
        r'입력\s*[:：]?\s*\d',  # 입력: 5
        r'출력\s*[:：]?\s*\d',  # 출력: 10
        r'input\s*[:：]?\s*\d',
        r'output\s*[:：]?\s*\d',
        r'예[시제]\s*[:：]',  # 예시:, 예제:
        r'example\s*[:：]',
        r'sample\s*[:：]',
        r'테스트\s*케이스',
        r'test\s*case',
    ]
    
    for pattern in io_patterns:
        if re.search(pattern, prompt_lower):
            return True
    
    # 구체적인 숫자 배열 예시 (예: [1, 2, 3] 또는 1 2 3)
    if re.search(r'\[\s*\d+(\s*,\s*\d+)+\s*\]', user_prompt):
        return True
    
    # 엣지 케이스 언급
    edge_keywords = [
        "엣지", "edge", "경계", "boundary",
        "최대", "최소", "max", "min",
        "빈 배열", "empty", "0인 경우", "1인 경우",
    ]
    
    for keyword in edge_keywords:
        if keyword in prompt_lower:
            return True
    
    return False


def has_specific_values(user_prompt: str) -> bool:
    """
    프롬프트에 구체적인 값/조건 포함 여부 확인
    
    구체적 값 기준:
    - 숫자 제약 조건 (N <= 1000 등)
    - 시간/공간 복잡도 명시
    - 구체적인 범위 지정
    
    Args:
        user_prompt: 사용자 프롬프트
        
    Returns:
        구체적 값 포함 여부 (True/False)
    """
    import re
    
    prompt_lower = user_prompt.lower()
    
    # 부등식 조건 (N <= 1000, n < 100 등)
    if re.search(r'[a-zA-Z]\s*[<>]=?\s*\d+', user_prompt):
        return True
    
    # 범위 표현 (1 ~ 100, 1-100, 1..100 등)
    if re.search(r'\d+\s*[~\-\.]{1,2}\s*\d+', user_prompt):
        return True
    
    # 시간복잡도 표현 (O(N), O(N^2), O(N log N) 등)
    if re.search(r'o\s*\([^)]+\)', prompt_lower):
        return True
    
    # 구체적인 숫자 제약
    constraint_patterns = [
        r'\d+\s*(이하|이상|미만|초과)',  # 1000 이하
        r'(최대|최소|max|min)\s*\d+',  # 최대 1000
        r'\d+\s*(개|번|초|ms|바이트|byte)',  # 1000개, 1초
    ]
    
    for pattern in constraint_patterns:
        if re.search(pattern, prompt_lower):
            return True
    
    # 메모리 제한 언급
    if re.search(r'\d+\s*(mb|kb|gb|메가|킬로)', prompt_lower):
        return True
    
    return False


def count_recovered_specs(
    state: MainGraphState,
    current_missing: List[Dict[str, Any]]
) -> tuple[int, List[str]]:
    """
    이전 턴 대비 회복된 Spec 수 계산
    
    Args:
        state: 현재 그래프 상태
        current_missing: 현재 턴의 누락 Spec 목록
        
    Returns:
        (회복된 Spec 수, 회복된 Spec 카테고리 목록)
    """
    # 첫 턴이면 회복 없음
    current_turn = state.get("current_turn", 1)
    if current_turn <= 1:
        return 0, []
    
    # 이전 턴의 spec_result 확인
    prev_spec_result = state.get("spec_result")
    if not prev_spec_result:
        return 0, []
    
    prev_missing = prev_spec_result.get("missing_requirements", [])
    if not prev_missing:
        return 0, []
    
    # 이전에 누락되었다가 현재는 누락되지 않은 것 = 회복됨
    prev_categories = {m.get("category") for m in prev_missing}
    current_categories = {m.get("category") for m in current_missing}
    
    recovered = prev_categories - current_categories
    
    return len(recovered), list(recovered)


def references_previous_turn(user_prompt: str) -> bool:
    """
    사용자 프롬프트가 이전 턴을 참조하는지 확인
    
    Args:
        user_prompt: 사용자 프롬프트
        
    Returns:
        이전 턴 참조 여부
    """
    import re
    
    prompt_lower = user_prompt.lower()
    
    # 이전 턴 참조 패턴
    reference_patterns = [
        r'(아까|방금|이전|위에서|앞에서)',
        r'(말씀하신|말한|언급한|설명한)',
        r'(그|그것|그거|이것|저것).*?(대해|관해|관련)',
        r'(다시|한번\s*더|추가로)',
        r'(수정|변경|바꿔|고쳐)',
        r'(이해가|모르겠|헷갈|다시\s*설명)',
        r'(위\s*코드|해당\s*코드|그\s*코드)',
    ]
    
    for pattern in reference_patterns:
        if re.search(pattern, prompt_lower):
            return True
    
    return False


def generate_turn_summary(
    user_prompt: str,
    spec_result: Dict[str, Any],
    max_length: int = 150
) -> str:
    """
    턴 요약 생성 (프롬프트 + Spec 분석 기반)
    
    Args:
        user_prompt: 사용자 프롬프트
        spec_result: Spec 분석 결과
        max_length: 최대 길이
        
    Returns:
        요약 문자열
    """
    # 명시된 Spec
    specified = spec_result.get("specified_requirements", [])
    specified_text = ", ".join(specified[:3]) if specified else "없음"
    
    # 누락된 Spec (HIGH 중요도만)
    missing = spec_result.get("missing_requirements", [])
    high_missing = [m["category"] for m in missing if m.get("importance") == "HIGH"]
    missing_text = ", ".join(high_missing[:3]) if high_missing else "없음"
    
    # 품질 점수
    quality = spec_result.get("prompt_quality_score", 50)
    
    # 요약 생성
    if quality >= 80:
        quality_desc = "우수"
    elif quality >= 60:
        quality_desc = "양호"
    elif quality >= 40:
        quality_desc = "보통"
    else:
        quality_desc = "미흡"
    
    summary = f"[{quality_desc}] 명시: {specified_text} | 누락(HIGH): {missing_text}"
    
    # 길이 제한
    if len(summary) > max_length:
        summary = summary[:max_length-3] + "..."
    
    return summary


def create_turn_analysis(
    state: MainGraphState,
    spec_result: Dict[str, Any],
    user_prompt: str,
) -> Dict[str, Any]:
    """
    TurnAnalysis 생성 (Spec 분석 결과 기반)
    
    Args:
        state: 현재 그래프 상태
        spec_result: Spec Extractor 결과
        user_prompt: 사용자 프롬프트
        
    Returns:
        TurnAnalysis 딕셔너리
    """
    current_turn = state.get("current_turn", 1)
    
    # 표현 품질 지표 계산
    clarity = calculate_clarity_score(user_prompt)
    structure = has_structure(user_prompt)
    examples = has_examples(user_prompt)
    specific_values = has_specific_values(user_prompt)
    
    # Spec 회복 계산
    missing_specs = spec_result.get("missing_requirements", [])
    recovery_count, recovered_specs = count_recovered_specs(state, missing_specs)
    
    # 이전 턴 참조 여부
    refs_previous = references_previous_turn(user_prompt) if current_turn > 1 else False
    
    # 요약 생성
    summary = generate_turn_summary(user_prompt, spec_result)
    
    # TurnAnalysis 딕셔너리 생성
    turn_analysis = {
        "turn": current_turn,
        "is_first_prompt": current_turn == 1,
        
        # Spec 분석
        "spec_completeness": spec_result.get("prompt_quality_score", 50.0),
        "specified_specs": spec_result.get("specified_requirements", []),
        "missing_specs": [
            {
                "category": m.get("category", ""),
                "importance": m.get("importance", "MEDIUM"),
                "related_component": m.get("related_component"),
            }
            for m in missing_specs
        ],
        "ambiguous_specs": spec_result.get("ambiguous_requirements", []),
        
        # 표현 품질
        "clarity_score": clarity,
        "has_structure": structure,
        "has_examples": examples,
        "has_specific_values": specific_values,
        
        # 맥락 연결
        "spec_recovery_count": recovery_count,
        "references_previous": refs_previous,
        "recovered_specs": recovered_specs,
        
        # 요약
        "summary": summary,
    }
    
    logger.info(
        f"[TurnAnalysis] 생성 완료 - turn: {current_turn}, "
        f"spec: {turn_analysis['spec_completeness']:.1f}, "
        f"clarity: {clarity:.1f}, "
        f"structure: {structure}, examples: {examples}, "
        f"recovery: {recovery_count}"
    )
    
    return turn_analysis


# ===== 유틸리티 함수 =====


def analyze_prompt_quality_simple(user_prompt: str, problem_context: Dict[str, Any]) -> float:
    """
    간단한 규칙 기반 프롬프트 품질 분석 (LLM 없이)
    
    Args:
        user_prompt: 사용자 프롬프트
        problem_context: 문제 정보
        
    Returns:
        품질 점수 (0-100)
    """
    score = 50.0  # 기본 점수
    prompt_lower = user_prompt.lower()
    
    # 부정적 패턴 (감점)
    negative_patterns = [
        ("정답", -20),
        ("답 알려", -20),
        ("코드 줘", -15),
        ("복붙", -20),
        ("그냥", -10),
        ("빨리", -5),
    ]
    
    # 긍정적 패턴 (가점)
    positive_patterns = [
        ("점화식", 10),
        ("시간복잡도", 10),
        ("공간복잡도", 8),
        ("dp", 5),
        ("메모이제이션", 10),
        ("비트마스킹", 10),
        ("상태", 5),
        ("기저조건", 10),
        ("재귀", 5),
        ("접근", 5),
        ("방법", 3),
        ("왜", 5),
        ("어떻게", 5),
    ]
    
    for pattern, adjustment in negative_patterns:
        if pattern in prompt_lower:
            score += adjustment
    
    for pattern, adjustment in positive_patterns:
        if pattern in prompt_lower:
            score += adjustment
    
    # 프롬프트 길이 보너스
    if len(user_prompt) > 100:
        score += 5
    if len(user_prompt) > 200:
        score += 5
    
    # 범위 제한
    return max(0.0, min(100.0, score))
