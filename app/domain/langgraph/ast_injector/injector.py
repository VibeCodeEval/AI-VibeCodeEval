"""
Error Injector - AST 기반 코드 변형 통합 모듈

[Phase 6-a Task 6a-4]
Spec Extractor, AST Analyzer, Spec-AST Mapper의 결과를 통합하여
의도적으로 불완전한 코드를 생성합니다.

[역할]
- 전체 변형 파이프라인 조율
- LLM을 사용한 변형 방식 결정
- 변형된 코드 생성 및 검증
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.domain.langgraph.ast_injector.analyzer import (
    ASTAnalysisResult,
    ASTAnalyzer,
    analyze_code,
)
from app.domain.langgraph.ast_injector.components import CodeComponent, ComponentType
from app.domain.langgraph.ast_injector.mapper import (
    MappingResult,
    SpecASTMapper,
    SpecASTMappingResult,
    map_specs_to_ast,
)
from app.domain.langgraph.ast_injector.modifier import (
    CodeModifier,
    ModificationResult,
    modify_code,
)
from app.domain.langgraph.ast_injector.strategies import (
    ModificationStrategy,
    ModificationType,
    get_strategies_for_component,
    select_best_strategy,
)
from app.domain.langgraph.states import MainGraphState

logger = logging.getLogger(__name__)


# ===== Pydantic 모델 (LLM 구조화 출력용) =====


class ModificationDecision(BaseModel):
    """LLM의 변형 결정"""
    
    component_type: str = Field(
        ...,
        description="변형할 컴포넌트 타입"
    )
    modification_type: str = Field(
        ...,
        description="적용할 변형 유형 (remove, simplify, incorrect, incomplete, replace, add_todo, pass_placeholder)"
    )
    reasoning: str = Field(
        ...,
        description="이 변형을 선택한 이유"
    )
    custom_replacement: Optional[str] = Field(
        None,
        description="커스텀 대체 코드 (선택사항)"
    )


class InjectionPlan(BaseModel):
    """변형 계획"""
    
    decisions: List[ModificationDecision] = Field(
        default_factory=list,
        description="변형 결정 목록"
    )
    overall_strategy: str = Field(
        "",
        description="전체 변형 전략 설명"
    )
    expected_difficulty: str = Field(
        "MEDIUM",
        description="예상 난이도 (EASY, MEDIUM, HARD)"
    )


@dataclass
class InjectionResult:
    """Error Injection 결과"""
    
    original_code: str
    """원본 정답 코드"""
    
    modified_code: str
    """변형된 코드"""
    
    spec_result: Dict[str, Any]
    """Spec 추출 결과"""
    
    ast_analysis: Dict[str, Any]
    """AST 분석 결과"""
    
    mapping_result: Dict[str, Any]
    """Spec-AST 매핑 결과"""
    
    modifications_applied: List[Dict[str, Any]]
    """적용된 변형 목록"""
    
    prompt_quality_score: float
    """프롬프트 품질 점수"""
    
    injection_summary: str
    """변형 요약"""
    
    success: bool
    """성공 여부"""
    
    error_message: Optional[str] = None
    """에러 메시지"""
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "original_code": self.original_code,
            "modified_code": self.modified_code,
            "spec_result": self.spec_result,
            "ast_analysis": self.ast_analysis,
            "mapping_result": self.mapping_result,
            "modifications_applied": self.modifications_applied,
            "prompt_quality_score": self.prompt_quality_score,
            "injection_summary": self.injection_summary,
            "success": self.success,
            "error_message": self.error_message,
        }


class ErrorInjector:
    """
    Error Injector
    
    누락된 Spec을 기반으로 의도적으로 불완전한 코드를 생성합니다.
    """
    
    def __init__(
        self,
        solution_code: str,
        spec_result: Dict[str, Any],
        problem_context: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            solution_code: 정답 코드
            spec_result: Spec Extractor의 결과
            problem_context: 문제 정보
        """
        self.solution_code = solution_code
        self.spec_result = spec_result
        self.problem_context = problem_context or {}
        
        # 분석 결과 초기화
        self.ast_result: Optional[ASTAnalysisResult] = None
        self.mapping_result: Optional[SpecASTMappingResult] = None
    
    def inject(self, max_modifications: int = 3) -> InjectionResult:
        """
        코드에 에러를 주입합니다.
        
        Args:
            max_modifications: 최대 변형 수
            
        Returns:
            InjectionResult: 변형 결과
        """
        try:
            # 1. AST 분석
            logger.info("[Error Injector] AST 분석 시작")
            self.ast_result = analyze_code(self.solution_code)
            logger.info(f"[Error Injector] AST 분석 완료: {self.ast_result.analysis_summary}")
            
            # 2. Spec-AST 매핑
            missing_specs = self.spec_result.get("missing_requirements", [])
            
            if not missing_specs:
                # 누락된 Spec이 없으면 원본 코드 반환
                logger.info("[Error Injector] 누락된 Spec 없음, 원본 코드 반환")
                return self._create_no_modification_result()
            
            logger.info(f"[Error Injector] Spec-AST 매핑 시작: {len(missing_specs)}개 누락 Spec")
            self.mapping_result = map_specs_to_ast(self.ast_result, missing_specs)
            logger.info(f"[Error Injector] 매핑 완료: {self.mapping_result.summary}")
            
            # 3. 변형 계획 수립
            modification_plan = self._create_modification_plan(max_modifications)
            
            if not modification_plan:
                logger.info("[Error Injector] 변형 계획 없음, 원본 코드 반환")
                return self._create_no_modification_result()
            
            # 4. 코드 변형 적용
            logger.info(f"[Error Injector] 변형 적용 시작: {len(modification_plan)}개")
            modification_result = modify_code(self.solution_code, modification_plan)
            
            # 5. 결과 생성
            return InjectionResult(
                original_code=self.solution_code,
                modified_code=modification_result.modified_code,
                spec_result=self.spec_result,
                ast_analysis=self.ast_result.to_dict(),
                mapping_result=self.mapping_result.to_dict(),
                modifications_applied=modification_result.modifications,
                prompt_quality_score=self.spec_result.get("prompt_quality_score", 50.0),
                injection_summary=self._generate_summary(modification_result),
                success=True,
            )
            
        except Exception as e:
            logger.error(f"[Error Injector] 에러 발생: {e}", exc_info=True)
            return InjectionResult(
                original_code=self.solution_code,
                modified_code=self.solution_code,
                spec_result=self.spec_result,
                ast_analysis={},
                mapping_result={},
                modifications_applied=[],
                prompt_quality_score=self.spec_result.get("prompt_quality_score", 50.0),
                injection_summary=f"변형 실패: {str(e)}",
                success=False,
                error_message=str(e),
            )
    
    def _create_modification_plan(
        self,
        max_modifications: int,
    ) -> List[Tuple[CodeComponent, ModificationStrategy]]:
        """
        변형 계획을 수립합니다.
        
        Args:
            max_modifications: 최대 변형 수
            
        Returns:
            (컴포넌트, 전략) 튜플 목록
        """
        plan: List[Tuple[CodeComponent, ModificationStrategy]] = []
        
        if not self.mapping_result:
            return plan
        
        # 매핑된 것들 중 우선순위 높은 것부터 선택
        for mapping in self.mapping_result.mappings[:max_modifications]:
            if not mapping.matched_components:
                continue
            
            # 첫 번째 매칭 컴포넌트 선택
            component = mapping.matched_components[0]
            
            # 최적 전략 선택
            strategy = select_best_strategy(
                component.component_type,
                spec_importance=mapping.spec_importance,
            )
            
            if strategy:
                plan.append((component, strategy))
                logger.debug(
                    f"[Error Injector] 변형 계획 추가: "
                    f"{component.component_type.value} -> {strategy.modification_type.value}"
                )
        
        return plan
    
    def _create_no_modification_result(self) -> InjectionResult:
        """변형 없음 결과 생성"""
        return InjectionResult(
            original_code=self.solution_code,
            modified_code=self.solution_code,
            spec_result=self.spec_result,
            ast_analysis=self.ast_result.to_dict() if self.ast_result else {},
            mapping_result=self.mapping_result.to_dict() if self.mapping_result else {},
            modifications_applied=[],
            prompt_quality_score=self.spec_result.get("prompt_quality_score", 100.0),
            injection_summary="모든 Spec이 명시되어 변형 없이 정답 코드 제공",
            success=True,
        )
    
    def _generate_summary(self, modification_result: ModificationResult) -> str:
        """변형 요약 생성"""
        parts = []
        
        num_mods = len(modification_result.modifications)
        parts.append(f"{num_mods}개 변형 적용")
        
        # 변형 유형별 집계
        mod_types = {}
        for mod in modification_result.modifications:
            mod_type = mod.get("strategy", "unknown")
            mod_types[mod_type] = mod_types.get(mod_type, 0) + 1
        
        for mod_type, count in mod_types.items():
            parts.append(f"{mod_type}: {count}개")
        
        return " | ".join(parts)


# ===== 노드 함수 =====


async def error_injector(state: MainGraphState) -> Dict[str, Any]:
    """
    Error Injector 노드 함수
    
    Spec Extractor의 결과를 바탕으로 정답 코드를 변형합니다.
    
    Args:
        state: 메인 그래프 상태
        
    Returns:
        변형 결과를 포함한 상태 업데이트 딕셔너리
    """
    spec_result = state.get("spec_result")
    problem_context = state.get("problem_context", {})
    
    logger.info("[Error Injector] 시작")
    
    # 가드레일 위반 시 건너뛰기
    if state.get("is_guardrail_failed", False):
        logger.info("[Error Injector] 가드레일 위반으로 건너뜀")
        return {
            "ast_analysis": None,
            "modification_plan": None,
            "modified_code": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    # Spec 결과가 없으면 건너뛰기
    if not spec_result:
        logger.info("[Error Injector] Spec 결과 없음, 건너뜀")
        return {
            "ast_analysis": None,
            "modification_plan": None,
            "modified_code": None,
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    # 정답 코드 가져오기
    solution_code = problem_context.get("solution_code", "")
    
    if not solution_code:
        logger.warning("[Error Injector] 정답 코드 없음")
        return {
            "ast_analysis": None,
            "modification_plan": None,
            "modified_code": None,
            "error_message": "정답 코드가 없습니다.",
            "updated_at": datetime.utcnow().isoformat(),
        }
    
    try:
        # Error Injection 실행
        injector = ErrorInjector(
            solution_code=solution_code,
            spec_result=spec_result,
            problem_context=problem_context,
        )
        
        result = injector.inject(max_modifications=3)
        
        logger.info(f"[Error Injector] 완료: {result.injection_summary}")
        
        return {
            "ast_analysis": result.ast_analysis,
            "modification_plan": result.mapping_result,
            "modified_code": result.modified_code,
            "injection_result": result.to_dict(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(f"[Error Injector] 에러: {e}", exc_info=True)
        return {
            "ast_analysis": None,
            "modification_plan": None,
            "modified_code": None,
            "error_message": f"Error Injection 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }


# ===== 편의 함수 =====


def inject_errors(
    solution_code: str,
    missing_specs: List[Dict[str, Any]],
    problem_context: Optional[Dict[str, Any]] = None,
    max_modifications: int = 3,
) -> InjectionResult:
    """
    정답 코드에 에러를 주입합니다.
    
    Args:
        solution_code: 정답 코드
        missing_specs: 누락된 Spec 목록
        problem_context: 문제 정보
        max_modifications: 최대 변형 수
        
    Returns:
        InjectionResult: 변형 결과
    """
    spec_result = {
        "missing_requirements": missing_specs,
        "prompt_quality_score": 50.0,
    }
    
    injector = ErrorInjector(
        solution_code=solution_code,
        spec_result=spec_result,
        problem_context=problem_context,
    )
    
    return injector.inject(max_modifications=max_modifications)
