"""
V2.1 Step 04: 코드 품질 분석 유틸

- Radon CC: 함수별 순환 복잡도(Cyclomatic Complexity). 10 초과 시 주니어급 플래그.
- AST 패턴 검사: SecurityRule → BaseRule 상속, GateManager 전략 패턴 유지 (스마트 게이트 2026).
"""

import ast
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Step 04: 주니어급 플래그 임계치 (Radon CC)
JUNIOR_CC_THRESHOLD = 10


def compute_radon_cc(code: str) -> Dict[str, Any]:
    """
    Radon으로 함수·메서드별 순환 복잡도(CC) 계산.

    Args:
        code: Python 소스 코드 문자열

    Returns:
        {
            "functions": [{"name": str, "complexity": int}, ...],
            "max_cc": int,
            "avg_cc": float,
            "junior_grade": bool,  # any CC > 10
        }
    """
    try:
        from radon.complexity import cc_visit
    except ImportError:
        logger.warning("[code_quality] radon 미설치 - CC 계산 스킵")
        return {
            "functions": [],
            "max_cc": 0,
            "avg_cc": 0.0,
            "junior_grade": False,
            "error": "radon not installed",
        }

    if not code or not code.strip():
        return {
            "functions": [],
            "max_cc": 0,
            "avg_cc": 0.0,
            "junior_grade": False,
        }

    try:
        results = cc_visit(code)
        functions = []
        for block in results:
            name = getattr(block, "name", getattr(block, "fullname", "?"))
            comp = getattr(block, "complexity", 0)
            functions.append({"name": name, "complexity": comp})

        if not functions:
            return {
                "functions": [],
                "max_cc": 0,
                "avg_cc": 0.0,
                "junior_grade": False,
            }

        max_cc = max(f["complexity"] for f in functions)
        avg_cc = sum(f["complexity"] for f in functions) / len(functions)
        junior_grade = max_cc > JUNIOR_CC_THRESHOLD

        return {
            "functions": functions,
            "max_cc": max_cc,
            "avg_cc": round(avg_cc, 2),
            "junior_grade": junior_grade,
        }
    except Exception as e:
        logger.warning(f"[code_quality] Radon CC 계산 실패: {e}")
        return {
            "functions": [],
            "max_cc": 0,
            "avg_cc": 0.0,
            "junior_grade": False,
            "error": str(e),
        }


def compute_delta_cc(
    v1_radon_result: Dict[str, Any],
    v2_radon_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    v1 대비 v2의 CC 상승률(ΔCC) 계산. 학점 산정용.

    ΔCC(%) = (v2_avg_cc - v1_avg_cc) / max(v1_avg_cc, 0.01) * 100
    v1에 함수가 없으면 v1_avg_cc=0으로 보고, v2만 있으면 상승률 100% 또는 N/A로 처리.

    Returns:
        {
            "delta_cc_pct": float,   # 상승률 (%)
            "v1_avg_cc": float,
            "v2_avg_cc": float,
            "v1_max_cc": int,
            "v2_max_cc": int,
        }
    """
    v1_avg = v1_radon_result.get("avg_cc") or 0.0
    v2_avg = v2_radon_result.get("avg_cc") or 0.0
    v1_max = v1_radon_result.get("max_cc") or 0
    v2_max = v2_radon_result.get("max_cc") or 0

    base_cc = max(v1_avg, 0.01)
    delta_cc_pct = round((v2_avg - v1_avg) / base_cc * 100.0, 2)

    return {
        "delta_cc_pct": delta_cc_pct,
        "v1_avg_cc": v1_avg,
        "v2_avg_cc": v2_avg,
        "v1_max_cc": v1_max,
        "v2_max_cc": v2_max,
    }


# 스마트 게이트 2026(spec_id=20) 기본 패턴
SMART_GATE_2026_SPEC_ID = 20

# 문제별 '필수 클래스/상속 관계' 패턴 정의
# - inheritance: class_name 이 base_names 중 하나를 상속해야 함 (이름 부분 일치)
# - strategy_pattern: class_name 이 규칙 속성(이름에 rules_attr_contains 포함) 보유 및 apply_methods_contain 중 하나 호출
# 다른 문제 대응: problem_context["ast_required_patterns"] 등에서 리스트를 넘기면 check_ast_patterns(..., required_patterns=...) 로 사용 가능
AST_PATTERN_INHERITANCE = "inheritance"
AST_PATTERN_STRATEGY = "strategy_pattern"

SMART_GATE_2026_PATTERNS: List[Dict[str, Any]] = [
    {
        "type": AST_PATTERN_INHERITANCE,
        "class_name": "SecurityRule",
        "base_names": ["BaseRule", "Rule"],
    },
    {
        "type": AST_PATTERN_STRATEGY,
        "class_name": "GateManager",
        "rules_attr_contains": "rule",
        "apply_methods_contain": ["check", "evaluate", "apply"],
    },
]


def _check_inheritance(tree: ast.AST, class_name: str, base_names: List[str]) -> bool:
    """클래스 class_name 이 base_names 중 하나를 상속하는지 검사."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for base in node.bases:
                base_name = _get_name(base)
                if base_name:
                    for allowed in base_names:
                        if allowed in base_name or base_name == allowed:
                            return True
    return False


def _check_strategy_pattern(
    tree: ast.AST,
    class_name: str,
    rules_attr_contains: str = "rule",
    apply_methods_contain: Optional[List[str]] = None,
) -> bool:
    """class_name 클래스가 규칙 속성 보유·적용(순회 또는 메서드 호출) 형태인지 검사."""
    apply_methods_contain = apply_methods_contain or ["check", "evaluate", "apply"]
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            for stmt in node.body:
                if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
                    for t in targets:
                        attr = _get_attr_name(t)
                        if attr and rules_attr_contains.lower() in attr.lower():
                            return True
                if isinstance(stmt, ast.FunctionDef):
                    for n in ast.walk(stmt):
                        if isinstance(n, ast.For) and getattr(n, "iter", None):
                            iter_name = _get_name(n.iter)
                            if iter_name and rules_attr_contains.lower() in iter_name.lower():
                                return True
                        if isinstance(n, ast.Call):
                            call_name = _get_call_name(n)
                            if call_name and any(m in call_name.lower() for m in apply_methods_contain):
                                return True
    return False


def check_ast_patterns(
    code: str,
    spec_id: Optional[int] = None,
    required_patterns: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    문제별 '필수 클래스/상속 관계' 리스트에 따른 AST 정답 구조 검사.

    required_patterns 를 넘기면 해당 패턴만 검사. 넘기지 않으면 spec_id=20 일 때
    스마트 게이트 2026 기본 패턴(SecurityRule 상속, GateManager 전략 패턴) 사용.
    spec_id != 20 이고 required_patterns 도 없으면 적용 안 함(applicable=False).

    패턴 형식:
    - inheritance: {"type": "inheritance", "class_name": str, "base_names": [str, ...]}
    - strategy_pattern: {"type": "strategy_pattern", "class_name": str,
        "rules_attr_contains": str (기본 "rule"), "apply_methods_contain": [str, ...] (기본 check/evaluate/apply)}

    Args:
        code: Python 소스 코드 문자열
        spec_id: 문제 스펙 ID. required_patterns 없을 때 20이면 Smart Gate 2026 패턴 사용.
        required_patterns: 문제별 필수 패턴 리스트. 있으면 spec_id 무관히 이걸로 검사.

    Returns:
        {
            "applicable": bool,
            "pattern_results": [{"pattern": dict, "passed": bool}, ...],
            "ast_pattern_matched": bool,  # 모든 패턴 통과 시 True
            "security_rule_inherits_baserule": bool,  # Smart Gate 2026 호환용
            "gate_manager_strategy_pattern": bool,
        }
    """
    not_applicable = {
        "applicable": False,
        "pattern_results": [],
        "security_rule_inherits_baserule": False,
        "gate_manager_strategy_pattern": False,
        "ast_pattern_matched": True,
    }
    patterns = required_patterns if required_patterns else (
        SMART_GATE_2026_PATTERNS if spec_id == SMART_GATE_2026_SPEC_ID else None
    )
    if not patterns:
        return not_applicable

    if not code or not code.strip():
        return {
            "applicable": True,
            "pattern_results": [{"pattern": p, "passed": False} for p in patterns],
            "security_rule_inherits_baserule": False,
            "gate_manager_strategy_pattern": False,
            "ast_pattern_matched": False,
        }

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        logger.debug(f"[code_quality] AST 파싱 실패: {e}")
        return {
            "applicable": True,
            "pattern_results": [{"pattern": p, "passed": False} for p in patterns],
            "security_rule_inherits_baserule": False,
            "gate_manager_strategy_pattern": False,
            "ast_pattern_matched": False,
            "error": str(e),
        }

    results: List[Dict[str, Any]] = []
    for p in patterns:
        ptype = p.get("type")
        if ptype == AST_PATTERN_INHERITANCE:
            passed = _check_inheritance(
                tree,
                p.get("class_name", ""),
                p.get("base_names", []),
            )
        elif ptype == AST_PATTERN_STRATEGY:
            passed = _check_strategy_pattern(
                tree,
                p.get("class_name", ""),
                p.get("rules_attr_contains", "rule"),
                p.get("apply_methods_contain"),
            )
        else:
            passed = False
        results.append({"pattern": p, "passed": passed})

    ast_pattern_matched = all(r["passed"] for r in results)
    out: Dict[str, Any] = {
        "applicable": True,
        "pattern_results": results,
        "ast_pattern_matched": ast_pattern_matched,
    }
    # Smart Gate 2026 호환: 동일 순서/구성일 때 레거시 키 유지
    if patterns == SMART_GATE_2026_PATTERNS and len(results) >= 2:
        out["security_rule_inherits_baserule"] = results[0]["passed"]
        out["gate_manager_strategy_pattern"] = results[1]["passed"]
    else:
        out["security_rule_inherits_baserule"] = False
        out["gate_manager_strategy_pattern"] = False
    return out


def _get_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _get_attr_name(node: ast.AST) -> Optional[str]:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _get_call_name(node: ast.Call) -> Optional[str]:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None
