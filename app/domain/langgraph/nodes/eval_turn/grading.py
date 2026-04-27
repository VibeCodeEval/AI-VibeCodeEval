"""
V2.1 Hybrid 평가 모델 — 1~5점 Likert 척도 및 Backend 환산

- LLM은 1~5 정수(likert_score)와 진단 태그(diagnosis_profile)를 출력.
- Backend는 Map {5:100, 4:90, 3:80, 2:60, 1:0}으로 최종 점수(final_score) 환산.
- 가중치 산식은 사용하지 않음 (직관적 4점=우수/90점, 5점=탁월/100점).

V3.0 Rubric-Based 모델 (EvalTurnV30Output): 레거시 호환.
V3.1 (EvalTurnV31LLMOutput): LLM은 scoring_cot + rubric_breakdown(Rn 키)만 출력.
- turn_score는 eval_turn.yaml `intent_rubric_gates` 산식으로 백엔드에서 계산.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# 1~5 Likert → Backend 점수 (0~100) 매핑
# 5: Excellence(탁월) 100, 4: Good(우수) 80, 3: Neutral(보통) 70, 2: Weak(미흡) 50, 1: Bad(나쁨) 0
SCORE_MAPPING: Dict[int, int] = {
    5: 100,
    4: 80,
    3: 70,
    2: 50,
    1: 0,
}


def likert_to_final(likert_score: int) -> int:
    """
    LLM이 부여한 1~5 Likert 점수를 Backend 최종 점수(0, 50, 70, 80, 100)로 환산.

    Args:
        likert_score: 1, 2, 3, 4, 5 중 하나

    Returns:
        0, 50, 70, 80, 100 중 하나. 범위 밖이면 0 반환.
    """
    return SCORE_MAPPING.get(int(likert_score), 0)


def final_to_likert(final_score: int) -> int:
    """Backend 점수 → 대응 Likert (역매핑, 동점 시 높은 Likert 우선)."""
    for likert in (5, 4, 3, 2, 1):
        if SCORE_MAPPING[likert] == final_score:
            return likert
    return 3  # 기본 중립


# --- 진단 태그: 점수 계산용이 아닌 피드백/분석용 ---
# SETTING/CREATION: has_explicit_rules, has_examples
# FOLLOW_UP: context_maintenance, strategic_direction
# 공통: clarity_tier (High/Mid/Low)


def build_diagnosis_profile(
    clarity_tier: str = "Mid",
    has_explicit_rules: bool = False,
    has_examples: bool = False,
    context_maintenance: str = "Good",
    strategic_direction: bool = False,
) -> Dict[str, Any]:
    """진단 프로필 딕셔너리 생성 (기본값 포함)."""
    return {
        "clarity_tier": clarity_tier,  # "High" | "Mid" | "Low"
        "has_explicit_rules": has_explicit_rules,
        "has_examples": has_examples,
        "context_maintenance": context_maintenance,  # "Perfect" | "Good" | "Vague"
        "strategic_direction": strategic_direction,
    }


# --- V3.0 YAML JSON 출력 파싱용 (R1~R4 루브릭 기반) ---
class EvalTurnV30Output(BaseModel):
    """
    eval_turn.yaml V3.0에서 요구하는 JSON 출력 형식.
    LLM은 turn_score(1~5), rubric_breakdown(적용 루브릭별 점수),
    applied_rubrics(적용된 루브릭 목록), feedback_summary를 반환.
    final_score는 Backend에서 likert_to_final(turn_score)로 환산.
    """

    turn_score: int = Field(..., ge=1, le=5, description="의도별 가중 평균 점수 (1~5)")
    rubric_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="적용된 루브릭별 1~5 점수 (예: {'R1_logic_efficiency': 4, 'R2_clarity_completeness': 2})",
    )
    applied_rubrics: List[str] = Field(
        default_factory=list,
        description="실제 적용된 루브릭 목록 (의도에 따라 가변, 예: ['R1', 'R2', 'R3'])",
    )
    feedback_summary: str = Field("", description="평가 요약 (강점/아쉬운 점)")


class EvalTurnV31LLMOutput(BaseModel):
    """
    eval_turn.yaml V3.1 LLM JSON: scoring_cot + rubric_breakdown (Rn 키).
    turn_score는 백엔드 compute_turn_score_v31에서 산출.
    """

    scoring_cot: Dict[str, str] = Field(
        default_factory=dict,
        description="적용된 각 Rn에 대한 한국어 근거 (키: R1, R2, …)",
    )
    rubric_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="적용 루브릭별 1~5 정수 (키: R1, R2 또는 R1_logic_efficiency 등)",
    )


def _score_for_rubric_tag(bd: Dict[str, int], tag: str) -> int:
    """rubric_breakdown에서 Rn 접두 키의 첫 점수를 찾고, 없으면 3(중립)."""
    for k, v in bd.items():
        if str(k).upper().startswith(tag):
            return int(v)
    return 3


def scores_r1_to_r4(bd: Dict[str, int]) -> Dict[str, int]:
    return {t: _score_for_rubric_tag(bd, t) for t in ("R1", "R2", "R3", "R4")}


def compute_turn_score_v31(unified_intent: str, rubric_breakdown: Dict[str, int]) -> int:
    """
    eval_turn.yaml intent_rubric_gates 주석의 turn_score 산식 (1~5 정수로 클램프).
    """
    s = scores_r1_to_r4(rubric_breakdown or {})
    u = (unified_intent or "").strip().upper() or "DEBUGGING"
    if u == "VALIDATION":
        u = "DEBUGGING"

    def clamp(x: float) -> int:
        v = int(round(x))
        return max(1, min(5, v))

    if u == "FOLLOW_UP":
        return clamp(float(s["R4"]))
    if u == "CREATION":
        return clamp((s["R1"] + s["R2"] + s["R3"]) / 3.0)
    if u == "SETTING":
        return clamp((s["R2"] + s["R3"]) / 2.0)
    if u == "REFINEMENT":
        return clamp((s["R1"] + s["R2"] + s["R3"] + s["R4"]) / 4.0)
    if u == "DEBUGGING":
        return clamp((s["R1"] + 2 * s["R2"] + s["R4"]) / 4.0)
    if u == "EXPLORATION":
        return clamp((s["R1"] + s["R2"]) / 2.0)
    return clamp((s["R1"] + 2 * s["R2"] + s["R4"]) / 4.0)


def infer_applied_rubrics_from_breakdown(rubric_breakdown: Dict[str, int]) -> List[str]:
    """breakdown 키에서 R1~R4 태그 목록 추출 (정렬)."""
    found: List[str] = []
    for k in rubric_breakdown:
        ku = str(k).upper()
        for tag in ("R1", "R2", "R3", "R4"):
            if ku.startswith(tag) and tag not in found:
                found.append(tag)
                break
    order = {"R1": 0, "R2": 1, "R3": 2, "R4": 3}
    return sorted(found, key=lambda t: order[t])


def resolve_unified_intent_for_turn_eval(
    state: Any, eval_type: str
) -> str:
    """
    State.unified_intent 우선, 없으면 eval_type 한글/영문 키워드로 6대 의도 추정.
    """
    ui = (state.get("unified_intent") or "").strip().upper()
    if ui == "VALIDATION":
        return "DEBUGGING"
    if ui in {"SETTING", "CREATION", "REFINEMENT", "DEBUGGING", "EXPLORATION", "FOLLOW_UP"}:
        return ui
    et = eval_type or ""
    needles = (
        ("규칙 설정", "SETTING"),
        ("시스템 프롬프트", "SETTING"),
        ("코드 생성", "CREATION"),
        ("최적화", "REFINEMENT"),
        ("디버깅", "DEBUGGING"),
        ("테스트 케이스", "DEBUGGING"),
        ("힌트", "EXPLORATION"),
        ("질의", "EXPLORATION"),
        ("탐구", "EXPLORATION"),
        ("후속", "FOLLOW_UP"),
        ("Follow Up", "FOLLOW_UP"),
    )
    for needle, val in needles:
        if needle in et:
            return val
    return "DEBUGGING"


# --- V2.1 YAML JSON 출력 파싱용 (LLM이 반환하는 필드만) ---
class EvalTurnV21Output(BaseModel):
    """
    eval_turn.yaml V2.1에서 요구하는 JSON 출력 형식.
    LLM은 likert_score, diagnosis_profile, feedback_summary만 반환하고,
    final_score는 Backend에서 likert_to_final()로 환산하여 채움.
    """

    likert_score: int = Field(..., ge=1, le=5, description="1~5 Likert 점수")
    diagnosis_profile: Dict[str, Any] = Field(
        default_factory=lambda: {
            "clarity_tier": "Mid",
            "has_explicit_rules": False,
            "has_examples": False,
            "context_maintenance": "Good",
            "strategic_direction": False,
        },
        description="진단 태그 (clarity_tier, has_explicit_rules 등)",
    )
    feedback_summary: str = Field("", description="평가 요약 (강점/보완점)")


# --- Hybrid 평가 결과 구조체 (LLM 출력/Backend 환산) ---
DEFAULT_DIAGNOSIS_PROFILE = {
    "clarity_tier": "Mid",
    "has_explicit_rules": False,
    "has_examples": False,
    "context_maintenance": "Good",
    "strategic_direction": False,
}


class DiagnosisProfile(BaseModel):
    """평가 근거용 진단 태그 (점수 계산에는 미사용)."""

    clarity_tier: str = "Mid"  # "High" | "Mid" | "Low"
    has_explicit_rules: bool = False
    has_examples: bool = False
    context_maintenance: str = "Good"  # "Perfect" | "Good" | "Vague"
    strategic_direction: bool = False


class EvaluationResult(BaseModel):
    """
    Hybrid 평가 결과. Legacy 응답도 받을 수 있도록 likert_score는 Optional.
    출력(Output)은 항상 final_score가 채워진 상태로 통일하여 downstream(Holistic Flow 등)에 전달.
    """

    likert_score: Optional[int] = Field(
        None, ge=1, le=5, description="LLM 출력값 1~5 (Legacy일 땐 없음)"
    )
    final_score: int = Field(..., description="Backend 환산값 0, 60, 80, 90, 100 (항상 채움)")
    diagnosis_profile: Dict[str, Any] = Field(
        default_factory=lambda: dict(DEFAULT_DIAGNOSIS_PROFILE),
        description="진단 태그 (피드백용)",
    )
    feedback_summary: str = Field("", description="평가 요약")

    @classmethod
    def from_likert(cls, likert_score: int, **kwargs: Any) -> "EvaluationResult":
        """Likert 1~5만 주어졌을 때 final_score 자동 환산."""
        return cls(
            likert_score=likert_score,
            final_score=likert_to_final(likert_score),
            **kwargs,
        )

    @classmethod
    def from_legacy_score(cls, score: int, **kwargs: Any) -> "EvaluationResult":
        """Legacy 0~100 점수만 있을 때. likert_score 없음, final_score만 채움."""
        return cls(likert_score=None, final_score=max(0, min(100, int(score))), **kwargs)


def evaluation_result_from_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    LLM/스키마 출력을 Hybrid 평가 결과 형태로 정규화.
    출력은 항상 final_score가 채워진 상태로 통일 (Legacy score/average로 채울 수 있음).
    """
    out = dict(data)
    likert = data.get("likert_score")
    final = data.get("final_score")
    legacy_score = data.get("score", data.get("average"))

    if final is not None and isinstance(final, (int, float)):
        out["final_score"] = int(final)
    elif likert is not None:
        try:
            out["final_score"] = likert_to_final(int(likert))
        except (TypeError, ValueError):
            out["final_score"] = 0
    elif legacy_score is not None:
        out["final_score"] = max(0, min(100, int(legacy_score)))
    else:
        out.setdefault("final_score", 0)

    if "diagnosis_profile" not in out or not isinstance(out["diagnosis_profile"], dict):
        out.setdefault("diagnosis_profile", dict(DEFAULT_DIAGNOSIS_PROFILE))
    out.setdefault("feedback_summary", data.get("final_reasoning", ""))
    return out
