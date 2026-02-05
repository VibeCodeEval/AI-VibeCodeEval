"""
Spec-AST Mapper - 누락된 Spec과 AST 구성 요소 매핑

[Phase 6-a Task 6a-3]
Spec Extractor에서 추출한 누락 Spec을 AST Analyzer의 결과와 매핑합니다.
이 매핑은 Error Injector가 어떤 코드 부분을 변형할지 결정하는 데 사용됩니다.

[매핑 테이블]
- 기저조건 → BASE_CASE
- 메모이제이션 → MEMOIZATION, DECORATOR
- 비트마스킹 → BIT_OPERATION
- 점화식 → STATE_TRANSITION
- 시간복잡도 → LOOP_STRUCTURE, RECURSIVE_CALL
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.domain.langgraph.ast_injector.analyzer import ASTAnalysisResult
from app.domain.langgraph.ast_injector.components import (
    CodeComponent,
    ComponentType,
    SPEC_TO_COMPONENT_MAPPING,
)

logger = logging.getLogger(__name__)


# ===== 확장된 Spec-AST 매핑 테이블 =====

SPEC_MAPPING_TABLE = {
    # 알고리즘 기법
    "기저조건": {
        "component_types": [ComponentType.BASE_CASE],
        "priority": 1,
        "description": "재귀 함수의 종료 조건",
        "modification_hint": "기저 조건을 제거하거나 불완전하게 만들기",
    },
    "메모이제이션": {
        "component_types": [
            ComponentType.MEMOIZATION,
            ComponentType.MEMOIZATION_CHECK,
            ComponentType.MEMOIZATION_STORE,
            ComponentType.DECORATOR,
            ComponentType.DP_ARRAY_INIT,
        ],
        "priority": 2,
        "description": "계산 결과를 저장하여 중복 계산 방지",
        "modification_hint": "메모이제이션 로직 제거 또는 데코레이터 삭제",
    },
    "비트마스킹": {
        "component_types": [
            ComponentType.BIT_OPERATION,
            ComponentType.BIT_AND,
            ComponentType.BIT_OR,
            ComponentType.BIT_SHIFT,
        ],
        "priority": 2,
        "description": "비트 연산을 통한 상태 표현",
        "modification_hint": "비트 연산을 리스트/집합으로 대체 (비효율적)",
    },
    "비트연산": {
        "component_types": [
            ComponentType.BIT_OPERATION,
            ComponentType.BIT_AND,
            ComponentType.BIT_OR,
            ComponentType.BIT_SHIFT,
        ],
        "priority": 2,
        "description": "비트 연산자 사용",
        "modification_hint": "비트 연산을 일반 연산으로 대체",
    },
    "점화식": {
        "component_types": [
            ComponentType.STATE_TRANSITION,
            ComponentType.DP_UPDATE,
        ],
        "priority": 1,
        "description": "DP 상태 전이 수식",
        "modification_hint": "점화식 로직을 단순화하거나 잘못된 로직으로 변경",
    },
    "상태정의": {
        "component_types": [
            ComponentType.STATE_TRANSITION,
            ComponentType.DP_ARRAY_INIT,
            ComponentType.FUNCTION_DEF,
        ],
        "priority": 1,
        "description": "DP 상태의 정의",
        "modification_hint": "상태 변수를 불완전하게 정의",
    },
    "시간복잡도": {
        "component_types": [
            ComponentType.LOOP_STRUCTURE,
            ComponentType.RECURSIVE_CALL,
        ],
        "priority": 3,
        "description": "알고리즘의 시간 복잡도",
        "modification_hint": "비효율적인 중첩 루프로 변경",
    },
    "재귀호출": {
        "component_types": [ComponentType.RECURSIVE_CALL],
        "priority": 2,
        "description": "재귀 함수 호출",
        "modification_hint": "재귀 로직을 반복문으로 변경 (불완전하게)",
    },
    "외판원순회전략": {
        "component_types": [
            ComponentType.MAIN_FUNCTION,
            ComponentType.FUNCTION_DEF,
        ],
        "priority": 1,
        "description": "TSP 문제 해결 전략",
        "modification_hint": "그리디 접근으로 단순화",
    },
    "비트마스킹DP": {
        "component_types": [
            ComponentType.BIT_OPERATION,
            ComponentType.MEMOIZATION,
            ComponentType.STATE_TRANSITION,
        ],
        "priority": 1,
        "description": "비트마스킹과 DP를 결합한 기법",
        "modification_hint": "비트마스크 대신 집합 사용 (메모리 비효율)",
    },
    "출발점복귀": {
        "component_types": [
            ComponentType.BASE_CASE,
            ComponentType.CONDITIONAL,
        ],
        "priority": 2,
        "description": "출발점으로 돌아오는 조건 처리",
        "modification_hint": "복귀 조건 누락",
    },
    "방문체크": {
        "component_types": [
            ComponentType.CONDITIONAL,
            ComponentType.DATA_STRUCTURE_INIT,
        ],
        "priority": 2,
        "description": "방문 여부 확인",
        "modification_hint": "방문 체크 로직 불완전하게 만들기",
    },
    "큐자료구조": {
        "component_types": [
            ComponentType.DATA_STRUCTURE_INIT,
            ComponentType.IMPORT_STATEMENT,
        ],
        "priority": 2,
        "description": "BFS용 큐 자료구조",
        "modification_hint": "큐 대신 리스트 사용 (비효율)",
    },
}


@dataclass
class MappingResult:
    """
    Spec-AST 매핑 결과
    
    누락된 Spec과 해당하는 AST 컴포넌트를 매핑한 결과입니다.
    """
    
    spec_category: str
    """Spec 카테고리"""
    
    spec_description: str
    """Spec 설명"""
    
    spec_importance: str
    """Spec 중요도 (HIGH, MEDIUM, LOW)"""
    
    matched_components: List[CodeComponent]
    """매칭된 AST 컴포넌트 목록"""
    
    modification_hint: str
    """변형 힌트"""
    
    priority: int
    """우선순위 (낮을수록 높은 우선순위)"""
    
    confidence: float = 1.0
    """매칭 신뢰도 (0.0 - 1.0)"""
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "spec_category": self.spec_category,
            "spec_description": self.spec_description,
            "spec_importance": self.spec_importance,
            "matched_components": [c.to_dict() for c in self.matched_components],
            "modification_hint": self.modification_hint,
            "priority": self.priority,
            "confidence": self.confidence,
        }


@dataclass
class SpecASTMappingResult:
    """
    전체 Spec-AST 매핑 결과
    """
    
    mappings: List[MappingResult]
    """개별 매핑 결과 목록"""
    
    unmapped_specs: List[str]
    """매핑되지 않은 Spec 목록"""
    
    total_modifications_needed: int
    """필요한 총 변형 수"""
    
    summary: str
    """매핑 요약"""
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "mappings": [m.to_dict() for m in self.mappings],
            "unmapped_specs": self.unmapped_specs,
            "total_modifications_needed": self.total_modifications_needed,
            "summary": self.summary,
        }


class SpecASTMapper:
    """
    Spec-AST 매퍼
    
    누락된 Spec을 AST 분석 결과와 매핑합니다.
    """
    
    def __init__(
        self,
        ast_result: ASTAnalysisResult,
        missing_specs: List[Dict[str, Any]],
    ):
        """
        Args:
            ast_result: AST 분석 결과
            missing_specs: 누락된 Spec 목록 (SpecExtractor의 결과)
        """
        self.ast_result = ast_result
        self.missing_specs = missing_specs
    
    def map(self) -> SpecASTMappingResult:
        """
        누락된 Spec을 AST 컴포넌트와 매핑합니다.
        
        Returns:
            SpecASTMappingResult: 매핑 결과
        """
        mappings: List[MappingResult] = []
        unmapped_specs: List[str] = []
        
        for spec in self.missing_specs:
            category = spec.get("category", "")
            description = spec.get("description", "")
            importance = spec.get("importance", "MEDIUM")
            related_component = spec.get("related_component")
            
            # 매핑 테이블에서 조회
            mapping_info = SPEC_MAPPING_TABLE.get(category)
            
            if not mapping_info:
                # 유사한 카테고리 찾기
                mapping_info = self._find_similar_mapping(category)
            
            if mapping_info:
                # 해당 타입의 컴포넌트 찾기
                matched_components = self._find_components(
                    mapping_info["component_types"],
                    related_component,
                )
                
                mapping_result = MappingResult(
                    spec_category=category,
                    spec_description=description,
                    spec_importance=importance,
                    matched_components=matched_components,
                    modification_hint=mapping_info["modification_hint"],
                    priority=mapping_info["priority"],
                    confidence=1.0 if matched_components else 0.5,
                )
                mappings.append(mapping_result)
            else:
                unmapped_specs.append(category)
                logger.warning(f"[Spec-AST Mapper] 매핑 불가: {category}")
        
        # 우선순위별 정렬
        mappings.sort(key=lambda m: (m.priority, -len(m.matched_components)))
        
        # 요약 생성
        summary = self._generate_summary(mappings, unmapped_specs)
        
        return SpecASTMappingResult(
            mappings=mappings,
            unmapped_specs=unmapped_specs,
            total_modifications_needed=len(mappings),
            summary=summary,
        )
    
    def _find_components(
        self,
        component_types: List[ComponentType],
        related_component: Optional[str] = None,
    ) -> List[CodeComponent]:
        """
        지정된 타입의 컴포넌트를 찾습니다.
        
        Args:
            component_types: 찾을 컴포넌트 타입 목록
            related_component: 관련 컴포넌트 이름 (힌트)
            
        Returns:
            매칭된 컴포넌트 목록
        """
        matched = []
        
        for component in self.ast_result.components:
            # 타입 매칭
            if component.component_type in component_types:
                matched.append(component)
            # 관련 컴포넌트 이름으로 추가 매칭
            elif related_component:
                try:
                    related_type = ComponentType(related_component)
                    if component.component_type == related_type:
                        matched.append(component)
                except ValueError:
                    pass
        
        # 자식 컴포넌트에서도 검색
        for func_name, func_comp in self.ast_result.functions.items():
            for child in func_comp.children:
                if child.component_type in component_types and child not in matched:
                    matched.append(child)
        
        return matched
    
    def _find_similar_mapping(
        self, category: str
    ) -> Optional[Dict[str, Any]]:
        """
        유사한 카테고리 매핑을 찾습니다.
        
        Args:
            category: 카테고리명
            
        Returns:
            유사한 매핑 정보 또는 None
        """
        category_lower = category.lower()
        
        # 유사 키워드 매핑
        similarity_map = {
            "기저": "기저조건",
            "base": "기저조건",
            "memo": "메모이제이션",
            "cache": "메모이제이션",
            "bit": "비트마스킹",
            "비트": "비트마스킹",
            "점화": "점화식",
            "transition": "점화식",
            "recurrence": "점화식",
            "state": "상태정의",
            "상태": "상태정의",
            "복잡도": "시간복잡도",
            "complexity": "시간복잡도",
            "재귀": "재귀호출",
            "recursive": "재귀호출",
            "tsp": "외판원순회전략",
            "외판원": "외판원순회전략",
        }
        
        for keyword, mapped_category in similarity_map.items():
            if keyword in category_lower:
                return SPEC_MAPPING_TABLE.get(mapped_category)
        
        return None
    
    def _generate_summary(
        self,
        mappings: List[MappingResult],
        unmapped_specs: List[str],
    ) -> str:
        """매핑 요약 생성"""
        parts = []
        
        if mappings:
            high_priority = [m for m in mappings if m.spec_importance == "HIGH"]
            medium_priority = [m for m in mappings if m.spec_importance == "MEDIUM"]
            
            parts.append(f"총 {len(mappings)}개 Spec 매핑 완료")
            
            if high_priority:
                parts.append(f"HIGH 중요도: {len(high_priority)}개")
            if medium_priority:
                parts.append(f"MEDIUM 중요도: {len(medium_priority)}개")
        
        if unmapped_specs:
            parts.append(f"매핑 실패: {len(unmapped_specs)}개")
        
        total_components = sum(len(m.matched_components) for m in mappings)
        parts.append(f"변형 대상 컴포넌트: {total_components}개")
        
        return " | ".join(parts)


# ===== 편의 함수 =====


def map_specs_to_ast(
    ast_result: ASTAnalysisResult,
    missing_specs: List[Dict[str, Any]],
) -> SpecASTMappingResult:
    """
    누락된 Spec을 AST 컴포넌트와 매핑합니다.
    
    Args:
        ast_result: AST 분석 결과
        missing_specs: 누락된 Spec 목록
        
    Returns:
        SpecASTMappingResult: 매핑 결과
    """
    mapper = SpecASTMapper(ast_result, missing_specs)
    return mapper.map()


def get_modification_plan(
    mapping_result: SpecASTMappingResult,
    max_modifications: int = 3,
) -> List[Dict[str, Any]]:
    """
    매핑 결과에서 변형 계획을 생성합니다.
    
    Args:
        mapping_result: Spec-AST 매핑 결과
        max_modifications: 최대 변형 수
        
    Returns:
        변형 계획 목록
    """
    plan = []
    
    # 우선순위가 높은 것부터 선택
    for mapping in mapping_result.mappings[:max_modifications]:
        if mapping.matched_components:
            # 첫 번째 매칭 컴포넌트 선택
            target_component = mapping.matched_components[0]
            
            plan.append({
                "spec_category": mapping.spec_category,
                "spec_importance": mapping.spec_importance,
                "target_component": target_component.to_dict(),
                "modification_hint": mapping.modification_hint,
                "priority": mapping.priority,
            })
    
    return plan
