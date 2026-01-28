#!/usr/bin/env python
"""
Phase 5-A: 응답 파인튜닝 데이터 추출 스크립트

사용자 프롬프트와 AI 응답 쌍을 추출하여 Writer LLM 응답 품질 개선에 활용합니다.

출력 파일:
- response_pairs.jsonl      : 전체 문답 데이터
- response_normal.jsonl     : 정상 응답 (is_guardrail_failed = false)
- response_guardrail.jsonl  : 가드레일 응답 (is_guardrail_failed = true)
- response_examples.json    : Few-shot 예시 (전략별/의도별 대표 응답)

사용법:
    python scripts/extract_response_pairs.py
    python scripts/extract_response_pairs.py --output-dir ./custom_output
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
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


# SQL 쿼리: USER + AI 쌍 추출
# 참고: DB에서 role은 'USER'/'user'(사용자)와 'AI'(응답)로 구분됨
EXTRACT_RESPONSE_PAIRS_SQL = """
SET search_path TO ai_vibe_coding_test;

SELECT 
    pm_user.session_id,
    pm_user.turn,
    pm_user.content AS user_prompt,
    pm_ai.content AS ai_response,
    pm_user.created_at,
    pe.details->>'intent' AS intent,
    pe.details->>'guide_strategy' AS guide_strategy,
    pe.details->>'is_guardrail_failed' AS is_guardrail_failed,
    pe.details->>'score' AS eval_score,
    pe.details->>'ai_summary' AS ai_summary,
    pe.details AS full_details
FROM ai_vibe_coding_test.prompt_messages pm_user
JOIN ai_vibe_coding_test.prompt_messages pm_ai 
    ON pm_user.session_id = pm_ai.session_id 
    AND pm_user.turn + 1 = pm_ai.turn
LEFT JOIN ai_vibe_coding_test.prompt_evaluations pe 
    ON pm_user.session_id = pe.session_id 
    AND pm_user.turn = pe.turn
    AND pe.evaluation_type = 'TURN_EVAL'
WHERE UPPER(pm_user.role) = 'USER' 
    AND UPPER(pm_ai.role) = 'AI'
ORDER BY pm_user.session_id, pm_user.turn;
"""


def extract_response_pairs(conn) -> list[dict[str, Any]]:
    """DB에서 응답 쌍 추출"""
    print("[INFO] 응답 쌍 데이터 추출 중...")
    
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(EXTRACT_RESPONSE_PAIRS_SQL)
        rows = cur.fetchall()
    
    results = []
    for row in rows:
        # JSON 필드 파싱
        is_guardrail_failed = row.get("is_guardrail_failed")
        if isinstance(is_guardrail_failed, str):
            is_guardrail_failed = is_guardrail_failed.lower() == "true"
        elif is_guardrail_failed is None:
            is_guardrail_failed = False
        
        eval_score = row.get("eval_score")
        if eval_score is not None:
            try:
                eval_score = float(eval_score)
            except (ValueError, TypeError):
                eval_score = None
        
        # 출력 레코드 구성
        record = {
            "id": f"resp_{row['session_id']}_{row['turn']}",
            "user_prompt": row["user_prompt"],
            "ai_response": row["ai_response"],
            "intent": row.get("intent"),
            "guide_strategy": row.get("guide_strategy"),
            "is_guardrail_failed": is_guardrail_failed,
            "eval_score": eval_score,
            "ai_summary": row.get("ai_summary"),
            "metadata": {
                "session_id": row["session_id"],
                "turn": row["turn"],
                "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
            }
        }
        results.append(record)
    
    print(f"[INFO] 총 {len(results)}개의 응답 쌍 추출 완료")
    return results


def categorize_responses(responses: list[dict]) -> dict[str, list[dict]]:
    """응답 데이터를 가드레일/정상 응답으로 분류"""
    categorized = {
        "normal": [],
        "guardrail": [],
    }
    
    for resp in responses:
        if resp.get("is_guardrail_failed"):
            categorized["guardrail"].append(resp)
        else:
            categorized["normal"].append(resp)
    
    print(f"[INFO] 분류 결과: 정상 응답 {len(categorized['normal'])}개, 가드레일 응답 {len(categorized['guardrail'])}개")
    return categorized


def categorize_by_intent(responses: list[dict]) -> dict[str, list[dict]]:
    """의도별로 분류"""
    by_intent = defaultdict(list)
    for resp in responses:
        intent = resp.get("intent") or "UNKNOWN"
        by_intent[intent].append(resp)
    return dict(by_intent)


def categorize_by_strategy(responses: list[dict]) -> dict[str, list[dict]]:
    """전략별로 분류"""
    by_strategy = defaultdict(list)
    for resp in responses:
        strategy = resp.get("guide_strategy") or "UNKNOWN"
        by_strategy[strategy].append(resp)
    return dict(by_strategy)


def categorize_by_score(responses: list[dict]) -> dict[str, list[dict]]:
    """점수대별로 분류"""
    by_score = {
        "high": [],      # 70+
        "medium": [],    # 40-69
        "low": [],       # 0-39
        "unknown": [],   # None
    }
    
    for resp in responses:
        score = resp.get("eval_score")
        if score is None:
            by_score["unknown"].append(resp)
        elif score >= 70:
            by_score["high"].append(resp)
        elif score >= 40:
            by_score["medium"].append(resp)
        else:
            by_score["low"].append(resp)
    
    return by_score


def select_few_shot_examples(responses: list[dict], categorized: dict) -> dict:
    """Few-shot 예시 선정 (의도별/전략별 대표 응답)"""
    examples = {
        "by_intent": {},
        "by_strategy": {},
        "guardrail_examples": [],
        "high_score_examples": [],
    }
    
    # 의도별 예시 선정 (각 의도당 최대 3개)
    by_intent = categorize_by_intent(categorized["normal"])
    for intent, items in by_intent.items():
        # 점수 높은 순 정렬
        sorted_items = sorted(
            [i for i in items if i.get("eval_score") is not None],
            key=lambda x: x.get("eval_score", 0),
            reverse=True
        )
        examples["by_intent"][intent] = sorted_items[:3]
    
    # 전략별 예시 선정 (각 전략당 최대 3개)
    by_strategy = categorize_by_strategy(categorized["normal"])
    for strategy, items in by_strategy.items():
        sorted_items = sorted(
            [i for i in items if i.get("eval_score") is not None],
            key=lambda x: x.get("eval_score", 0),
            reverse=True
        )
        examples["by_strategy"][strategy] = sorted_items[:3]
    
    # 가드레일 응답 예시 (최대 5개)
    examples["guardrail_examples"] = categorized["guardrail"][:5]
    
    # 고점 응답 예시 (점수 70+ 중 최대 5개)
    by_score = categorize_by_score(categorized["normal"])
    examples["high_score_examples"] = by_score["high"][:5]
    
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


def print_statistics(responses: list[dict], categorized: dict):
    """통계 정보 출력"""
    print("\n" + "=" * 60)
    print("📊 추출 결과 통계")
    print("=" * 60)
    
    print(f"\n📌 전체 응답 쌍: {len(responses)}개")
    print(f"   - 정상 응답: {len(categorized['normal'])}개")
    print(f"   - 가드레일 응답: {len(categorized['guardrail'])}개")
    
    # 의도별 분포
    by_intent = categorize_by_intent(responses)
    print(f"\n📌 의도별 분포:")
    for intent, items in sorted(by_intent.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"   - {intent}: {len(items)}개")
    
    # 전략별 분포
    by_strategy = categorize_by_strategy(categorized["normal"])
    print(f"\n📌 전략별 분포 (정상 응답):")
    for strategy, items in sorted(by_strategy.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"   - {strategy}: {len(items)}개")
    
    # 점수대별 분포
    by_score = categorize_by_score(responses)
    print(f"\n📌 점수대별 분포:")
    print(f"   - 고점 (70+): {len(by_score['high'])}개")
    print(f"   - 중점 (40-69): {len(by_score['medium'])}개")
    print(f"   - 저점 (0-39): {len(by_score['low'])}개")
    print(f"   - 평가 없음: {len(by_score['unknown'])}개")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Phase 5-A: 응답 파인튜닝 데이터 추출"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".maestro/data/finetuning/phase5a_response",
        help="출력 디렉토리 (기본값: .maestro/data/finetuning/phase5a_response)"
    )
    args = parser.parse_args()
    
    output_dir = Path(project_root) / args.output_dir
    
    print("=" * 60)
    print("🚀 Phase 5-A: 응답 파인튜닝 데이터 추출")
    print(f"   출력 디렉토리: {output_dir}")
    print("=" * 60)
    
    try:
        # DB 연결
        conn = connect_db()
        
        # 데이터 추출
        responses = extract_response_pairs(conn)
        
        if not responses:
            print("[WARN] 추출된 데이터가 없습니다. DB에 데이터가 있는지 확인하세요.")
            return
        
        # 분류
        categorized = categorize_responses(responses)
        
        # 통계 출력
        print_statistics(responses, categorized)
        
        # 파일 저장
        print("\n📁 파일 저장 중...")
        
        # 1. 전체 응답 쌍
        save_jsonl(responses, output_dir / "response_pairs.jsonl")
        
        # 2. 정상 응답
        save_jsonl(categorized["normal"], output_dir / "response_normal.jsonl")
        
        # 3. 가드레일 응답
        save_jsonl(categorized["guardrail"], output_dir / "response_guardrail.jsonl")
        
        # 4. Few-shot 예시
        examples = select_few_shot_examples(responses, categorized)
        save_json(examples, output_dir / "response_examples.json")
        
        # 5. 점수대별 분류 (추가)
        by_score = categorize_by_score(categorized["normal"])
        save_jsonl(by_score["high"], output_dir / "response_high_score.jsonl")
        save_jsonl(by_score["medium"], output_dir / "response_medium_score.jsonl")
        save_jsonl(by_score["low"], output_dir / "response_low_score.jsonl")
        
        print("\n✅ Phase 5-A 완료!")
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
