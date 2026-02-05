"""
AST 노드 변형기

[Phase 6-a Task 6a-4]
AST 분석 결과와 변형 전략을 바탕으로 실제 코드를 변형합니다.

[역할]
- 원본 코드에서 특정 컴포넌트를 변형
- 변형 전략에 따른 코드 생성
- 변형 결과 추적 및 로깅
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.domain.langgraph.ast_injector.components import CodeComponent, ComponentType
from app.domain.langgraph.ast_injector.strategies import (
    ModificationStrategy,
    ModificationType,
)

logger = logging.getLogger(__name__)


@dataclass
class ModificationResult:
    """변형 결과"""
    
    original_code: str
    """원본 코드"""
    
    modified_code: str
    """변형된 코드"""
    
    modifications: List[Dict[str, Any]]
    """적용된 변형 목록"""
    
    success: bool
    """변형 성공 여부"""
    
    error_message: Optional[str] = None
    """에러 메시지 (실패 시)"""
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "original_code": self.original_code,
            "modified_code": self.modified_code,
            "modifications": self.modifications,
            "success": self.success,
            "error_message": self.error_message,
        }


class CodeModifier:
    """
    코드 변형기
    
    원본 코드에 변형 전략을 적용하여 의도적으로 불완전한 코드를 생성합니다.
    """
    
    def __init__(self, source_code: str):
        """
        Args:
            source_code: 변형할 원본 소스 코드
        """
        self.source_code = source_code
        self.lines = source_code.split("\n")
        self.modifications: List[Dict[str, Any]] = []
    
    def apply_modification(
        self,
        component: CodeComponent,
        strategy: ModificationStrategy,
    ) -> str:
        """
        단일 변형을 적용합니다.
        
        Args:
            component: 변형 대상 컴포넌트
            strategy: 적용할 변형 전략
            
        Returns:
            변형된 코드
        """
        start_line = component.start_line - 1  # 0-based
        end_line = component.end_line  # exclusive
        
        # 원본 코드 블록 추출
        original_block = "\n".join(self.lines[start_line:end_line])
        
        # 변형 유형에 따른 처리
        if strategy.modification_type == ModificationType.REMOVE:
            modified_block = self._apply_remove(component, strategy)
        elif strategy.modification_type == ModificationType.SIMPLIFY:
            modified_block = self._apply_simplify(component, strategy, original_block)
        elif strategy.modification_type == ModificationType.MAKE_INCORRECT:
            modified_block = self._apply_incorrect(component, strategy, original_block)
        elif strategy.modification_type == ModificationType.MAKE_INCOMPLETE:
            modified_block = self._apply_incomplete(component, strategy, original_block)
        elif strategy.modification_type == ModificationType.REPLACE_ALGORITHM:
            modified_block = self._apply_replace(component, strategy, original_block)
        elif strategy.modification_type == ModificationType.ADD_TODO:
            modified_block = self._apply_add_todo(component, strategy, original_block)
        elif strategy.modification_type == ModificationType.PASS_PLACEHOLDER:
            modified_block = self._apply_pass_placeholder(component, strategy)
        else:
            modified_block = original_block
        
        # 변형 적용
        new_lines = self.lines[:start_line] + modified_block.split("\n") + self.lines[end_line:]
        self.lines = new_lines
        
        # 변형 기록
        self.modifications.append({
            "component_type": component.component_type.value,
            "strategy": strategy.modification_type.value,
            "start_line": component.start_line,
            "end_line": component.end_line,
            "original": original_block,
            "modified": modified_block,
        })
        
        return "\n".join(self.lines)
    
    def _apply_remove(
        self,
        component: CodeComponent,
        strategy: ModificationStrategy,
    ) -> str:
        """코드 제거 변형"""
        indent = self._get_indent(component.start_line - 1)
        
        if component.component_type == ComponentType.DECORATOR:
            return ""  # 데코레이터는 완전 제거
        elif component.component_type == ComponentType.BASE_CASE:
            return f"{indent}# TODO: 기저 조건 구현 필요\n{indent}pass"
        else:
            return f"{indent}# TODO: {strategy.description}\n{indent}pass"
    
    def _apply_simplify(
        self,
        component: CodeComponent,
        strategy: ModificationStrategy,
        original: str,
    ) -> str:
        """단순화 변형"""
        indent = self._get_indent(component.start_line - 1)
        
        if component.component_type in [
            ComponentType.BIT_OPERATION,
            ComponentType.BIT_AND,
            ComponentType.BIT_OR,
            ComponentType.BIT_SHIFT,
        ]:
            # 비트 연산을 리스트로 대체
            simplified = original
            # visited & (1 << i) -> i in visited_set
            simplified = re.sub(
                r'(\w+)\s*&\s*\(\s*1\s*<<\s*(\w+)\s*\)',
                r'\2 in visited_set',
                simplified
            )
            # visited | (1 << i) -> visited_set.add(i)
            simplified = re.sub(
                r'(\w+)\s*\|\s*\(\s*1\s*<<\s*(\w+)\s*\)',
                r'visited_set | {{\2}}',
                simplified
            )
            return f"{indent}# 단순화됨 (비효율적)\n{simplified}"
        
        return f"{indent}# 단순화됨\n{original}"
    
    def _apply_incorrect(
        self,
        component: CodeComponent,
        strategy: ModificationStrategy,
        original: str,
    ) -> str:
        """잘못된 로직으로 변형"""
        indent = self._get_indent(component.start_line - 1)
        
        if component.component_type == ComponentType.STATE_TRANSITION:
            # min을 max로, 또는 + 를 - 로 변경
            incorrect = original.replace("min(", "max(")
            if incorrect == original:
                incorrect = original.replace("max(", "min(")
            return f"{indent}# 잘못된 로직 (의도적 오류)\n{incorrect}"
        
        elif component.component_type == ComponentType.BASE_CASE:
            # 반환값 변경
            incorrect = re.sub(r'return\s+(\d+)', r'return \1 + 1', original)
            if incorrect == original:
                incorrect = re.sub(r'return\s+(\w+)', r'return \1 - 1', original)
            return f"{indent}# 잘못된 반환값 (의도적 오류)\n{incorrect}"
        
        elif component.component_type == ComponentType.LOOP_STRUCTURE:
            # range 범위 변경
            incorrect = re.sub(r'range\((\w+)\)', r'range(\1 - 1)', original)
            return f"{indent}# 범위 오류 (의도적)\n{incorrect}"
        
        return f"{indent}# 의도적 오류 포함\n{original}"
    
    def _apply_incomplete(
        self,
        component: CodeComponent,
        strategy: ModificationStrategy,
        original: str,
    ) -> str:
        """불완전한 구현으로 변형"""
        indent = self._get_indent(component.start_line - 1)
        lines = original.split("\n")
        
        # 처음 절반만 유지
        half = max(1, len(lines) // 2)
        partial = "\n".join(lines[:half])
        
        return f"{partial}\n{indent}# TODO: 나머지 구현 필요\n{indent}pass"
    
    def _apply_replace(
        self,
        component: CodeComponent,
        strategy: ModificationStrategy,
        original: str,
    ) -> str:
        """알고리즘 대체 변형"""
        indent = self._get_indent(component.start_line - 1)
        
        if component.component_type in [
            ComponentType.BIT_OPERATION,
            ComponentType.BIT_AND,
            ComponentType.BIT_OR,
        ]:
            # 비트마스크를 집합으로 대체하는 코드 예시
            return f"""{indent}# 비트마스크 대신 집합 사용 (비효율적)
{indent}visited_set = set()
{indent}# TODO: 비트 연산을 집합 연산으로 변환 필요
{indent}# 원본: {original.strip().split(chr(10))[0]}"""
        
        return f"{indent}# 알고리즘 대체됨\n{original}"
    
    def _apply_add_todo(
        self,
        component: CodeComponent,
        strategy: ModificationStrategy,
        original: str,
    ) -> str:
        """TODO 주석 추가"""
        indent = self._get_indent(component.start_line - 1)
        
        desc = strategy.description or "구현 필요"
        
        # 첫 줄만 남기고 TODO 추가
        first_line = original.split("\n")[0] if original else ""
        
        return f"""{indent}# TODO: {desc}
{indent}# 힌트: {first_line.strip()}
{indent}pass"""
    
    def _apply_pass_placeholder(
        self,
        component: CodeComponent,
        strategy: ModificationStrategy,
    ) -> str:
        """pass placeholder로 대체"""
        indent = self._get_indent(component.start_line - 1)
        
        # 함수 시그니처 추출
        if component.component_type in [ComponentType.FUNCTION_DEF, ComponentType.MAIN_FUNCTION]:
            # 첫 줄 (함수 정의)만 유지
            first_line = component.code_snippet.split("\n")[0]
            func_name = component.metadata.get("name", "unknown")
            
            return f"""{first_line}
{indent}    \"\"\"
{indent}    TODO: {func_name} 함수 구현 필요
{indent}    \"\"\"
{indent}    pass"""
        
        return f"{indent}# TODO: 구현 필요\n{indent}pass"
    
    def _get_indent(self, line_idx: int) -> str:
        """라인의 들여쓰기 추출"""
        if 0 <= line_idx < len(self.lines):
            line = self.lines[line_idx]
            match = re.match(r'^(\s*)', line)
            if match:
                return match.group(1)
        return ""
    
    def get_result(self) -> ModificationResult:
        """변형 결과 반환"""
        modified_code = "\n".join(self.lines)
        
        return ModificationResult(
            original_code=self.source_code,
            modified_code=modified_code,
            modifications=self.modifications,
            success=True,
        )


def modify_code(
    source_code: str,
    modifications: List[Tuple[CodeComponent, ModificationStrategy]],
) -> ModificationResult:
    """
    여러 변형을 순차적으로 적용합니다.
    
    Args:
        source_code: 원본 소스 코드
        modifications: (컴포넌트, 전략) 튜플 목록
        
    Returns:
        ModificationResult: 변형 결과
    """
    modifier = CodeModifier(source_code)
    
    try:
        # 라인 번호가 높은 것부터 처리 (변형 시 라인 번호 변화 방지)
        sorted_modifications = sorted(
            modifications,
            key=lambda x: x[0].start_line,
            reverse=True,
        )
        
        for component, strategy in sorted_modifications:
            modifier.apply_modification(component, strategy)
        
        return modifier.get_result()
        
    except Exception as e:
        logger.error(f"[Code Modifier] 변형 중 오류: {e}", exc_info=True)
        return ModificationResult(
            original_code=source_code,
            modified_code=source_code,
            modifications=[],
            success=False,
            error_message=str(e),
        )
