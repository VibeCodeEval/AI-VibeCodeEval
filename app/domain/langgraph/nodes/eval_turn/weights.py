"""
의도 그룹 매핑 및 루브릭 이름 (v2.1 Hybrid: 가중치 산식 폐기)

- 6대 통합 그룹(SETTING, CREATION, REFINEMENT, DEBUGGING, EXPLORATION, FOLLOW_UP) 정의.
- 점수 산출은 grading.py의 1~5 Likert → final_score 매핑 사용 (가중치 미사용).
"""

from typing import Dict

# 루브릭 이름 매핑 (한글 → 영문 키)
RUBRIC_NAME_MAP = {
    "규칙 (Rules)": "rules",
    "명확성 (Clarity)": "clarity",
    "예시 (Examples)": "examples",
    "문제 적절성 (Problem Relevance)": "problem_relevance",
    "문맥 (Context)": "context",
}

# 6대 통합 그룹 정의 (기존 8대 의도 → 6대 그룹)
NEW_INTENT_GROUPS = {
    "SETTING": ["RULE_SETTING", "SYSTEM_PROMPT"],
    "CREATION": ["GENERATION", "OPTIMIZATION"],
    "REFINEMENT": ["FIX_LOGIC", "SPECIFIC_UPDATE"],
    "DEBUGGING": ["DEBUGGING", "TEST_CASE"],
    "EXPLORATION": ["HINT_OR_QUERY"],
    "FOLLOW_UP": ["SIMPLE_ACK", "PROCEED", "FOLLOW_UP"],
}

# 세부 의도 → 5대 그룹 매핑
INTENT_GROUP_MAP: Dict[str, str] = {}
for _group, _intents in NEW_INTENT_GROUPS.items():
    for _intent in _intents:
        INTENT_GROUP_MAP[_intent.upper().replace("-", "_")] = _group


def _normalize_intent(intent: str) -> str:
    return (intent or "").upper().replace("-", "_").strip()


def intent_to_group(intent: str) -> str:
    """세부 의도(8종 등) → 5대 그룹명 반환."""
    key = _normalize_intent(intent)
    if key in INTENT_GROUP_MAP:
        return INTENT_GROUP_MAP[key]
    if key in NEW_INTENT_GROUPS:
        return key
    return "DEBUGGING"


# 루브릭 키 표시 순서 (로그/JSON 정렬용, 가중치 아님)
RUBRIC_DISPLAY_ORDER = [
    "rules",
    "clarity",
    "examples",
    "problem_relevance",
    "context",
]

# ---------------------------------------------------------------------------
# TODO: 모든 프롬프트가 V2.1로 전환된 후 삭제 예정. 삭제 후 아카이빙하여 별도 저장.
# Legacy Adapter: rubrics만 있고 score/likert_score가 없을 때만 사용 (Tier 3 Fallback).
# 신규 로직( grading.SCORE_MAPPING )과 섞이지 않도록 본 블록만 호출.
# ---------------------------------------------------------------------------

LEGACY_INTENT_WEIGHTS: Dict[str, Dict[str, float]] = {
    # V2.3 6대 통합 의도 (Legacy Adapter Tier 3용)
    "SETTING": {"rules": 0.65, "clarity": 0.35, "examples": 0.0, "problem_relevance": 0.0, "context": 0.0},
    "CREATION": {"rules": 0.3, "clarity": 0.25, "examples": 0.25, "problem_relevance": 0.1, "context": 0.1},
    "REFINEMENT": {"rules": 0.4, "clarity": 0.2, "examples": 0.05, "problem_relevance": 0.05, "context": 0.3},
    "DEBUGGING": {"rules": 0.1, "clarity": 0.35, "examples": 0.2, "problem_relevance": 0.1, "context": 0.25},
    "EXPLORATION": {"rules": 0.0, "clarity": 0.45, "examples": 0.0, "problem_relevance": 0.35, "context": 0.2},
    "VALIDATION": {"rules": 0.1, "clarity": 0.35, "examples": 0.2, "problem_relevance": 0.1, "context": 0.25},
    "FOLLOW_UP": {"rules": 0.0, "clarity": 0.2, "examples": 0.0, "problem_relevance": 0.0, "context": 0.8},
    # 레거시 8-way (하위 호환, 점진적 제거 예정)
    "GENERATION": {"rules": 0.3, "clarity": 0.25, "examples": 0.25, "problem_relevance": 0.1, "context": 0.1},
    "OPTIMIZATION": {"rules": 0.4, "clarity": 0.2, "examples": 0.05, "problem_relevance": 0.05, "context": 0.3},
    "DEBUGGING": {"rules": 0.05, "clarity": 0.3, "examples": 0.2, "problem_relevance": 0.05, "context": 0.4},
    "TEST_CASE": {"rules": 0.4, "clarity": 0.2, "examples": 0.3, "problem_relevance": 0.05, "context": 0.05},
    "HINT_OR_QUERY": {"rules": 0.0, "clarity": 0.5, "examples": 0.0, "problem_relevance": 0.3, "context": 0.2},
    "RULE_SETTING": {"rules": 0.7, "clarity": 0.3, "examples": 0.0, "problem_relevance": 0.0, "context": 0.0},
    "SYSTEM_PROMPT": {"rules": 0.6, "clarity": 0.4, "examples": 0.0, "problem_relevance": 0.0, "context": 0.0},
}


def legacy_turn_score_from_rubrics(
    rubrics: list,
    intent: str,
    context_override_100: bool = False,
) -> float:
    """
    Legacy Adapter: rubrics만 있을 때 0~100 가중 합산으로 턴 점수 계산.
    Tier 3 Fallback에서만 호출. (신규 Likert 로직과 분리)
    """
    intent_key = _normalize_intent(intent)
    weights = LEGACY_INTENT_WEIGHTS.get(
        intent_key,
        {"rules": 0.2, "clarity": 0.2, "examples": 0.2, "problem_relevance": 0.2, "context": 0.2},
    )
    total = 0.0
    for rubric in rubrics:
        criterion = rubric.get("criterion", "")
        score = rubric.get("score", 0.0)
        rubric_key = RUBRIC_NAME_MAP.get(criterion, criterion.lower().replace(" ", "_"))
        weight = weights.get(rubric_key, 0.2)
        if rubric_key == "context" and context_override_100:
            score = 100.0
        elif rubric_key in ("examples", "rules") and (score is None or score <= 0):
            score = 70.0
        total += (float(score) if score is not None else 0.0) * weight
    return round(total, 2)
