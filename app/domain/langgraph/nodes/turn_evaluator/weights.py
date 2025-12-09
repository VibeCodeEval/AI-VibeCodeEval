"""
의도별 평가 루브릭 가중치 설정

각 의도(Intent)에 따라 5가지 평가 기준(규칙, 명확성, 예시, 문제 적절성, 문맥)의
가중치가 다르게 적용됩니다.
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

# 의도별 가중치 설정
# 형식: {의도: {루브릭_키: 가중치}}
INTENT_WEIGHTS: Dict[str, Dict[str, float]] = {
    "GENERATION": {
        "rules": 0.3,
        "clarity": 0.25,
        "examples": 0.25,
        "problem_relevance": 0.1,
        "context": 0.1,
    },
    "OPTIMIZATION": {
        "rules": 0.4,
        "clarity": 0.2,
        "examples": 0.05,
        "problem_relevance": 0.05,
        "context": 0.3,
    },
    "DEBUGGING": {
        "rules": 0.05,
        "clarity": 0.3,
        "examples": 0.2,
        "problem_relevance": 0.05,
        "context": 0.4,
    },
    "TEST_CASE": {
        "rules": 0.4,
        "clarity": 0.2,
        "examples": 0.3,
        "problem_relevance": 0.05,
        "context": 0.05,
    },
    "HINT_OR_QUERY": {
        "rules": 0.0,
        "clarity": 0.5,
        "examples": 0.0,
        "problem_relevance": 0.3,
        "context": 0.2,
    },
    "RULE_SETTING": {
        "rules": 0.7,
        "clarity": 0.3,
        "examples": 0.0,
        "problem_relevance": 0.0,
        "context": 0.0,
    },
    "FOLLOW_UP": {
        "rules": 0.0,
        "clarity": 0.2,
        "examples": 0.0,
        "problem_relevance": 0.0,
        "context": 0.8,
    },
    "SYSTEM_PROMPT": {
        "rules": 0.6,
        "clarity": 0.4,
        "examples": 0.0,
        "problem_relevance": 0.0,
        "context": 0.0,
    },
}


def get_weights_for_intent(intent: str) -> Dict[str, float]:
    """
    의도에 따른 가중치 반환
    
    Args:
        intent: 의도 타입 (예: "GENERATION", "OPTIMIZATION")
    
    Returns:
        루브릭별 가중치 딕셔너리
    """
    return INTENT_WEIGHTS.get(intent, {
        "rules": 0.2,
        "clarity": 0.2,
        "examples": 0.2,
        "problem_relevance": 0.2,
        "context": 0.2,
    })


def get_weight_for_rubric(intent: str, rubric_name: str) -> float:
    """
    특정 의도와 루브릭에 대한 가중치 반환
    
    Args:
        intent: 의도 타입
        rubric_name: 루브릭 이름 (한글 또는 영문 키)
    
    Returns:
        가중치 (0.0 ~ 1.0)
    """
    weights = get_weights_for_intent(intent)
    
    # 한글 이름인 경우 영문 키로 변환
    rubric_key = RUBRIC_NAME_MAP.get(rubric_name, rubric_name.lower().replace(" ", "_"))
    
    return weights.get(rubric_key, 0.2)  # 기본값 0.2


def calculate_weighted_score(rubrics: list, intent: str) -> float:
    """
    가중치를 적용한 총점 계산
    
    Args:
        rubrics: 루브릭 리스트 (각 항목은 {"criterion": str, "score": float} 형식)
        intent: 의도 타입
    
    Returns:
        가중치 적용 후 총점 (0-100)
    """
    weights = get_weights_for_intent(intent)
    total_score = 0.0
    
    for rubric in rubrics:
        criterion = rubric.get("criterion", "")
        score = rubric.get("score", 0.0)
        
        # 루브릭 이름을 영문 키로 변환
        rubric_key = RUBRIC_NAME_MAP.get(criterion, criterion.lower().replace(" ", "_"))
        
        # 가중치 적용
        weight = weights.get(rubric_key, 0.2)
        total_score += score * weight
    
    return round(total_score, 2)

