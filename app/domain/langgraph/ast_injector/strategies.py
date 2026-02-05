"""
변형 전략 정의

[Phase 6-a Task 6a-4]
코드 변형에 사용되는 전략들을 정의합니다.

[변형 유형]
- REMOVE: 완전 제거
- SIMPLIFY: 단순화
- MAKE_INCORRECT: 잘못된 로직
- MAKE_INCOMPLETE: 불완전하게
- REPLACE_ALGORITHM: 다른 알고리즘 대체
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from app.domain.langgraph.ast_injector.components import ComponentType


class ModificationType(Enum):
    """변형 유형"""
    
    REMOVE = "remove"
    """완전 제거 - 해당 코드 블록을 제거"""
    
    SIMPLIFY = "simplify"
    """단순화 - 복잡한 로직을 단순한 버전으로 대체"""
    
    MAKE_INCORRECT = "incorrect"
    """잘못된 로직 - 미묘하게 틀린 로직으로 변경"""
    
    MAKE_INCOMPLETE = "incomplete"
    """불완전하게 - 일부만 구현하고 TODO 주석 남기기"""
    
    REPLACE_ALGORITHM = "replace"
    """다른 알고리즘 대체 - 비효율적인 알고리즘으로 대체"""
    
    ADD_TODO = "add_todo"
    """TODO 주석 추가 - 구현해야 할 부분을 표시"""
    
    PASS_PLACEHOLDER = "pass_placeholder"
    """pass로 대체 - 로직을 pass 문으로 대체"""


@dataclass
class ModificationStrategy:
    """
    변형 전략
    
    특정 컴포넌트 타입에 적용할 수 있는 변형 방법을 정의합니다.
    """
    
    modification_type: ModificationType
    """변형 유형"""
    
    target_component_types: List[ComponentType]
    """적용 가능한 컴포넌트 타입"""
    
    description: str
    """전략 설명"""
    
    code_template: str = ""
    """변형에 사용할 코드 템플릿"""
    
    preserves_structure: bool = True
    """코드 구조 유지 여부"""
    
    difficulty_level: int = 1
    """난이도 (1-5, 높을수록 찾기 어려움)"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """추가 메타데이터"""


# ===== 컴포넌트별 변형 전략 =====

# 기저 조건 변형 전략
BASE_CASE_STRATEGIES = [
    ModificationStrategy(
        modification_type=ModificationType.REMOVE,
        target_component_types=[ComponentType.BASE_CASE],
        description="기저 조건 완전 제거 (무한 재귀 발생)",
        code_template="# TODO: 기저 조건 구현 필요",
        preserves_structure=False,
        difficulty_level=1,
    ),
    ModificationStrategy(
        modification_type=ModificationType.MAKE_INCOMPLETE,
        target_component_types=[ComponentType.BASE_CASE],
        description="기저 조건 일부만 처리 (edge case 누락)",
        code_template="if {condition}:\n    return {partial_value}  # TODO: 다른 케이스 처리 필요",
        preserves_structure=True,
        difficulty_level=3,
    ),
    ModificationStrategy(
        modification_type=ModificationType.MAKE_INCORRECT,
        target_component_types=[ComponentType.BASE_CASE],
        description="잘못된 반환값 (off-by-one 에러)",
        code_template="if {condition}:\n    return {wrong_value}  # 의도적으로 잘못된 값",
        preserves_structure=True,
        difficulty_level=4,
    ),
]

# 메모이제이션 변형 전략
MEMOIZATION_STRATEGIES = [
    ModificationStrategy(
        modification_type=ModificationType.REMOVE,
        target_component_types=[
            ComponentType.MEMOIZATION,
            ComponentType.DECORATOR,
            ComponentType.MEMOIZATION_CHECK,
            ComponentType.MEMOIZATION_STORE,
        ],
        description="메모이제이션 완전 제거 (시간 초과 발생)",
        code_template="# 메모이제이션 없이 구현 - 시간 복잡도 증가",
        preserves_structure=True,
        difficulty_level=2,
    ),
    ModificationStrategy(
        modification_type=ModificationType.MAKE_INCOMPLETE,
        target_component_types=[
            ComponentType.MEMOIZATION,
            ComponentType.DP_ARRAY_INIT,
        ],
        description="메모이제이션 초기화만 남기고 사용 안 함",
        code_template="dp = {}  # TODO: 메모이제이션 로직 추가 필요",
        preserves_structure=True,
        difficulty_level=3,
    ),
]

# 비트 연산 변형 전략
BIT_OPERATION_STRATEGIES = [
    ModificationStrategy(
        modification_type=ModificationType.REPLACE_ALGORITHM,
        target_component_types=[
            ComponentType.BIT_OPERATION,
            ComponentType.BIT_AND,
            ComponentType.BIT_OR,
            ComponentType.BIT_SHIFT,
        ],
        description="비트 연산을 집합(set)으로 대체 (메모리 비효율)",
        code_template="visited_set.add({city})  # 비트마스크 대신 집합 사용",
        preserves_structure=True,
        difficulty_level=2,
    ),
    ModificationStrategy(
        modification_type=ModificationType.SIMPLIFY,
        target_component_types=[ComponentType.BIT_OPERATION],
        description="비트 연산을 리스트로 대체 (메모리 비효율)",
        code_template="visited_list[{city}] = True  # 비트마스크 대신 리스트 사용",
        preserves_structure=True,
        difficulty_level=2,
    ),
    ModificationStrategy(
        modification_type=ModificationType.MAKE_INCOMPLETE,
        target_component_types=[ComponentType.BIT_OPERATION],
        description="비트 연산 일부만 구현",
        code_template="# TODO: 비트 연산으로 상태 관리 구현 필요\npass",
        preserves_structure=False,
        difficulty_level=3,
    ),
]

# 상태 전이 (점화식) 변형 전략
STATE_TRANSITION_STRATEGIES = [
    ModificationStrategy(
        modification_type=ModificationType.MAKE_INCORRECT,
        target_component_types=[
            ComponentType.STATE_TRANSITION,
            ComponentType.DP_UPDATE,
        ],
        description="점화식 오류 (최솟값 대신 최댓값 등)",
        code_template="dp[state] = max(...)  # 잘못된 연산자 사용",
        preserves_structure=True,
        difficulty_level=4,
    ),
    ModificationStrategy(
        modification_type=ModificationType.MAKE_INCOMPLETE,
        target_component_types=[ComponentType.STATE_TRANSITION],
        description="점화식 일부만 구현 (모든 케이스 미처리)",
        code_template="# TODO: 점화식 완성 필요\nresult = {partial_formula}",
        preserves_structure=True,
        difficulty_level=3,
    ),
    ModificationStrategy(
        modification_type=ModificationType.ADD_TODO,
        target_component_types=[ComponentType.STATE_TRANSITION],
        description="점화식 위치에 TODO 주석만 남기기",
        code_template="# TODO: 상태 전이 로직 구현\n# dp[current][visited] = ???",
        preserves_structure=False,
        difficulty_level=2,
    ),
]

# 루프 구조 변형 전략
LOOP_STRUCTURE_STRATEGIES = [
    ModificationStrategy(
        modification_type=ModificationType.MAKE_INCORRECT,
        target_component_types=[ComponentType.LOOP_STRUCTURE],
        description="루프 범위 오류 (off-by-one)",
        code_template="for i in range({wrong_range}):  # 범위 오류",
        preserves_structure=True,
        difficulty_level=4,
    ),
    ModificationStrategy(
        modification_type=ModificationType.SIMPLIFY,
        target_component_types=[ComponentType.LOOP_STRUCTURE],
        description="중첩 루프를 비효율적으로 변경",
        code_template="for i in {outer_range}:\n    for j in {inner_range}:  # O(N^2) 비효율",
        preserves_structure=True,
        difficulty_level=3,
    ),
]

# 재귀 호출 변형 전략
RECURSIVE_CALL_STRATEGIES = [
    ModificationStrategy(
        modification_type=ModificationType.MAKE_INCOMPLETE,
        target_component_types=[ComponentType.RECURSIVE_CALL],
        description="재귀 호출 구조만 남기고 로직 제거",
        code_template="def {func_name}(...):\n    # TODO: 재귀 로직 구현 필요\n    pass",
        preserves_structure=True,
        difficulty_level=2,
    ),
    ModificationStrategy(
        modification_type=ModificationType.MAKE_INCORRECT,
        target_component_types=[ComponentType.RECURSIVE_CALL],
        description="잘못된 재귀 인자 전달",
        code_template="{func_name}({wrong_args})  # 인자 오류",
        preserves_structure=True,
        difficulty_level=4,
    ),
]

# 함수 정의 변형 전략
FUNCTION_DEF_STRATEGIES = [
    ModificationStrategy(
        modification_type=ModificationType.PASS_PLACEHOLDER,
        target_component_types=[
            ComponentType.FUNCTION_DEF,
            ComponentType.MAIN_FUNCTION,
        ],
        description="함수 시그니처만 남기고 본문을 pass로 대체",
        code_template="def {func_name}({args}):\n    # TODO: 구현 필요\n    pass",
        preserves_structure=True,
        difficulty_level=1,
    ),
    ModificationStrategy(
        modification_type=ModificationType.MAKE_INCOMPLETE,
        target_component_types=[ComponentType.FUNCTION_DEF],
        description="함수 일부만 구현",
        code_template="def {func_name}({args}):\n    {partial_implementation}\n    # TODO: 나머지 구현",
        preserves_structure=True,
        difficulty_level=3,
    ),
]


# ===== 전략 레지스트리 =====

STRATEGY_REGISTRY: Dict[ComponentType, List[ModificationStrategy]] = {
    ComponentType.BASE_CASE: BASE_CASE_STRATEGIES,
    ComponentType.MEMOIZATION: MEMOIZATION_STRATEGIES,
    ComponentType.MEMOIZATION_CHECK: MEMOIZATION_STRATEGIES,
    ComponentType.MEMOIZATION_STORE: MEMOIZATION_STRATEGIES,
    ComponentType.DECORATOR: MEMOIZATION_STRATEGIES,
    ComponentType.DP_ARRAY_INIT: MEMOIZATION_STRATEGIES,
    ComponentType.BIT_OPERATION: BIT_OPERATION_STRATEGIES,
    ComponentType.BIT_AND: BIT_OPERATION_STRATEGIES,
    ComponentType.BIT_OR: BIT_OPERATION_STRATEGIES,
    ComponentType.BIT_SHIFT: BIT_OPERATION_STRATEGIES,
    ComponentType.STATE_TRANSITION: STATE_TRANSITION_STRATEGIES,
    ComponentType.DP_UPDATE: STATE_TRANSITION_STRATEGIES,
    ComponentType.LOOP_STRUCTURE: LOOP_STRUCTURE_STRATEGIES,
    ComponentType.RECURSIVE_CALL: RECURSIVE_CALL_STRATEGIES,
    ComponentType.FUNCTION_DEF: FUNCTION_DEF_STRATEGIES,
    ComponentType.MAIN_FUNCTION: FUNCTION_DEF_STRATEGIES,
}


def get_strategies_for_component(
    component_type: ComponentType,
) -> List[ModificationStrategy]:
    """
    특정 컴포넌트 타입에 대한 변형 전략 목록을 반환합니다.
    
    Args:
        component_type: 컴포넌트 타입
        
    Returns:
        적용 가능한 변형 전략 목록
    """
    return STRATEGY_REGISTRY.get(component_type, [])


def get_strategy_by_type(
    component_type: ComponentType,
    modification_type: ModificationType,
) -> Optional[ModificationStrategy]:
    """
    특정 컴포넌트 타입과 변형 유형에 맞는 전략을 반환합니다.
    
    Args:
        component_type: 컴포넌트 타입
        modification_type: 변형 유형
        
    Returns:
        해당하는 전략 또는 None
    """
    strategies = get_strategies_for_component(component_type)
    for strategy in strategies:
        if strategy.modification_type == modification_type:
            return strategy
    return None


def select_best_strategy(
    component_type: ComponentType,
    spec_importance: str = "MEDIUM",
    prefer_type: Optional[ModificationType] = None,
) -> Optional[ModificationStrategy]:
    """
    최적의 변형 전략을 선택합니다.
    
    Args:
        component_type: 컴포넌트 타입
        spec_importance: Spec 중요도
        prefer_type: 선호하는 변형 유형
        
    Returns:
        선택된 전략 또는 None
    """
    strategies = get_strategies_for_component(component_type)
    
    if not strategies:
        return None
    
    # 선호 유형이 있으면 우선
    if prefer_type:
        for strategy in strategies:
            if strategy.modification_type == prefer_type:
                return strategy
    
    # 중요도에 따른 선택
    # HIGH: 더 심각한 변형 (REMOVE, MAKE_INCORRECT)
    # MEDIUM: 중간 수준 (MAKE_INCOMPLETE, SIMPLIFY)
    # LOW: 가벼운 변형 (ADD_TODO, PASS_PLACEHOLDER)
    
    priority_map = {
        "HIGH": [
            ModificationType.REMOVE,
            ModificationType.MAKE_INCORRECT,
            ModificationType.MAKE_INCOMPLETE,
        ],
        "MEDIUM": [
            ModificationType.MAKE_INCOMPLETE,
            ModificationType.SIMPLIFY,
            ModificationType.REPLACE_ALGORITHM,
        ],
        "LOW": [
            ModificationType.ADD_TODO,
            ModificationType.PASS_PLACEHOLDER,
            ModificationType.SIMPLIFY,
        ],
    }
    
    preferred_types = priority_map.get(spec_importance, priority_map["MEDIUM"])
    
    for mod_type in preferred_types:
        for strategy in strategies:
            if strategy.modification_type == mod_type:
                return strategy
    
    # 기본: 첫 번째 전략 반환
    return strategies[0]
