#!/usr/bin/env python
"""
Phase 5-C: Chaining 파인튜닝 데이터 추출 스크립트

HOLISTIC_FLOW 평가 데이터를 추출하여 6a 노드(Holistic Flow Evaluator)의 
Chaining 전략 평가 품질 개선에 활용합니다.

출력 파일:
- chaining_data.jsonl              : 전체 Chaining 평가 데이터
- chaining_high_score.jsonl        : 고점 Chaining 전략 (70+)
- chaining_medium_score.jsonl      : 중점 Chaining 전략 (40-69)
- chaining_low_score.jsonl         : 저점 Chaining 전략 (0-39)
- chaining_examples.json           : Few-shot 예시

사용법:
    python scripts/extract_chaining_finetuning_data.py
    python scripts/extract_chaining_finetuning_data.py --output-dir ./custom_output
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


# SQL 쿼리: HOLISTIC_FLOW 평가 데이터 추출
EXTRACT_CHAINING_DATA_SQL = """
SET search_path TO ai_vibe_coding_test;

SELECT 
    pe.id,
    pe.session_id,
    pe.evaluation_type,
    pe.details,
    pe.created_at,
    ps.spec_id AS problem_spec_id
FROM ai_vibe_coding_test.prompt_evaluations pe
LEFT JOIN ai_vibe_coding_test.prompt_sessions ps 
    ON pe.session_id = ps.id
WHERE pe.evaluation_type::text = 'HOLISTIC_FLOW'
    AND pe.turn IS NULL
    AND pe.details->>'score' IS NOT NULL
ORDER BY pe.session_id;
"""


def parse_details(details: dict) -> dict[str, Any]:
    """details JSONB 필드 파싱"""
    result = {}
    
    # 기본 필드
    result["score"] = _safe_float(details.get("score"))
    result["analysis"] = details.get("analysis", "")
    
    # 평가 항목 파싱
    result["problem_decomposition"] = _parse_evaluation_criterion(
        details.get("problem_decomposition")
    )
    result["feedback_integration"] = _parse_evaluation_criterion(
        details.get("feedback_integration")
    )
    result["strategic_exploration"] = _parse_evaluation_criterion(
        details.get("strategic_exploration")
    )
    
    # structured_logs 파싱
    structured_logs = details.get("structured_logs", [])
    result["turn_summaries"] = []
    
    if isinstance(structured_logs, list):
        for log in structured_logs:
            if isinstance(log, dict):
                turn_summary = {
                    "turn": log.get("turn"),
                    "intent": log.get("intent"),
                    "user_summary": log.get("user_prompt_summary") or log.get("user_summary", ""),
                    "ai_summary": log.get("ai_summary", ""),
                    "score": _safe_float(log.get("turn_score") or log.get("score"))
                }
                result["turn_summaries"].append(turn_summary)
    
    return result


def _parse_evaluation_criterion(criterion: Any) -> dict[str, Any]:
    """평가 항목 파싱 (score, analysis 포함)"""
    if isinstance(criterion, dict):
        return {
            "score": _safe_float(criterion.get("score")),
            "analysis": criterion.get("analysis", "")
        }
    elif isinstance(criterion, (int, float)):
        # 점수만 있는 경우
        return {
            "score": _safe_float(criterion),
            "analysis": ""
        }
    else:
        return {
            "score": None,
            "analysis": ""
        }


def _safe_float(value: Any) -> float | None:
    """안전하게 float 변환"""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def extract_chaining_data(conn) -> list[dict[str, Any]]:
    """DB에서 Chaining 평가 데이터 추출"""
    print("[INFO] Chaining 평가 데이터 추출 중...")
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(EXTRACT_CHAINING_DATA_SQL)
        rows = cur.fetchall()
    
    results = []
    for row in rows:
        details = row.get("details", {})
        if not isinstance(details, dict):
            continue
        
        parsed = parse_details(details)
        
        # 출력 레코드 구성
        record = {
            "id": f"chaining_session_{row['session_id']}",
            "session_id": row["session_id"],
            "total_score": parsed.get("score"),
            "analysis": parsed.get("analysis", ""),
            "evaluation_criteria": {
                "problem_decomposition": parsed.get("problem_decomposition", {}),
                "feedback_integration": parsed.get("feedback_integration", {}),
                "strategic_exploration": parsed.get("strategic_exploration", {})
            },
            "turn_summaries": parsed.get("turn_summaries", []),
            "turn_count": len(parsed.get("turn_summaries", [])),
            "metadata": {
                "problem_spec_id": row.get("problem_spec_id"),
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
        }
        results.append(record)
    
    print(f"[INFO] 총 {len(results)}개의 Chaining 평가 데이터 추출 완료")
    return results


def clean_data(chaining_data: list[dict]) -> list[dict]:
    """데이터 정제: score가 NULL이거나 analysis가 비어있는 데이터 제외"""
    cleaned = []
    for data in chaining_data:
        score = data.get("total_score")
        analysis = data.get("analysis", "").strip()
        
        # 평가 항목이 최소 1개 이상 있는지 확인
        criteria = data.get("evaluation_criteria", {})
        has_criteria = any(
            criterion.get("score") is not None
            for criterion in criteria.values()
        )
        
        if score is not None and analysis and has_criteria:
            cleaned.append(data)
    
    print(f"[INFO] 정제 결과: {len(cleaned)}개 (전체 {len(chaining_data)}개 중)")
    return cleaned


def categorize_by_score(chaining_data: list[dict]) -> dict[str, list[dict]]:
    """점수대별로 분류"""
    by_score = {
        "high": [],      # 70+
        "medium": [],    # 40-69
        "low": [],       # 0-39
    }
    
    for data in chaining_data:
        score = data.get("total_score")
        if score is None:
            continue
        elif score >= 70:
            by_score["high"].append(data)
        elif score >= 40:
            by_score["medium"].append(data)
        else:
            by_score["low"].append(data)
    
    return by_score


def select_few_shot_examples(chaining_data: list[dict]) -> dict:
    """Few-shot 예시 선정 (점수대별/평가 항목별 대표 예시)"""
    examples = {
        "by_score": {
            "high": [],
            "medium": [],
            "low": []
        },
        "by_criterion": {
            "problem_decomposition": {"high": [], "low": []},
            "feedback_integration": {"high": [], "low": []},
            "strategic_exploration": {"high": [], "low": []}
        },
        "best_examples": []  # 전체적으로 우수한 예시
    }
    
    # 점수대별 예시 선정
    by_score = categorize_by_score(chaining_data)
    for score_level, items in by_score.items():
        # analysis가 명확한 것 우선
        sorted_items = sorted(
            items,
            key=lambda x: (
                len(x.get("analysis", "")),  # analysis 길이
                x.get("total_score", 0)  # 점수
            ),
            reverse=True
        )
        examples["by_score"][score_level] = sorted_items[:5]
    
    # 평가 항목별 예시 선정
    for criterion_name in ["problem_decomposition", "feedback_integration", "strategic_exploration"]:
        # 고점 예시 (해당 항목 점수 70+)
        high_items = [
            data for data in chaining_data
            if data.get("evaluation_criteria", {}).get(criterion_name, {}).get("score", 0) >= 70
        ]
        sorted_high = sorted(
            high_items,
            key=lambda x: (
                len(x.get("evaluation_criteria", {}).get(criterion_name, {}).get("analysis", "")),
                x.get("evaluation_criteria", {}).get(criterion_name, {}).get("score", 0)
            ),
            reverse=True
        )
        examples["by_criterion"][criterion_name]["high"] = sorted_high[:3]
        
        # 저점 예시 (해당 항목 점수 < 40)
        low_items = [
            data for data in chaining_data
            if data.get("evaluation_criteria", {}).get(criterion_name, {}).get("score", 0) < 40
        ]
        sorted_low = sorted(
            low_items,
            key=lambda x: (
                len(x.get("evaluation_criteria", {}).get(criterion_name, {}).get("analysis", "")),
                x.get("total_score", 0)
            ),
            reverse=True
        )
        examples["by_criterion"][criterion_name]["low"] = sorted_low[:3]
    
    # 최고 예시 (전체 점수 70+ 이고 모든 항목이 우수한 것)
    high_score = by_score["high"]
    sorted_best = sorted(
        high_score,
        key=lambda x: (
            sum([
                criterion.get("score", 0)
                for criterion in x.get("evaluation_criteria", {}).values()
                if isinstance(criterion, dict)
            ]),
            len(x.get("analysis", "")),
            x.get("total_score", 0)
        ),
        reverse=True
    )
    examples["best_examples"] = sorted_best[:10]
    
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


def print_statistics(chaining_data: list[dict], cleaned: list[dict]):
    """통계 정보 출력"""
    print("\n" + "=" * 60)
    print("📊 추출 결과 통계")
    print("=" * 60)
    
    print(f"\n📌 전체 Chaining 평가 데이터: {len(chaining_data)}개")
    print(f"   - 정제된 데이터: {len(cleaned)}개")
    
    # 점수대별 분포
    by_score = categorize_by_score(cleaned)
    print(f"\n📌 점수대별 분포:")
    print(f"   - 고점 (70+): {len(by_score['high'])}개")
    print(f"   - 중점 (40-69): {len(by_score['medium'])}개")
    print(f"   - 저점 (0-39): {len(by_score['low'])}개")
    
    # 평가 항목별 평균 점수
    if cleaned:
        problem_decomp_scores = [
            data.get("evaluation_criteria", {}).get("problem_decomposition", {}).get("score")
            for data in cleaned
            if data.get("evaluation_criteria", {}).get("problem_decomposition", {}).get("score") is not None
        ]
        feedback_scores = [
            data.get("evaluation_criteria", {}).get("feedback_integration", {}).get("score")
            for data in cleaned
            if data.get("evaluation_criteria", {}).get("feedback_integration", {}).get("score") is not None
        ]
        strategic_scores = [
            data.get("evaluation_criteria", {}).get("strategic_exploration", {}).get("score")
            for data in cleaned
            if data.get("evaluation_criteria", {}).get("strategic_exploration", {}).get("score") is not None
        ]
        
        print(f"\n📌 평가 항목별 평균 점수:")
        if problem_decomp_scores:
            print(f"   - 문제 분해 (Problem Decomposition): {sum(problem_decomp_scores) / len(problem_decomp_scores):.2f}")
        if feedback_scores:
            print(f"   - 피드백 수용성 (Feedback Integration): {sum(feedback_scores) / len(feedback_scores):.2f}")
        if strategic_scores:
            print(f"   - 전략적 탐색 (Strategic Exploration): {sum(strategic_scores) / len(strategic_scores):.2f}")
    
    # 턴 수 분포
    turn_counts = [data.get("turn_count", 0) for data in cleaned]
    if turn_counts:
        print(f"\n📌 턴 수 분포:")
        print(f"   - 평균: {sum(turn_counts) / len(turn_counts):.2f}턴")
        print(f"   - 최대: {max(turn_counts)}턴")
        print(f"   - 최소: {min(turn_counts)}턴")
    
    # 전체 점수 통계
    scores = [data.get("total_score") for data in cleaned if data.get("total_score") is not None]
    if scores:
        print(f"\n📌 전체 점수 통계:")
        print(f"   - 평균: {sum(scores) / len(scores):.2f}")
        print(f"   - 최고: {max(scores):.2f}")
        print(f"   - 최저: {min(scores):.2f}")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Phase 5-C: Chaining 파인튜닝 데이터 추출"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".maestro/data/finetuning/phase5c_chaining",
        help="출력 디렉토리 (기본값: .maestro/data/finetuning/phase5c_chaining)"
    )
    args = parser.parse_args()
    
    output_dir = Path(project_root) / args.output_dir
    
    print("=" * 60)
    print("🚀 Phase 5-C: Chaining 파인튜닝 데이터 추출")
    print(f"   출력 디렉토리: {output_dir}")
    print("=" * 60)
    
    try:
        # DB 연결
        conn = connect_db()
        
        # 데이터 추출
        chaining_data = extract_chaining_data(conn)
        
        if not chaining_data:
            print("[WARN] 추출된 데이터가 없습니다. DB에 HOLISTIC_FLOW 데이터가 있는지 확인하세요.")
            return
        
        # 데이터 정제
        cleaned = clean_data(chaining_data)
        
        if not cleaned:
            print("[WARN] 정제된 데이터가 없습니다. score, analysis, 평가 항목이 있는 데이터가 필요합니다.")
            return
        
        # 통계 출력
        print_statistics(chaining_data, cleaned)
        
        # 분류
        by_score = categorize_by_score(cleaned)
        
        # 파일 저장
        print("\n📁 파일 저장 중...")
        
        # 1. 전체 Chaining 데이터
        save_jsonl(chaining_data, output_dir / "chaining_data.jsonl")
        
        # 2. 정제된 데이터 (cleaned는 이미 저장됨)
        save_jsonl(cleaned, output_dir / "chaining_cleaned.jsonl")
        
        # 3. 점수대별 분류
        save_jsonl(by_score["high"], output_dir / "chaining_high_score.jsonl")
        save_jsonl(by_score["medium"], output_dir / "chaining_medium_score.jsonl")
        save_jsonl(by_score["low"], output_dir / "chaining_low_score.jsonl")
        
        # 4. Few-shot 예시
        examples = select_few_shot_examples(cleaned)
        save_json(examples, output_dir / "chaining_examples.json")
        
        print("\n✅ Phase 5-C 완료!")
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
