#!/usr/bin/env python
"""
Phase 5-B: 평가 파인튜닝 데이터 추출 스크립트

사용자 프롬프트에 대한 평가 점수, 분석, 루브릭을 추출하여 평가 LLM 품질 개선에 활용합니다.

출력 파일:
- evaluation_data.jsonl      : 전체 평가 데이터
- evaluation_cleaned.jsonl   : 정제된 데이터 (score, analysis 필수)
- eval_high_score.jsonl       : 고점 프롬프트 (70+)
- eval_medium_score.jsonl    : 중점 프롬프트 (40-69)
- eval_low_score.jsonl       : 저점 프롬프트 (0-39)
- evaluation_examples.json   : Few-shot 예시 (의도별/점수대별)

사용법:
    python scripts/extract_evaluation_data.py
    python scripts/extract_evaluation_data.py --output-dir ./custom_output
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

# 프로젝트 루트를 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv(project_root / ".env")


def get_db_config() -> dict:
    """환경 변수에서 DB 설정 읽기"""
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", 5435)),
        "user": os.getenv("POSTGRES_USER", "postgres"),
        "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "database": os.getenv("POSTGRES_DB", "ai_vibe_coding_test"),
    }


def connect_db():
    """PostgreSQL 연결"""
    config = get_db_config()
    print(f"[INFO] DB 연결 중: {config['host']}:{config['port']}/{config['database']}")
    conn = psycopg2.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=config["database"],
    )
    return conn


# SQL 쿼리: 평가 데이터 추출
EXTRACT_EVALUATION_DATA_SQL = """
SET search_path TO ai_vibe_coding_test;

SELECT 
    pe.id,
    pe.session_id,
    pe.turn,
    pm.content AS user_prompt,
    pe.details,
    pe.created_at
FROM ai_vibe_coding_test.prompt_evaluations pe
JOIN ai_vibe_coding_test.prompt_messages pm 
    ON pe.session_id = pm.session_id 
    AND pe.turn = pm.turn
WHERE UPPER(pm.role) = 'USER'
    AND pe.evaluation_type = 'TURN_EVAL'
    AND pe.details->>'score' IS NOT NULL
ORDER BY pe.session_id, pe.turn;
"""


def parse_details(details: dict) -> dict[str, Any]:
    """details JSONB 필드 파싱"""
    result = {}
    
    # 기본 필드
    result["score"] = _safe_float(details.get("score"))
    result["analysis"] = details.get("analysis", "")
    result["intent"] = details.get("intent")
    result["intent_confidence"] = _safe_float(details.get("intent_confidence"))
    result["is_guardrail_failed"] = _safe_bool(details.get("is_guardrail_failed"))
    
    # 루브릭 파싱 (배열 또는 객체 형태)
    rubrics_raw = details.get("rubrics", [])
    result["rubrics"] = {}
    
    if isinstance(rubrics_raw, list):
        # 배열 형태: [{"name": "clarity", "score": 40.0, "reasoning": "..."}, ...]
        for rubric in rubrics_raw:
            if isinstance(rubric, dict):
                name = rubric.get("name")
                if name:
                    result["rubrics"][name] = {
                        "score": _safe_float(rubric.get("score")),
                        "reasoning": rubric.get("reasoning", "")
                    }
    elif isinstance(rubrics_raw, dict):
        # 객체 형태: {"clarity": {"score": 40.0, "reasoning": "..."}, ...}
        result["rubrics"] = {
            name: {
                "score": _safe_float(value.get("score") if isinstance(value, dict) else None),
                "reasoning": value.get("reasoning", "") if isinstance(value, dict) else ""
            }
            for name, value in rubrics_raw.items()
        }
    
    # 가중치 정보
    result["weights"] = details.get("weights", {})
    
    return result


def _safe_float(value: Any) -> float | None:
    """안전하게 float 변환"""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_bool(value: Any) -> bool:
    """안전하게 bool 변환"""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return bool(value)


def extract_evaluation_data(conn) -> list[dict[str, Any]]:
    """DB에서 평가 데이터 추출"""
    print("[INFO] 평가 데이터 추출 중...")
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(EXTRACT_EVALUATION_DATA_SQL)
        rows = cur.fetchall()
    
    results = []
    for row in rows:
        details = row.get("details", {})
        if not isinstance(details, dict):
            continue
        
        parsed = parse_details(details)
        
        # 출력 레코드 구성
        record = {
            "id": f"eval_{row['session_id']}_{row['turn']}",
            "user_prompt": row["user_prompt"],
            "intent": parsed.get("intent"),
            "intent_confidence": parsed.get("intent_confidence"),
            "score": parsed.get("score"),
            "rubrics": parsed.get("rubrics", {}),
            "weights": parsed.get("weights", {}),
            "analysis": parsed.get("analysis", ""),
            "is_guardrail_failed": parsed.get("is_guardrail_failed", False),
            "metadata": {
                "session_id": row["session_id"],
                "turn": row["turn"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
        }
        results.append(record)
    
    print(f"[INFO] 총 {len(results)}개의 평가 데이터 추출 완료")
    return results


def clean_data(evaluations: list[dict]) -> list[dict]:
    """데이터 정제: score가 NULL이거나 analysis가 비어있는 데이터 제외"""
    cleaned = []
    for eval_data in evaluations:
        score = eval_data.get("score")
        analysis = eval_data.get("analysis", "").strip()
        
        if score is not None and analysis:
            cleaned.append(eval_data)
    
    print(f"[INFO] 정제 결과: {len(cleaned)}개 (전체 {len(evaluations)}개 중)")
    return cleaned


def categorize_by_score(evaluations: list[dict]) -> dict[str, list[dict]]:
    """점수대별로 분류"""
    by_score = {
        "high": [],      # 70+
        "medium": [],    # 40-69
        "low": [],       # 0-39
    }
    
    for eval_data in evaluations:
        score = eval_data.get("score")
        if score is None:
            continue
        elif score >= 70:
            by_score["high"].append(eval_data)
        elif score >= 40:
            by_score["medium"].append(eval_data)
        else:
            by_score["low"].append(eval_data)
    
    return by_score


def categorize_by_intent(evaluations: list[dict]) -> dict[str, list[dict]]:
    """의도별로 분류"""
    by_intent = defaultdict(list)
    for eval_data in evaluations:
        intent = eval_data.get("intent") or "UNKNOWN"
        by_intent[intent].append(eval_data)
    return dict(by_intent)


def select_few_shot_examples(evaluations: list[dict]) -> dict:
    """Few-shot 예시 선정 (의도별/점수대별 대표 예시)"""
    examples = {
        "by_intent": {},
        "by_score": {
            "high": [],
            "medium": [],
            "low": []
        },
        "best_examples": []  # reasoning이 명확하고 점수가 높은 예시
    }
    
    # 의도별 예시 선정 (각 의도당 최대 5개, reasoning이 명확한 것 우선)
    by_intent = categorize_by_intent(evaluations)
    for intent, items in by_intent.items():
        # reasoning 길이와 점수로 정렬
        sorted_items = sorted(
            items,
            key=lambda x: (
                len(x.get("analysis", "")),  # analysis 길이 (명확한 reasoning)
                x.get("score", 0)  # 점수
            ),
            reverse=True
        )
        examples["by_intent"][intent] = sorted_items[:5]
    
    # 점수대별 예시 선정
    by_score = categorize_by_score(evaluations)
    for score_level, items in by_score.items():
        # analysis가 명확한 것 우선
        sorted_items = sorted(
            items,
            key=lambda x: len(x.get("analysis", "")),
            reverse=True
        )
        examples["by_score"][score_level] = sorted_items[:5]
    
    # 최고 예시 (점수 70+ 이고 analysis가 명확한 것)
    high_score = by_score["high"]
    sorted_high = sorted(
        high_score,
        key=lambda x: (len(x.get("analysis", "")), x.get("score", 0)),
        reverse=True
    )
    examples["best_examples"] = sorted_high[:10]
    
    return examples


def save_jsonl(data: list[dict], filepath: Path):
    """JSONL 형식으로 저장"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
    print(f"[INFO] 저장 완료: {filepath} ({len(data)}개 레코드)")


def save_json(data: dict, filepath: Path):
    """JSON 형식으로 저장"""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    print(f"[INFO] 저장 완료: {filepath}")


def print_statistics(evaluations: list[dict], cleaned: list[dict]):
    """통계 정보 출력"""
    print("\n" + "=" * 60)
    print("📊 추출 결과 통계")
    print("=" * 60)
    
    print(f"\n📌 전체 평가 데이터: {len(evaluations)}개")
    print(f"   - 정제된 데이터: {len(cleaned)}개")
    
    # 점수대별 분포
    by_score = categorize_by_score(cleaned)
    print(f"\n📌 점수대별 분포:")
    print(f"   - 고점 (70+): {len(by_score['high'])}개")
    print(f"   - 중점 (40-69): {len(by_score['medium'])}개")
    print(f"   - 저점 (0-39): {len(by_score['low'])}개")
    
    # 의도별 분포
    by_intent = categorize_by_intent(cleaned)
    print(f"\n📌 의도별 분포:")
    for intent, items in sorted(by_intent.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"   - {intent}: {len(items)}개")
    
    # 점수 통계
    scores = [e.get("score") for e in cleaned if e.get("score") is not None]
    if scores:
        print(f"\n📌 점수 통계:")
        print(f"   - 평균: {sum(scores) / len(scores):.2f}")
        print(f"   - 최고: {max(scores):.2f}")
        print(f"   - 최저: {min(scores):.2f}")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Phase 5-B: 평가 파인튜닝 데이터 추출"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".maestro/data/finetuning/phase5b_evaluation",
        help="출력 디렉토리 (기본값: .maestro/data/finetuning/phase5b_evaluation)"
    )
    args = parser.parse_args()
    
    output_dir = Path(project_root) / args.output_dir
    
    print("=" * 60)
    print("🚀 Phase 5-B: 평가 파인튜닝 데이터 추출")
    print(f"   출력 디렉토리: {output_dir}")
    print("=" * 60)
    
    try:
        # DB 연결
        conn = connect_db()
        
        # 데이터 추출
        evaluations = extract_evaluation_data(conn)
        
        if not evaluations:
            print("[WARN] 추출된 데이터가 없습니다. DB에 데이터가 있는지 확인하세요.")
            return
        
        # 데이터 정제
        cleaned = clean_data(evaluations)
        
        if not cleaned:
            print("[WARN] 정제된 데이터가 없습니다. score와 analysis가 있는 데이터가 필요합니다.")
            return
        
        # 통계 출력
        print_statistics(evaluations, cleaned)
        
        # 분류
        by_score = categorize_by_score(cleaned)
        
        # 파일 저장
        print("\n📁 파일 저장 중...")
        
        # 1. 전체 평가 데이터
        save_jsonl(evaluations, output_dir / "evaluation_data.jsonl")
        
        # 2. 정제된 데이터
        save_jsonl(cleaned, output_dir / "evaluation_cleaned.jsonl")
        
        # 3. 점수대별 분류
        save_jsonl(by_score["high"], output_dir / "eval_high_score.jsonl")
        save_jsonl(by_score["medium"], output_dir / "eval_medium_score.jsonl")
        save_jsonl(by_score["low"], output_dir / "eval_low_score.jsonl")
        
        # 4. Few-shot 예시
        examples = select_few_shot_examples(cleaned)
        save_json(examples, output_dir / "evaluation_examples.json")
        
        print("\n✅ Phase 5-B 완료!")
        print(f"   출력 디렉토리: {output_dir}")
        
        conn.close()
        
    except psycopg2.Error as e:
        print(f"[ERROR] DB 오류: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
