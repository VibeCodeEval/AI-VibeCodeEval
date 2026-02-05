"""
AST Analyzer - 정답 코드 구조 분석기

[Phase 6-a Task 6a-2]
Python의 ast 모듈을 사용하여 정답 코드를 분석하고
코드 구성 요소를 식별합니다.

[분석 대상]
- 함수 정의 및 구조
- 기저 조건 (Base Case)
- 재귀 호출
- 메모이제이션 패턴
- 비트 연산
- 루프 구조
- 상태 전이 (점화식)
"""

import ast
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from app.domain.langgraph.ast_injector.components import (
    CodeComponent,
    ComponentType,
)

logger = logging.getLogger(__name__)


@dataclass
class ASTAnalysisResult:
    """AST 분석 결과"""
    
    components: List[CodeComponent]
    """식별된 코드 구성 요소 목록"""
    
    functions: Dict[str, CodeComponent]
    """함수명 → 함수 컴포넌트 매핑"""
    
    main_function: Optional[str]
    """메인 함수명 (핵심 로직이 있는 함수)"""
    
    has_memoization: bool
    """메모이제이션 사용 여부"""
    
    has_bit_operations: bool
    """비트 연산 사용 여부"""
    
    has_recursion: bool
    """재귀 사용 여부"""
    
    analysis_summary: str
    """분석 요약"""
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "components": [c.to_dict() for c in self.components],
            "functions": {k: v.to_dict() for k, v in self.functions.items()},
            "main_function": self.main_function,
            "has_memoization": self.has_memoization,
            "has_bit_operations": self.has_bit_operations,
            "has_recursion": self.has_recursion,
            "analysis_summary": self.analysis_summary,
        }


class ASTAnalyzer(ast.NodeVisitor):
    """
    AST 분석기
    
    Python 코드를 AST로 파싱하고 구성 요소를 식별합니다.
    """
    
    def __init__(self, source_code: str):
        """
        Args:
            source_code: 분석할 Python 소스 코드
        """
        self.source_code = source_code
        self.lines = source_code.split("\n")
        self.components: List[CodeComponent] = []
        self.functions: Dict[str, CodeComponent] = {}
        self.current_function: Optional[str] = None
        self.recursive_functions: Set[str] = set()
        self.function_calls: Dict[str, Set[str]] = {}  # 함수 내에서 호출하는 함수들
        self.decorators: Dict[str, List[str]] = {}  # 함수별 데코레이터
        
    def analyze(self) -> ASTAnalysisResult:
        """
        소스 코드를 분석하고 결과를 반환합니다.
        
        Returns:
            ASTAnalysisResult: 분석 결과
        """
        try:
            tree = ast.parse(self.source_code)
            self.visit(tree)
            
            # 재귀 함수 식별
            self._identify_recursive_functions()
            
            # 메인 함수 식별
            main_function = self._identify_main_function()
            
            # 분석 요약 생성
            summary = self._generate_summary()
            
            return ASTAnalysisResult(
                components=self.components,
                functions=self.functions,
                main_function=main_function,
                has_memoization=self._has_memoization(),
                has_bit_operations=self._has_bit_operations(),
                has_recursion=len(self.recursive_functions) > 0,
                analysis_summary=summary,
            )
            
        except SyntaxError as e:
            logger.error(f"[AST Analyzer] 구문 오류: {e}")
            return ASTAnalysisResult(
                components=[],
                functions={},
                main_function=None,
                has_memoization=False,
                has_bit_operations=False,
                has_recursion=False,
                analysis_summary=f"구문 오류로 분석 실패: {e}",
            )
    
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """함수 정의 방문"""
        func_name = node.name
        self.current_function = func_name
        self.function_calls[func_name] = set()
        
        # 데코레이터 추출
        decorators = [self._get_decorator_name(d) for d in node.decorator_list]
        self.decorators[func_name] = decorators
        
        # 코드 스니펫 추출
        start_line = node.lineno
        end_line = node.end_lineno or start_line
        code_snippet = self._get_code_snippet(start_line, end_line)
        
        # 컴포넌트 타입 결정
        comp_type = ComponentType.FUNCTION_DEF
        if func_name in ["main", "solve", "solution"]:
            comp_type = ComponentType.MAIN_FUNCTION
        
        # 데코레이터 컴포넌트 생성
        for i, decorator in enumerate(node.decorator_list):
            dec_name = self._get_decorator_name(decorator)
            if "cache" in dec_name.lower() or "memo" in dec_name.lower():
                dec_comp = CodeComponent(
                    component_type=ComponentType.DECORATOR,
                    start_line=decorator.lineno,
                    end_line=decorator.end_lineno or decorator.lineno,
                    code_snippet=f"@{dec_name}",
                    description=f"메모이제이션 데코레이터: @{dec_name}",
                    ast_node_type="Decorator",
                    related_specs=["메모이제이션"],
                    metadata={"decorator_name": dec_name, "function": func_name},
                )
                self.components.append(dec_comp)
        
        # 함수 컴포넌트 생성
        func_component = CodeComponent(
            component_type=comp_type,
            start_line=start_line,
            end_line=end_line,
            code_snippet=code_snippet,
            description=f"함수 정의: {func_name}",
            ast_node_type="FunctionDef",
            related_specs=[],
            metadata={
                "name": func_name,
                "args": [arg.arg for arg in node.args.args],
                "decorators": decorators,
            },
        )
        
        # 함수 본문 분석
        children = []
        for child_node in ast.walk(node):
            child_comp = self._analyze_node(child_node, func_name)
            if child_comp:
                children.append(child_comp)
        
        func_component.children = children
        self.components.append(func_component)
        self.functions[func_name] = func_component
        
        # 자식 노드 방문
        self.generic_visit(node)
        self.current_function = None
    
    def visit_Call(self, node: ast.Call) -> None:
        """함수 호출 방문"""
        if self.current_function:
            call_name = self._get_call_name(node)
            if call_name:
                self.function_calls[self.current_function].add(call_name)
        
        self.generic_visit(node)
    
    def _analyze_node(
        self, node: ast.AST, func_name: str
    ) -> Optional[CodeComponent]:
        """
        개별 AST 노드를 분석하여 컴포넌트 생성
        
        Args:
            node: AST 노드
            func_name: 현재 함수명
            
        Returns:
            CodeComponent 또는 None
        """
        if not hasattr(node, "lineno"):
            return None
        
        start_line = node.lineno
        end_line = getattr(node, "end_lineno", start_line) or start_line
        code_snippet = self._get_code_snippet(start_line, end_line)
        
        # If 문 분석 (기저 조건 식별)
        if isinstance(node, ast.If):
            if self._is_base_case(node, func_name):
                return CodeComponent(
                    component_type=ComponentType.BASE_CASE,
                    start_line=start_line,
                    end_line=end_line,
                    code_snippet=code_snippet,
                    description="기저 조건 (Base Case)",
                    ast_node_type="If",
                    related_specs=["기저조건"],
                    metadata={"function": func_name, "condition": ast.dump(node.test)},
                )
        
        # 비트 연산 분석
        if isinstance(node, ast.BinOp):
            bit_type = self._get_bit_operation_type(node)
            if bit_type:
                return CodeComponent(
                    component_type=bit_type,
                    start_line=start_line,
                    end_line=end_line,
                    code_snippet=code_snippet,
                    description=f"비트 연산: {bit_type.name}",
                    ast_node_type="BinOp",
                    related_specs=["비트마스킹", "비트연산"],
                    metadata={"function": func_name, "operation": type(node.op).__name__},
                )
        
        # For/While 루프 분석
        if isinstance(node, (ast.For, ast.While)):
            return CodeComponent(
                component_type=ComponentType.LOOP_STRUCTURE,
                start_line=start_line,
                end_line=end_line,
                code_snippet=code_snippet,
                description=f"루프 구조: {type(node).__name__}",
                ast_node_type=type(node).__name__,
                related_specs=["시간복잡도"],
                metadata={"function": func_name, "loop_type": type(node).__name__},
            )
        
        # DP 배열 초기화 분석
        if isinstance(node, ast.Assign):
            if self._is_dp_array_init(node):
                return CodeComponent(
                    component_type=ComponentType.DP_ARRAY_INIT,
                    start_line=start_line,
                    end_line=end_line,
                    code_snippet=code_snippet,
                    description="DP 배열 초기화",
                    ast_node_type="Assign",
                    related_specs=["상태정의", "메모이제이션"],
                    metadata={"function": func_name},
                )
        
        # min/max 함수 호출 (상태 전이 가능성)
        if isinstance(node, ast.Call):
            call_name = self._get_call_name(node)
            if call_name in ["min", "max"]:
                # 재귀 호출을 포함하는 min/max는 상태 전이
                if self._contains_recursive_call(node, func_name):
                    return CodeComponent(
                        component_type=ComponentType.STATE_TRANSITION,
                        start_line=start_line,
                        end_line=end_line,
                        code_snippet=code_snippet,
                        description=f"상태 전이 (점화식): {call_name}",
                        ast_node_type="Call",
                        related_specs=["점화식", "상태정의"],
                        metadata={"function": func_name, "operation": call_name},
                    )
        
        return None
    
    def _is_base_case(self, node: ast.If, func_name: str) -> bool:
        """
        If 노드가 기저 조건인지 판별
        
        기저 조건의 특징:
        - return 문을 직접 포함
        - 재귀 호출 없음
        - 조건이 종료 조건을 나타냄 (==, <, <=)
        """
        # return 문 존재 확인
        has_return = any(isinstance(n, ast.Return) for n in ast.walk(node))
        if not has_return:
            return False
        
        # body에 재귀 호출이 없는지 확인
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._get_call_name(child)
                if call_name == func_name:
                    return False
        
        # 조건 패턴 분석 (비트마스크 완료 체크 등)
        condition_str = ast.dump(node.test)
        base_case_patterns = [
            "visited == ",
            "mask == ",
            "n == 0",
            "n <= 0",
            "len(",
            "not ",
        ]
        
        return any(pattern in condition_str.lower() for pattern in base_case_patterns)
    
    def _get_bit_operation_type(self, node: ast.BinOp) -> Optional[ComponentType]:
        """비트 연산 타입 식별"""
        op = node.op
        
        if isinstance(op, ast.BitAnd):
            return ComponentType.BIT_AND
        elif isinstance(op, ast.BitOr):
            return ComponentType.BIT_OR
        elif isinstance(op, ast.LShift) or isinstance(op, ast.RShift):
            return ComponentType.BIT_SHIFT
        elif isinstance(op, ast.BitXor):
            return ComponentType.BIT_XOR
        
        return None
    
    def _is_dp_array_init(self, node: ast.Assign) -> bool:
        """DP 배열 초기화인지 판별"""
        # 변수명 패턴 체크
        for target in node.targets:
            if isinstance(target, ast.Name):
                name_lower = target.id.lower()
                if any(pattern in name_lower for pattern in ["dp", "memo", "cache", "visited"]):
                    return True
        
        # 리스트 컴프리헨션 또는 다차원 배열 초기화 패턴
        if isinstance(node.value, ast.ListComp):
            return True
        
        return False
    
    def _contains_recursive_call(self, node: ast.AST, func_name: str) -> bool:
        """노드 내에 재귀 호출이 있는지 확인"""
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                call_name = self._get_call_name(child)
                if call_name == func_name:
                    return True
        return False
    
    def _get_call_name(self, node: ast.Call) -> Optional[str]:
        """함수 호출에서 함수명 추출"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return node.func.attr
        return None
    
    def _get_decorator_name(self, node: ast.expr) -> str:
        """데코레이터 이름 추출"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        elif isinstance(node, ast.Call):
            return self._get_call_name(node) or "unknown"
        return "unknown"
    
    def _get_code_snippet(self, start_line: int, end_line: int) -> str:
        """라인 번호로 코드 스니펫 추출 (1-based)"""
        start_idx = max(0, start_line - 1)
        end_idx = min(len(self.lines), end_line)
        return "\n".join(self.lines[start_idx:end_idx])
    
    def _identify_recursive_functions(self) -> None:
        """재귀 함수 식별"""
        for func_name, calls in self.function_calls.items():
            if func_name in calls:
                self.recursive_functions.add(func_name)
                
                # 재귀 호출 컴포넌트 추가
                if func_name in self.functions:
                    func_comp = self.functions[func_name]
                    rec_comp = CodeComponent(
                        component_type=ComponentType.RECURSIVE_CALL,
                        start_line=func_comp.start_line,
                        end_line=func_comp.end_line,
                        code_snippet=f"# 재귀 함수: {func_name}",
                        description=f"재귀 호출: {func_name}()",
                        ast_node_type="RecursiveCall",
                        related_specs=["재귀호출"],
                        metadata={"function": func_name},
                    )
                    self.components.append(rec_comp)
    
    def _identify_main_function(self) -> Optional[str]:
        """메인 함수 식별"""
        # 1. 명시적인 메인 함수 이름
        main_names = ["main", "solve", "solution", "tsp", "dfs", "bfs", "dp"]
        for name in main_names:
            if name in self.functions:
                return name
        
        # 2. 재귀 함수 우선
        if self.recursive_functions:
            return list(self.recursive_functions)[0]
        
        # 3. 첫 번째 함수
        if self.functions:
            return list(self.functions.keys())[0]
        
        return None
    
    def _has_memoization(self) -> bool:
        """메모이제이션 사용 여부 확인"""
        # 데코레이터 확인
        for func_name, decorators in self.decorators.items():
            for dec in decorators:
                if any(pattern in dec.lower() for pattern in ["cache", "memo", "lru"]):
                    return True
        
        # DP 배열 초기화 확인
        for comp in self.components:
            if comp.component_type in [
                ComponentType.DP_ARRAY_INIT,
                ComponentType.MEMOIZATION,
                ComponentType.MEMOIZATION_CHECK,
            ]:
                return True
        
        return False
    
    def _has_bit_operations(self) -> bool:
        """비트 연산 사용 여부 확인"""
        for comp in self.components:
            if comp.component_type in [
                ComponentType.BIT_OPERATION,
                ComponentType.BIT_AND,
                ComponentType.BIT_OR,
                ComponentType.BIT_SHIFT,
                ComponentType.BIT_XOR,
            ]:
                return True
        return False
    
    def _generate_summary(self) -> str:
        """분석 요약 생성"""
        parts = []
        
        # 함수 정보
        func_count = len(self.functions)
        parts.append(f"함수 {func_count}개 정의됨")
        
        if self.recursive_functions:
            parts.append(f"재귀 함수: {', '.join(self.recursive_functions)}")
        
        if self._has_memoization():
            parts.append("메모이제이션 사용")
        
        if self._has_bit_operations():
            parts.append("비트 연산 사용")
        
        # 컴포넌트 통계
        comp_types = {}
        for comp in self.components:
            comp_type = comp.component_type.value
            comp_types[comp_type] = comp_types.get(comp_type, 0) + 1
        
        parts.append(f"구성 요소: {len(self.components)}개")
        
        return " | ".join(parts)


# ===== 편의 함수 =====


def analyze_code(source_code: str) -> ASTAnalysisResult:
    """
    Python 소스 코드를 분석합니다.
    
    Args:
        source_code: 분석할 Python 소스 코드
        
    Returns:
        ASTAnalysisResult: 분석 결과
    """
    analyzer = ASTAnalyzer(source_code)
    return analyzer.analyze()


def get_components_by_type(
    result: ASTAnalysisResult,
    component_type: ComponentType
) -> List[CodeComponent]:
    """
    특정 타입의 컴포넌트만 필터링
    
    Args:
        result: AST 분석 결과
        component_type: 찾을 컴포넌트 타입
        
    Returns:
        해당 타입의 컴포넌트 목록
    """
    return [c for c in result.components if c.component_type == component_type]


def get_components_for_spec(
    result: ASTAnalysisResult,
    spec_category: str
) -> List[CodeComponent]:
    """
    특정 Spec 카테고리와 관련된 컴포넌트 조회
    
    Args:
        result: AST 분석 결과
        spec_category: Spec 카테고리명
        
    Returns:
        관련 컴포넌트 목록
    """
    from app.domain.langgraph.ast_injector.components import SPEC_TO_COMPONENT_MAPPING
    
    target_types = SPEC_TO_COMPONENT_MAPPING.get(spec_category, [])
    
    components = []
    for comp in result.components:
        if comp.component_type in target_types:
            components.append(comp)
        elif spec_category in comp.related_specs:
            components.append(comp)
    
    return components
