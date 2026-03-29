"""
Phase 6B: Integrated Evaluator (통합 평가 노드)

V2.1 Step 04: Radon CC, AST 패턴 검사, 5대 루브릭 반영.

[목적]
- 제출 시 Spec 중심 통합 평가 수행
- 6개 핵심 지표 기반 점수 계산 (규칙 기반, LLM 호출 없음)
- code_content 있으면: Radon CC(함수별 복잡도), AST 패턴(SecurityRule 상속, GateManager 전략 패턴), 5대 루브릭 추정
- Context Window 최적화: turn_analysis 배열 사용 (~500 토큰)

[핵심 철학]
"불완전한 코드는 첫 프롬프트의 불완전한 Spec에서 비롯된다"
- 첫 프롬프트: 55% (Spec 완전성 35% + 표현 품질 20%)
- 후속 턴: 25% (맥락 연결 15% + Spec 회복 10%)
- 효율성: 20% (턴 수 + 회복 속도)

[평가 지표]
1. Spec 완전성 (35%) - 필수 Spec 명시 여부
2. 명확성 (7%) - 구체적 값, 조건 명시
3. 구조화 (7%) - XML 태그, 마크다운 활용
4. 예시/구체성 (6%) - I/O 예시, 엣지 케이스
5. 맥락 연결 (15%) - 이전 턴 참조, Spec 회복
6. 효율성 (20%) - 턴 수, 회복 속도

[데이터 흐름]
1. PostgreSQL에서 모든 turn_analysis 조회
2. 규칙 기반 점수 계산
3. 통합 점수 및 피드백 생성
4. State에 integrated_score 반환
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.domain.langgraph.states import (
    IntegratedEvaluationResult,
    MainGraphState,
    SessionAnalysis,
    TurnAnalysis,
)

logger = logging.getLogger(__name__)


# ===== 상수 정의 =====

# 가중치 설정
WEIGHTS = {
    "first_prompt": {
        "total": 0.55,
        "spec_completeness": 0.35,
        "expression_quality": 0.20,
    },
    "follow_up": {
        "total": 0.25,
        "context_connection": 0.15,
        "spec_recovery": 0.10,
    },
    "efficiency": {
        "total": 0.20,
        "turn_efficiency": 0.10,
        "recovery_speed": 0.10,
    },
}

# 효율성 점수 기준 (턴 수 기반)
TURN_EFFICIENCY_SCORES = {
    1: 100,  # 1턴: 만점
    2: 90,   # 2턴: 90점
    3: 75,   # 3턴: 75점
    4: 60,   # 4턴: 60점
    5: 50,   # 5턴: 50점
}


# ===== 유틸리티 함수 =====


def calculate_expression_score(turn_analysis: Dict[str, Any]) -> float:
    """
    표현 품질 점수 계산
    
    구성:
    - 명확성 (clarity_score): 50%
    - 구조화 (has_structure): 30% 보너스
    - 예시 (has_examples): 20% 보너스
    
    Args:
        turn_analysis: TurnAnalysis 딕셔너리
        
    Returns:
        표현 품질 점수 (0-100)
    """
    clarity = turn_analysis.get("clarity_score", 50.0)
    has_structure = turn_analysis.get("has_structure", False)
    has_examples = turn_analysis.get("has_examples", False)
    has_specific_values = turn_analysis.get("has_specific_values", False)
    
    # 기본 점수: 명확성의 50%
    score = clarity * 0.5
    
    # 보너스 점수
    if has_structure:
        score += 20
    if has_examples:
        score += 20
    if has_specific_values:
        score += 10
    
    return min(100.0, score)


def calculate_first_prompt_score(turn_analysis: Dict[str, Any]) -> Dict[str, Any]:
    """
    첫 프롬프트 점수 계산 (55%)
    
    구성:
    - Spec 완전성 (35%)
    - 표현 품질 (20%)
    
    Args:
        turn_analysis: 첫 턴의 TurnAnalysis
        
    Returns:
        {
            "score": float,
            "spec_completeness": float,
            "expression_quality": float,
            "details": {...}
        }
    """
    spec_completeness = turn_analysis.get("spec_completeness", 50.0)
    expression_quality = calculate_expression_score(turn_analysis)
    
    # 가중 점수 계산
    weighted_score = (
        spec_completeness * (WEIGHTS["first_prompt"]["spec_completeness"] / WEIGHTS["first_prompt"]["total"]) +
        expression_quality * (WEIGHTS["first_prompt"]["expression_quality"] / WEIGHTS["first_prompt"]["total"])
    )
    
    return {
        "score": round(weighted_score, 2),
        "spec_completeness": round(spec_completeness, 2),
        "expression_quality": round(expression_quality, 2),
        "details": {
            "specified_specs": turn_analysis.get("specified_specs", []),
            "missing_specs": turn_analysis.get("missing_specs", []),
            "has_structure": turn_analysis.get("has_structure", False),
            "has_examples": turn_analysis.get("has_examples", False),
            "has_specific_values": turn_analysis.get("has_specific_values", False),
        }
    }


def calculate_follow_up_score(turn_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    후속 턴 점수 계산 (25%)
    
    구성:
    - 맥락 연결 (15%): 이전 턴 참조 품질
    - Spec 회복 (10%): 누락 Spec 보완 품질
    
    Args:
        turn_analyses: 모든 턴의 TurnAnalysis 리스트
        
    Returns:
        {
            "score": float,
            "context_quality": float,
            "spec_recovery": float,
            "details": {...}
        }
    """
    if len(turn_analyses) <= 1:
        # 후속 턴이 없으면 만점 (첫 턴에서 완료)
        return {
            "score": 100.0,
            "context_quality": 100.0,
            "spec_recovery": 100.0,
            "details": {"follow_up_turns": 0, "total_recovered_specs": 0}
        }
    
    # 후속 턴들 (첫 턴 제외)
    follow_up_turns = turn_analyses[1:]
    
    # 맥락 연결 점수
    context_scores = []
    for ta in follow_up_turns:
        if ta.get("references_previous", False):
            context_scores.append(80)  # 이전 턴 참조 시 80점
        else:
            context_scores.append(40)  # 참조 없으면 40점
    
    context_quality = sum(context_scores) / len(context_scores) if context_scores else 50.0
    
    # Spec 회복 점수
    total_recovery = sum(ta.get("spec_recovery_count", 0) for ta in follow_up_turns)
    first_missing = len(turn_analyses[0].get("missing_specs", []))
    
    if first_missing > 0:
        recovery_rate = min(1.0, total_recovery / first_missing)
        spec_recovery = recovery_rate * 100
    else:
        spec_recovery = 100.0  # 누락 없었으면 만점
    
    # 가중 점수 계산
    weighted_score = (
        context_quality * (WEIGHTS["follow_up"]["context_connection"] / WEIGHTS["follow_up"]["total"]) +
        spec_recovery * (WEIGHTS["follow_up"]["spec_recovery"] / WEIGHTS["follow_up"]["total"])
    )
    
    return {
        "score": round(weighted_score, 2),
        "context_quality": round(context_quality, 2),
        "spec_recovery": round(spec_recovery, 2),
        "details": {
            "follow_up_turns": len(follow_up_turns),
            "total_recovered_specs": total_recovery,
            "first_turn_missing": first_missing,
        }
    }


def calculate_efficiency_score(turn_analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    효율성 점수 계산 (20%)
    
    구성:
    - 턴 효율성 (10%): 적은 턴으로 완료
    - 회복 속도 (10%): 빠른 Spec 보완
    
    Args:
        turn_analyses: 모든 턴의 TurnAnalysis 리스트
        
    Returns:
        {
            "score": float,
            "turn_efficiency": float,
            "recovery_speed": float,
            "details": {...}
        }
    """
    total_turns = len(turn_analyses)
    
    # 턴 효율성 점수
    turn_efficiency = TURN_EFFICIENCY_SCORES.get(total_turns, 40)
    
    # 회복 속도 점수
    if total_turns <= 1:
        recovery_speed = 100.0  # 1턴에 완료면 만점
    else:
        # 첫 턴에서 누락된 Spec이 몇 턴 만에 회복되었는지
        first_missing = len(turn_analyses[0].get("missing_specs", []))
        
        if first_missing == 0:
            recovery_speed = 100.0
        else:
            # 각 턴에서 회복된 Spec 누적
            cumulative_recovery = 0
            turns_to_recover = total_turns
            
            for i, ta in enumerate(turn_analyses[1:], start=2):
                cumulative_recovery += ta.get("spec_recovery_count", 0)
                if cumulative_recovery >= first_missing:
                    turns_to_recover = i
                    break
            
            # 빠른 회복일수록 높은 점수
            if turns_to_recover <= 2:
                recovery_speed = 90
            elif turns_to_recover <= 3:
                recovery_speed = 70
            elif turns_to_recover <= 4:
                recovery_speed = 50
            else:
                recovery_speed = 30
    
    # 가중 점수 계산
    weighted_score = (turn_efficiency + recovery_speed) / 2
    
    return {
        "score": round(weighted_score, 2),
        "turn_efficiency": round(turn_efficiency, 2),
        "recovery_speed": round(recovery_speed, 2),
        "details": {
            "total_turns": total_turns,
            "optimal_turns": 1,
        }
    }


def generate_analysis_text(
    first_prompt_result: Dict[str, Any],
    follow_up_result: Dict[str, Any],
    efficiency_result: Dict[str, Any],
    integrated_score: float,
) -> str:
    """
    종합 분석 텍스트 생성
    
    Args:
        first_prompt_result: 첫 프롬프트 평가 결과
        follow_up_result: 후속 턴 평가 결과
        efficiency_result: 효율성 평가 결과
        integrated_score: 통합 점수
        
    Returns:
        분석 텍스트
    """
    analysis_parts = []
    
    # 등급 판정
    if integrated_score >= 90:
        grade = "우수"
    elif integrated_score >= 70:
        grade = "양호"
    elif integrated_score >= 50:
        grade = "보통"
    else:
        grade = "미흡"
    
    analysis_parts.append(f"[종합 평가: {grade}] 통합 점수 {integrated_score:.1f}점")
    
    # 첫 프롬프트 분석
    fp_score = first_prompt_result["score"]
    spec_comp = first_prompt_result["spec_completeness"]
    
    if spec_comp >= 80:
        analysis_parts.append(f"첫 프롬프트에서 요구사항을 충분히 명시했습니다 (Spec 완전성: {spec_comp:.0f}%).")
    elif spec_comp >= 50:
        analysis_parts.append(f"첫 프롬프트에서 일부 요구사항이 누락되었습니다 (Spec 완전성: {spec_comp:.0f}%).")
    else:
        analysis_parts.append(f"첫 프롬프트에서 많은 요구사항이 누락되었습니다 (Spec 완전성: {spec_comp:.0f}%).")
    
    # 표현 품질
    expr = first_prompt_result["expression_quality"]
    if expr >= 70:
        analysis_parts.append("프롬프트 표현이 명확하고 구조화되어 있습니다.")
    elif expr >= 40:
        analysis_parts.append("프롬프트 표현이 다소 모호합니다. 구조화와 예시 추가를 권장합니다.")
    else:
        analysis_parts.append("프롬프트 표현이 불명확합니다. XML 태그, 마크다운, 예시 등을 활용하세요.")
    
    # 후속 턴 분석
    if follow_up_result["details"]["follow_up_turns"] > 0:
        recovery = follow_up_result["spec_recovery"]
        if recovery >= 80:
            analysis_parts.append("후속 턴에서 누락된 요구사항을 효과적으로 보완했습니다.")
        elif recovery >= 50:
            analysis_parts.append("후속 턴에서 일부 요구사항을 보완했지만 완전하지 않습니다.")
        else:
            analysis_parts.append("후속 턴에서 요구사항 보완이 부족합니다.")
    
    # 효율성 분석
    total_turns = efficiency_result["details"]["total_turns"]
    if total_turns == 1:
        analysis_parts.append("1턴에 완료하여 효율성이 매우 우수합니다.")
    elif total_turns <= 3:
        analysis_parts.append(f"{total_turns}턴에 완료했습니다.")
    else:
        analysis_parts.append(f"{total_turns}턴이 소요되어 효율성 개선이 필요합니다.")
    
    return " ".join(analysis_parts)


async def load_v1_checkpoint_code_from_db(session_id: str) -> Optional[str]:
    """
    Step 04: DB에서 is_v1_checkpoint 코드 조회.

    prompt_messages.meta에 is_v1_checkpoint=true, code_snapshot 이 있는 메시지에서
    v1 기준 코드를 가져옴.
    """
    from app.infrastructure.persistence.session import get_db_context
    from app.infrastructure.repositories.session_repository import SessionRepository

    postgres_session_id = (
        int(session_id.replace("session_", ""))
        if session_id and str(session_id).startswith("session_")
        else None
    )
    if not postgres_session_id:
        return None
    try:
        async with get_db_context() as db:
            repo = SessionRepository(db)
            return await repo.get_v1_checkpoint_code(postgres_session_id)
    except Exception as e:
        logger.warning(f"[Integrated Evaluator] v1 checkpoint 조회 실패: {e}")
        return None


def build_code_quality_metrics(
    v1_code: Optional[str],
    v2_code: Optional[str],
    spec_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Step 04: v1(Phase 1 확정) 대비 v2(제출 코드) 비교 — Radon CC, ΔCC, AST 패턴.

    - v1_code: DB에서 조회한 is_v1_checkpoint 코드 (없으면 None)
    - v2_code: 현재 제출 코드 (code_content)
    - spec_id: 스마트 게이트 2026(20)일 때만 AST 정답 구조 검사 적용
    - v1_metrics, v2_metrics: 각각 Radon CC 결과
    - delta_cc: v1 대비 v2의 CC 상승률(%)
    """
    from app.domain.langgraph.utils.code_quality import (
        check_ast_patterns,
        compute_delta_cc,
        compute_radon_cc,
    )

    v1_radon = compute_radon_cc(v1_code or "") if v1_code else {"avg_cc": 0.0, "max_cc": 0, "functions": []}
    v2_radon = compute_radon_cc(v2_code or "") if v2_code else {"avg_cc": 0.0, "max_cc": 0, "functions": []}
    ast_result = check_ast_patterns(v2_code or "", spec_id=spec_id) if v2_code else {}

    delta_cc_result = {}
    if v1_code or v2_code:
        delta_cc_result = compute_delta_cc(v1_radon, v2_radon)

    return {
        "v1_metrics": {"radon_cc": v1_radon},
        "v2_metrics": {
            "radon_cc": v2_radon,
            "ast_patterns": ast_result,
        },
        "radon_cc": v2_radon,
        "ast_pattern_matched": ast_result.get("ast_pattern_matched", False),
        "security_rule_inherits_baserule": ast_result.get("security_rule_inherits_baserule", False),
        "gate_manager_strategy_pattern": ast_result.get("gate_manager_strategy_pattern", False),
        "junior_grade": v2_radon.get("junior_grade", False),
        "delta_cc": delta_cc_result,
        "has_v1": bool(v1_code and (v1_code or "").strip()),
        "ast_applicable": ast_result.get("applicable", False),  # spec_id=20일 때만 True, 루브릭 보너스 적용 여부
    }


def build_rubric_breakdown(
    turn_analyses: List[Dict[str, Any]],
    first_prompt_result: Dict[str, Any],
    follow_up_result: Dict[str, Any],
    code_quality_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """
    Step 04: 5대 루브릭 키로 rubric_breakdown 구성.

    - instruction_clarity: 지시의 구체성 (turn_analysis 명확성 반영)
    - design_ownership: 설계 주도권 (구조화·예시 보너스)
    - logical_gaps: 논리적 빈틈없음 (spec_recovery 반영)
    - consistency_maintained: 일관성 유지 (맥락 연결 반영)
    - code_improvement_contribution: 코드 개선 기여도 (CC·AST 반영)
    """
    breakdown = {
        "instruction_clarity": 50.0,
        "design_ownership": 50.0,
        "logical_gaps": 50.0,
        "consistency_maintained": 50.0,
        "code_improvement_contribution": 50.0,
    }

    if turn_analyses:
        first = turn_analyses[0]
        breakdown["instruction_clarity"] = min(100.0, first.get("clarity_score", 50) * 1.2)
        breakdown["design_ownership"] = min(
            100.0,
            30.0 + (20.0 if first.get("has_structure") else 0) + (20.0 if first.get("has_examples") else 0) + first.get("spec_completeness", 50) * 0.3,
        )
    breakdown["logical_gaps"] = min(100.0, first_prompt_result.get("spec_completeness", 50) + follow_up_result.get("spec_recovery", 50) * 0.5)
    breakdown["consistency_maintained"] = min(100.0, follow_up_result.get("context_quality", 50))

    if code_quality_metrics:
        junior = code_quality_metrics.get("junior_grade", False)
        ast_ok = code_quality_metrics.get("ast_pattern_matched", False)
        ast_applicable = code_quality_metrics.get("ast_applicable", False)  # 스마트 게이트 2026 전용일 때만 보너스
        radon = code_quality_metrics.get("radon_cc", {})
        avg_cc = radon.get("avg_cc", 0)
        delta_cc = code_quality_metrics.get("delta_cc", {})
        delta_cc_pct = delta_cc.get("delta_cc_pct", 0.0)
        # 코드 개선 기여: AST 패턴 일치(spec_id=20일 때만) + CC·ΔCC 반영 (학점 산정용)
        contrib = 50.0
        if ast_ok and ast_applicable:
            contrib += 25.0
        if not junior and avg_cc <= 10:
            contrib += 15.0
        elif junior:
            contrib -= 15.0
        # ΔCC 상승률: v1이 있을 때만 적용 (10% 이하 가산, 30% 초과 감점)
        if code_quality_metrics.get("has_v1"):
            if delta_cc_pct <= 10:
                contrib += 10.0
            elif delta_cc_pct > 30:
                contrib -= 10.0
        breakdown["code_improvement_contribution"] = max(0.0, min(100.0, contrib))

    return {k: round(v, 2) for k, v in breakdown.items()}


def generate_suggestions(
    first_prompt_result: Dict[str, Any],
    follow_up_result: Dict[str, Any],
) -> List[str]:
    """
    개선 제안 생성
    
    Args:
        first_prompt_result: 첫 프롬프트 평가 결과
        follow_up_result: 후속 턴 평가 결과
        
    Returns:
        개선 제안 리스트
    """
    suggestions = []
    
    details = first_prompt_result["details"]
    
    # Spec 관련 제안
    missing_specs = details.get("missing_specs", [])
    if missing_specs:
        high_missing = [m["category"] for m in missing_specs if m.get("importance") == "HIGH"]
        if high_missing:
            suggestions.append(f"다음 핵심 요구사항을 첫 프롬프트에 명시하세요: {', '.join(high_missing[:3])}")
    
    # 표현 품질 제안
    if not details.get("has_structure"):
        suggestions.append("프롬프트를 구조화하세요 (예: XML 태그, 마크다운 헤더, 번호 리스트)")
    
    if not details.get("has_examples"):
        suggestions.append("입출력 예시나 엣지 케이스를 포함하세요")
    
    if not details.get("has_specific_values"):
        suggestions.append("구체적인 제약 조건(N <= 1000, 시간복잡도 O(N^2) 등)을 명시하세요")
    
    # 맥락 연결 제안
    if follow_up_result["context_quality"] < 70:
        suggestions.append("후속 질문 시 이전 대화를 명확히 참조하세요 (예: '위에서 말씀하신 방법에서...')")
    
    return suggestions[:5]  # 최대 5개


# ===== 메인 노드 함수 =====


async def load_turn_analyses_from_db(session_id: str) -> List[Dict[str, Any]]:
    """
    PostgreSQL에서 모든 turn_analysis 조회
    
    Args:
        session_id: 세션 ID (예: "session_123")
        
    Returns:
        TurnAnalysis 딕셔너리 리스트
    """
    from app.infrastructure.persistence.session import get_db_context
    from app.infrastructure.repositories.session_repository import SessionRepository
    
    try:
        # session_id에서 PostgreSQL ID 추출
        postgres_session_id = (
            int(session_id.replace("session_", ""))
            if session_id.startswith("session_")
            else None
        )
        
        if not postgres_session_id:
            logger.warning(f"[Integrated Evaluator] 유효하지 않은 session_id: {session_id}")
            return []
        
        async with get_db_context() as db:
            session_repo = SessionRepository(db)
            turn_analyses = await session_repo.get_all_turn_analyses(postgres_session_id)
            
            logger.info(
                f"[Integrated Evaluator] turn_analysis 조회 완료 - "
                f"session_id: {postgres_session_id}, 턴 수: {len(turn_analyses)}"
            )
            
            return turn_analyses
            
    except Exception as e:
        logger.error(
            f"[Integrated Evaluator] turn_analysis 조회 실패 - "
            f"session_id: {session_id}, error: {str(e)}",
            exc_info=True,
        )
        return []


async def integrated_evaluator(state: MainGraphState) -> Dict[str, Any]:
    """
    통합 평가 노드 (제출 시 실행)
    
    [실행 시점]
    - 사용자가 제출 버튼 클릭 시
    - eval_holistic_flow 전에 실행
    
    [평가 흐름]
    1. PostgreSQL에서 모든 turn_analysis 조회
    2. 6개 지표 기반 점수 계산 (규칙 기반)
    3. 통합 점수 및 피드백 생성
    4. State에 결과 반환
    
    Args:
        state: 메인 그래프 상태
        
    Returns:
        {
            "integrated_score": float,
            "integrated_evaluation": Dict,
            "updated_at": str,
        }
    """
    session_id = state.get("session_id", "unknown")
    logger.info(f"[Integrated Evaluator] 시작 - session_id: {session_id}")
    
    try:
        # 1. PostgreSQL에서 turn_analysis 조회
        turn_analyses = await load_turn_analyses_from_db(session_id)
        
        if not turn_analyses:
            logger.warning(f"[Integrated Evaluator] turn_analysis 없음 - session_id: {session_id}")
            return {
                "integrated_score": None,
                "integrated_evaluation": {
                    "error": "turn_analysis 데이터가 없습니다",
                },
                "updated_at": datetime.utcnow().isoformat(),
            }
        
        # 2. 첫 프롬프트 평가 (55%)
        first_prompt_result = calculate_first_prompt_score(turn_analyses[0])
        
        # 3. 후속 턴 평가 (25%)
        follow_up_result = calculate_follow_up_score(turn_analyses)
        
        # 4. 효율성 평가 (20%)
        efficiency_result = calculate_efficiency_score(turn_analyses)
        
        # 5. 통합 점수 계산
        integrated_score = (
            first_prompt_result["score"] * WEIGHTS["first_prompt"]["total"] +
            follow_up_result["score"] * WEIGHTS["follow_up"]["total"] +
            efficiency_result["score"] * WEIGHTS["efficiency"]["total"]
        )
        integrated_score = round(integrated_score, 2)
        
        # 6. 분석 텍스트 생성
        analysis = generate_analysis_text(
            first_prompt_result,
            follow_up_result,
            efficiency_result,
            integrated_score,
        )
        
        # 7. 개선 제안 생성
        suggestions = generate_suggestions(first_prompt_result, follow_up_result)

        # Step 04: v1(DB is_v1_checkpoint) vs v2(code_content) 비교, ΔCC·code_quality_metrics·rubric_breakdown
        code_content = (state.get("code_content") or state.get("v2_code") or "").strip()
        v1_code = state.get("v1_code")
        if v1_code is None and code_content:
            v1_code = await load_v1_checkpoint_code_from_db(session_id)
        v2_code = code_content or None
        code_quality_metrics = None
        rubric_breakdown = build_rubric_breakdown(
            turn_analyses,
            first_prompt_result,
            follow_up_result,
            code_quality_metrics=None,
        )
        if v2_code or v1_code:
            spec_id = state.get("spec_id")
            code_quality_metrics = build_code_quality_metrics(v1_code, v2_code, spec_id=spec_id)
            rubric_breakdown = build_rubric_breakdown(
                turn_analyses,
                first_prompt_result,
                follow_up_result,
                code_quality_metrics=code_quality_metrics,
            )
            delta_cc = code_quality_metrics.get("delta_cc", {})
            logger.info(
                f"[Integrated Evaluator] code_quality_metrics - "
                f"v1_used: {bool(v1_code)}, delta_cc_pct: {delta_cc.get('delta_cc_pct')}, "
                f"junior_grade: {code_quality_metrics.get('junior_grade')}, "
                f"ast_pattern_matched: {code_quality_metrics.get('ast_pattern_matched')}"
            )
        
        # 8. 턴별 상세 정보
        turn_details = [
            {
                "turn": ta.get("turn", i + 1),
                "spec_completeness": ta.get("spec_completeness", 0),
                "clarity_score": ta.get("clarity_score", 0),
                "has_structure": ta.get("has_structure", False),
                "has_examples": ta.get("has_examples", False),
                "spec_recovery_count": ta.get("spec_recovery_count", 0),
                "summary": ta.get("summary", ""),
            }
            for i, ta in enumerate(turn_analyses)
        ]
        
        # 결과 구성 (Step 04: code_quality_metrics, rubric_breakdown 포함)
        integrated_evaluation = {
            "integrated_score": integrated_score,
            "first_prompt": first_prompt_result,
            "follow_up": follow_up_result,
            "efficiency": efficiency_result,
            "analysis": analysis,
            "suggestions": suggestions,
            "turn_details": turn_details,
            "total_turns": len(turn_analyses),
            "rubric_breakdown": rubric_breakdown,
        }
        if code_quality_metrics is not None:
            integrated_evaluation["code_quality_metrics"] = code_quality_metrics
        
        logger.info(
            f"[Integrated Evaluator] 완료 - session_id: {session_id}, "
            f"integrated_score: {integrated_score}, "
            f"first_prompt: {first_prompt_result['score']}, "
            f"follow_up: {follow_up_result['score']}, "
            f"efficiency: {efficiency_result['score']}"
        )
        
        return {
            "integrated_score": integrated_score,
            "integrated_evaluation": integrated_evaluation,
            "updated_at": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error(
            f"[Integrated Evaluator] 에러 발생 - session_id: {session_id}, error: {str(e)}",
            exc_info=True,
        )
        return {
            "integrated_score": None,
            "integrated_evaluation": {
                "error": f"통합 평가 중 오류 발생: {str(e)}",
            },
            "error_message": f"Integrated Evaluator 실패: {str(e)}",
            "updated_at": datetime.utcnow().isoformat(),
        }
