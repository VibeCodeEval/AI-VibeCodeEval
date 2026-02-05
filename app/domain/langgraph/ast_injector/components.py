"""
코드 구성 요소 타입 정의

[Phase 6-a Task 6a-2]
AST 분석에서 식별되는 코드 구성 요소 유형을 정의합니다.

[구성 요소 유형]
- FUNCTION_DEF: 함수 정의
- BASE_CASE: 기저 조건
- RECURSIVE_CALL: 재귀 호출
- MEMOIZATION: 메모이제이션
- BIT_OPERATION: 비트 연산
- LOOP_STRUCTURE: 루프 구조
- STATE_TRANSITION: 상태 전이 (점화식)
- INPUT_PROCESSING: 입력 처리
- OUTPUT_PROCESSING: 출력 처리
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ComponentType(Enum):
    """코드 구성 요소 유형"""
    
    # 함수 관련
    FUNCTION_DEF = "function_definition"
    MAIN_FUNCTION = "main_function"
    HELPER_FUNCTION = "helper_function"
    
    # 제어 흐름
    BASE_CASE = "base_case"
    RECURSIVE_CALL = "recursive_call"
    LOOP_STRUCTURE = "loop_structure"
    CONDITIONAL = "conditional"
    
    # 최적화 기법
    MEMOIZATION = "memoization"
    MEMOIZATION_CHECK = "memoization_check"
    MEMOIZATION_STORE = "memoization_store"
    
    # 비트 연산
    BIT_OPERATION = "bit_operation"
    BIT_AND = "bit_and"
    BIT_OR = "bit_or"
    BIT_SHIFT = "bit_shift"
    BIT_XOR = "bit_xor"
    
    # DP 관련
    STATE_TRANSITION = "state_transition"
    DP_ARRAY_INIT = "dp_array_init"
    DP_UPDATE = "dp_update"
    
    # 입출력
    INPUT_PROCESSING = "input_processing"
    OUTPUT_PROCESSING = "output_processing"
    
    # 자료구조
    DATA_STRUCTURE_INIT = "data_structure_init"
    ARRAY_ACCESS = "array_access"
    
    # 기타
    VARIABLE_DECLARATION = "variable_declaration"
    IMPORT_STATEMENT = "import_statement"
    DECORATOR = "decorator"
    UNKNOWN = "unknown"


@dataclass
class CodeComponent:
    """
    코드 구성 요소
    
    AST 분석에서 식별된 개별 코드 구성 요소를 나타냅니다.
    """
    
    component_type: ComponentType
    """구성 요소 유형"""
    
    start_line: int
    """시작 라인 번호 (1-based)"""
    
    end_line: int
    """종료 라인 번호 (1-based)"""
    
    code_snippet: str
    """코드 스니펫"""
    
    description: str = ""
    """구성 요소 설명"""
    
    ast_node_type: str = ""
    """AST 노드 타입 (예: FunctionDef, If, For)"""
    
    related_specs: List[str] = field(default_factory=list)
    """관련 Spec 카테고리 목록"""
    
    children: List["CodeComponent"] = field(default_factory=list)
    """하위 구성 요소들"""
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    """추가 메타데이터"""
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "component_type": self.component_type.value,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "code_snippet": self.code_snippet,
            "description": self.description,
            "ast_node_type": self.ast_node_type,
            "related_specs": self.related_specs,
            "children": [child.to_dict() for child in self.children],
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CodeComponent":
        """딕셔너리에서 생성"""
        return cls(
            component_type=ComponentType(data["component_type"]),
            start_line=data["start_line"],
            end_line=data["end_line"],
            code_snippet=data["code_snippet"],
            description=data.get("description", ""),
            ast_node_type=data.get("ast_node_type", ""),
            related_specs=data.get("related_specs", []),
            children=[cls.from_dict(c) for c in data.get("children", [])],
            metadata=data.get("metadata", {}),
        )
    
    def __repr__(self) -> str:
        return (
            f"CodeComponent("
            f"type={self.component_type.name}, "
            f"lines={self.start_line}-{self.end_line}, "
            f"snippet='{self.code_snippet[:50]}...')"
        )


# ===== 구성 요소 유형별 설명 =====

COMPONENT_DESCRIPTIONS = {
    ComponentType.FUNCTION_DEF: "함수 정의",
    ComponentType.MAIN_FUNCTION: "메인 함수 (핵심 로직)",
    ComponentType.HELPER_FUNCTION: "헬퍼 함수",
    ComponentType.BASE_CASE: "재귀의 기저 조건",
    ComponentType.RECURSIVE_CALL: "재귀 함수 호출",
    ComponentType.LOOP_STRUCTURE: "반복문 구조",
    ComponentType.CONDITIONAL: "조건문",
    ComponentType.MEMOIZATION: "메모이제이션 (캐싱)",
    ComponentType.MEMOIZATION_CHECK: "메모이제이션 조회",
    ComponentType.MEMOIZATION_STORE: "메모이제이션 저장",
    ComponentType.BIT_OPERATION: "비트 연산",
    ComponentType.BIT_AND: "비트 AND 연산",
    ComponentType.BIT_OR: "비트 OR 연산",
    ComponentType.BIT_SHIFT: "비트 시프트 연산",
    ComponentType.BIT_XOR: "비트 XOR 연산",
    ComponentType.STATE_TRANSITION: "상태 전이 (점화식)",
    ComponentType.DP_ARRAY_INIT: "DP 배열 초기화",
    ComponentType.DP_UPDATE: "DP 값 갱신",
    ComponentType.INPUT_PROCESSING: "입력 처리",
    ComponentType.OUTPUT_PROCESSING: "출력 처리",
    ComponentType.DATA_STRUCTURE_INIT: "자료구조 초기화",
    ComponentType.ARRAY_ACCESS: "배열 접근",
    ComponentType.VARIABLE_DECLARATION: "변수 선언",
    ComponentType.IMPORT_STATEMENT: "import 문",
    ComponentType.DECORATOR: "데코레이터",
    ComponentType.UNKNOWN: "알 수 없는 구성 요소",
}


# ===== Spec 카테고리 → 구성 요소 유형 매핑 =====

SPEC_TO_COMPONENT_MAPPING = {
    "기저조건": [ComponentType.BASE_CASE],
    "메모이제이션": [
        ComponentType.MEMOIZATION,
        ComponentType.MEMOIZATION_CHECK,
        ComponentType.MEMOIZATION_STORE,
        ComponentType.DECORATOR,
    ],
    "비트마스킹": [
        ComponentType.BIT_OPERATION,
        ComponentType.BIT_AND,
        ComponentType.BIT_OR,
        ComponentType.BIT_SHIFT,
    ],
    "비트연산": [
        ComponentType.BIT_OPERATION,
        ComponentType.BIT_AND,
        ComponentType.BIT_OR,
        ComponentType.BIT_SHIFT,
    ],
    "점화식": [ComponentType.STATE_TRANSITION, ComponentType.DP_UPDATE],
    "상태정의": [ComponentType.STATE_TRANSITION, ComponentType.DP_ARRAY_INIT],
    "시간복잡도": [ComponentType.LOOP_STRUCTURE, ComponentType.RECURSIVE_CALL],
    "재귀호출": [ComponentType.RECURSIVE_CALL],
    "외판원순회전략": [ComponentType.MAIN_FUNCTION, ComponentType.FUNCTION_DEF],
    "비트마스킹DP": [
        ComponentType.BIT_OPERATION,
        ComponentType.MEMOIZATION,
        ComponentType.STATE_TRANSITION,
    ],
    "출발점복귀": [ComponentType.BASE_CASE, ComponentType.CONDITIONAL],
}
