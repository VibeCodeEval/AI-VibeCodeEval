"""
AST Injector 모듈

[Phase 6-a]
AST 기반 코드 분석 및 변형 시스템

[구성 요소]
- components.py: 코드 구성 요소 타입 정의
- analyzer.py: AST 분석기 (정답 코드 → 구성 요소)
- mapper.py: Spec-AST 매퍼 (누락 Spec → AST 노드)
- strategies.py: 변형 전략 정의
- modifier.py: AST 노드 변형기
- injector.py: Error Injector 통합 모듈
"""

from app.domain.langgraph.ast_injector.components import (
    CodeComponent,
    ComponentType,
    SPEC_TO_COMPONENT_MAPPING,
)
from app.domain.langgraph.ast_injector.analyzer import (
    ASTAnalyzer,
    ASTAnalysisResult,
    analyze_code,
    get_components_by_type,
    get_components_for_spec,
)
from app.domain.langgraph.ast_injector.mapper import (
    SpecASTMapper,
    SpecASTMappingResult,
    MappingResult,
    map_specs_to_ast,
    get_modification_plan,
)
from app.domain.langgraph.ast_injector.strategies import (
    ModificationType,
    ModificationStrategy,
    get_strategies_for_component,
    select_best_strategy,
)
from app.domain.langgraph.ast_injector.modifier import (
    CodeModifier,
    ModificationResult,
    modify_code,
)
from app.domain.langgraph.ast_injector.injector import (
    ErrorInjector,
    InjectionResult,
    error_injector,
    inject_errors,
)

__all__ = [
    # Components
    "CodeComponent",
    "ComponentType",
    "SPEC_TO_COMPONENT_MAPPING",
    # Analyzer
    "ASTAnalyzer",
    "ASTAnalysisResult",
    "analyze_code",
    "get_components_by_type",
    "get_components_for_spec",
    # Mapper
    "SpecASTMapper",
    "SpecASTMappingResult",
    "MappingResult",
    "map_specs_to_ast",
    "get_modification_plan",
    # Strategies
    "ModificationType",
    "ModificationStrategy",
    "get_strategies_for_component",
    "select_best_strategy",
    # Modifier
    "CodeModifier",
    "ModificationResult",
    "modify_code",
    # Injector
    "ErrorInjector",
    "InjectionResult",
    "error_injector",
    "inject_errors",
]
