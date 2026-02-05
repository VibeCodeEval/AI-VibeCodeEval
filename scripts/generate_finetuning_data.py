#!/usr/bin/env python
"""
파인튜닝 데이터 자동 생성 스크립트

Maestro 정의(.maestro/tasks/phase5_finetuning.json, .maestro/docs/V2.1_Step_06_Finetuning_Data.md)에 따라
다음 두 가지 방식으로 데이터를 생성합니다.

1) DB 기반: 기존 추출 스크립트 3개를 순차 실행
   - Phase 5-A: 응답 쌍 (response_pairs, 점수대별, few-shot 예시)
   - Phase 5-B: 평가 데이터 (evaluation_data, 점수대별, 예시)
   - Phase 5-C: Chaining 평가 (chaining_data, 점수대별, 예시)

2) 합성 시드 데이터: DB 없이 또는 --synthetic 옵션으로
   - V2.1 Step 06 형식: (modification_prompt, cc_before, cc_after, ast_pattern_matched, label)
   - Phase 5 의도별 예시: intent, user_prompt, ideal_evaluation 스키마

사용법:
    python scripts/generate_finetuning_data.py
    python scripts/generate_finetuning_data.py --synthetic
    python scripts/generate_finetuning_data.py --db-only
    python scripts/generate_finetuning_data.py --output-dir .maestro/data/finetuning
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# 프로젝트 루트
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FINETUNING_BASE = PROJECT_ROOT / ".maestro" / "data" / "finetuning"


def run_script(script_name: str, output_dir: str) -> bool:
    """추출 스크립트 실행. 성공 시 True."""
    script_path = PROJECT_ROOT / "scripts" / script_name
    if not script_path.exists():
        print(f"[WARN] 스크립트 없음: {script_path}")
        return False
    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--output-dir", output_dir],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            print(f"[WARN] {script_name} 실패: {result.stderr[:500] if result.stderr else result.stdout[:500]}")
            return False
        print(result.stdout or f"[OK] {script_name} 완료")
        return True
    except subprocess.TimeoutExpired:
        print(f"[WARN] {script_name} 타임아웃")
        return False
    except Exception as e:
        print(f"[WARN] {script_name} 예외: {e}")
        return False


def generate_v21_cc_ast_seed(out_dir: Path) -> None:
    """
    V2.1 Step 06 형식 합성 시드 데이터 생성.
    (modification_prompt, cc_before, cc_after, ast_pattern_matched, label)
    - 구조적 지시 → 고득점, 모호한 지시 → 저득점 예시.
    """
    # .maestro/docs/V2.1_Work_Instructions.md 예시 기반
    seed_rows = [
        {
            "modification_prompt": "규칙 인터페이스 상속받아 SecurityRule 추가해줘",
            "cc_before": 12,
            "cc_after": 6,
            "ast_pattern_matched": {"SecurityRule_extends_BaseRule": True, "GateManager_strategy": True},
            "label": "high",
            "score": 85,
            "source": "synthetic_v21_seed",
        },
        {
            "modification_prompt": "기존 규칙 인터페이스를 유지하면서 SecurityRule 클래스를 추가해주세요",
            "cc_before": 14,
            "cc_after": 7,
            "ast_pattern_matched": {"SecurityRule_extends_BaseRule": True, "GateManager_strategy": True},
            "label": "high",
            "score": 82,
            "source": "synthetic_v21_seed",
        },
        {
            "modification_prompt": "2차 요구사항 반영해줘",
            "cc_before": 8,
            "cc_after": 18,
            "ast_pattern_matched": {"SecurityRule_extends_BaseRule": False, "GateManager_strategy": False},
            "label": "low",
            "score": 35,
            "source": "synthetic_v21_seed",
        },
        {
            "modification_prompt": "그냥 보안 규칙 넣어줘",
            "cc_before": 6,
            "cc_after": 15,
            "ast_pattern_matched": {"SecurityRule_extends_BaseRule": False, "GateManager_strategy": False},
            "label": "low",
            "score": 30,
            "source": "synthetic_v21_seed",
        },
        {
            "modification_prompt": "GateManager에 전략 패턴 적용해서 SecurityRule 붙여줘",
            "cc_before": 11,
            "cc_after": 5,
            "ast_pattern_matched": {"SecurityRule_extends_BaseRule": True, "GateManager_strategy": True},
            "label": "high",
            "score": 88,
            "source": "synthetic_v21_seed",
        },
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "v21_cc_ast_pairs.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for row in seed_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[INFO] 합성 시드 저장: {out_file} ({len(seed_rows)}건)")


def generate_phase5_intent_seed(out_dir: Path) -> None:
    """
    Phase 5 data_schema 형식 합성 시드 (의도별 예시).
    id, intent, user_prompt, context, ideal_evaluation
    """
    # phase5_finetuning.json data_schema + categories 기반
    categories = [
        "SYSTEM_PROMPT",
        "RULE_SETTING",
        "GENERATION",
        "OPTIMIZATION",
        "DEBUGGING",
        "TEST_CASE",
        "HINT_OR_QUERY",
        "FOLLOW_UP",
    ]
    seed_rows = [
        {
            "id": "label_001",
            "intent": "RULE_SETTING",
            "user_prompt": "여권 만료일이 2026-02-04 이전이면 REJECT, 항공편 상태가 BOARDING일 때만 통과하도록 규칙으로 정의해줘",
            "context": {"problem_id": 1, "turn_number": 1},
            "ideal_evaluation": {
                "clarity_score": 90,
                "examples_score": 70,
                "rules_score": 95,
                "cot_score": 85,
                "total_score": 85,
                "reasoning": "규칙을 명확히 나열하고 조건을 구체적으로 명시함.",
            },
            "source": "synthetic_phase5_seed",
        },
        {
            "id": "label_002",
            "intent": "GENERATION",
            "user_prompt": "규칙 인터페이스 상속받아 SecurityRule 추가해줘",
            "context": {"problem_id": 1, "turn_number": 2},
            "ideal_evaluation": {
                "clarity_score": 95,
                "examples_score": 60,
                "rules_score": 90,
                "cot_score": 88,
                "total_score": 88,
                "reasoning": "구조적 용어로 지시하여 설계 주도권·일관성 유지에 유리.",
            },
            "source": "synthetic_phase5_seed",
        },
        {
            "id": "label_003",
            "intent": "FOLLOW_UP",
            "user_prompt": "2차 요구사항 반영해줘",
            "context": {"problem_id": 1, "turn_number": 2},
            "ideal_evaluation": {
                "clarity_score": 40,
                "examples_score": 30,
                "rules_score": 35,
                "cot_score": 35,
                "total_score": 35,
                "reasoning": "모호한 지시로 인해 구조적 개선 없이 복잡도만 증가할 가능성 높음.",
            },
            "source": "synthetic_phase5_seed",
        },
        {
            "id": "label_004",
            "intent": "HINT_OR_QUERY",
            "user_prompt": "dp에 대해 알고있어?",
            "context": {"problem_id": 1, "turn_number": 3},
            "ideal_evaluation": {
                "clarity_score": 80,
                "examples_score": 50,
                "rules_score": 50,
                "cot_score": 70,
                "total_score": 65,
                "reasoning": "단순 힌트 질문으로 의도가 명확함.",
            },
            "source": "synthetic_phase5_seed",
        },
    ]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "phase5_ideal_evaluation_seed.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for row in seed_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[INFO] 합성 시드 저장: {out_file} ({len(seed_rows)}건)")


def main():
    parser = argparse.ArgumentParser(
        description="Maestro 기준 파인튜닝 데이터 자동 생성 (DB 추출 + 선택적 합성 시드)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".maestro/data/finetuning",
        help="출력 루트 디렉토리 (기본: .maestro/data/finetuning)",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="DB 없이 합성 시드 데이터만 생성 (phase6_gemma, phase5 시드)",
    )
    parser.add_argument(
        "--db-only",
        action="store_true",
        help="DB 추출만 수행, 합성 시드 생성 안 함",
    )
    args = parser.parse_args()

    base = Path(args.output_dir)
    if not base.is_absolute():
        base = PROJECT_ROOT / base

    print("=" * 60)
    print("파인튜닝 데이터 자동 생성")
    print(f"출력 루트: {base}")
    print("=" * 60)

    db_ok = False
    if not args.synthetic:
        # 1) DB 기반 추출
        phase5a_dir = str(base / "phase5a_response")
        phase5b_dir = str(base / "phase5b_evaluation")
        phase5c_dir = str(base / "phase5c_chaining")

        run_script("extract_response_pairs.py", phase5a_dir)
        run_script("extract_evaluation_data.py", phase5b_dir)
        run_script("extract_chaining_finetuning_data.py", phase5c_dir)
        db_ok = True  # 스크립트가 에러 시에도 경고만 하고 계속 진행됨

    if not args.db_only:
        # 2) 합성 시드 데이터 (--synthetic 이거나 DB만 돌린 뒤에도 시드는 추가 가능)
        generate_v21_cc_ast_seed(base / "phase6_gemma")
        generate_phase5_intent_seed(base / "phase5a_response")

    print("\n" + "=" * 60)
    print("완료. 출력 위치:")
    print(f"  - Phase 5-A 응답: {base / 'phase5a_response'}")
    print(f"  - Phase 5-B 평가: {base / 'phase5b_evaluation'}")
    print(f"  - Phase 5-C Chaining: {base / 'phase5c_chaining'}")
    print(f"  - Phase 6 (V2.1 CC/AST): {base / 'phase6_gemma'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
