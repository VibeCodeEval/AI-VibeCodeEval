#!/usr/bin/env python
"""
v2.1 파인튜닝 데이터 생성 — LLM 재작성(Paraphrasing) 필수 버전.

- 기존 generate_synthetic_v21_data.py 와 동일한 Seed & Mutate 구조.
- instruction 생성 시 **템플릿 반복이 아닌, 반드시 LLM(Gemini) 호출**로 매번 새 문장 생성.
- Paraphrasing 프롬프트: 의도 유지 + 말투/단어/문장 구조 변경 (급한 성격, 공손하게, 오타 섞인 등).
- temperature=0.9 로 다양성 확보.
- 생성된 instruction이 이전과 100% 일치하면 재생성(Retry, 최대 3회).

출력 기본값: data/v21_finetuning_dataset_paraphrased.jsonl (기존 파일과 별도)

사용법:
  uv run python scripts/generate_synthetic_v21_data_paraphrase.py
  uv run python scripts/generate_synthetic_v21_data_paraphrase.py -o data/v21_finetuning_dataset_paraphrased.jsonl --per-grade 20
"""

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path
from typing import Any

project_root = Path(__file__).resolve().parent.parent
scripts_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(scripts_dir))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

# 기존 스크립트의 상수·헬퍼 재사용 (SEED_CODES 등은 그대로)
import generate_synthetic_v21_data as base

# -----------------------------------------------------------------------------
# Paraphrasing 전용: 문체 힌트 (의도 유지, 말투만 완전히 다르게)
# -----------------------------------------------------------------------------
PARAPHRASE_STYLE_HINTS: list[str] = [
    "급한 성격처럼 짧고 직설적으로 바꿔줘.",
    "아주 공손하고 격식 있게 바꿔줘.",
    "오타가 1~2개 섞인 문장으로 변형해줘 (예: 해줘→해주에, 넣어줘→넣어주어).",
    "구어체·반말 톤으로 편하게 바꿔줘.",
    "요약하듯 한두 문장으로 압축해서 바꿔줘.",
    "설명을 보강해서 조금 더 구체적으로 바꿔줘.",
    "비슷한 뜻의 다른 단어로만 바꿔서 문장 구조를 유지해줘.",
    "문장 순서를 바꾸고 접속어를 다르게 써줘.",
    "업무 메모 스타일로 간결하게 바꿔줘.",
    "질문형으로 끝나도록 바꿔줘 (예: ~해줄 수 있어?).",
]

MAX_DEDUP_RETRIES = 3


def _get_llm_paraphrase():
    """재작성용 LLM: temperature=0.9 로 매번 다른 결과."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    from app.core.config import settings
    api_key = getattr(settings, "GEMINI_API_KEY", None)
    if not api_key:
        return None
    model = getattr(settings, "DEFAULT_LLM_MODEL", "gemini-2.5-flash")
    if "flash" not in model.lower():
        model = "gemini-2.5-flash"
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=api_key,
        temperature=0.9,
        max_output_tokens=1024,
    )


def _parse_instruction_from_response(text: str) -> list[str] | None:
    """응답에서 JSON 배열만 추출해 instruction 리스트 반환."""
    start = text.find("[")
    end = text.rfind("]") + 1
    if start < 0 or end <= start:
        return None
    try:
        arr = json.loads(text[start:end])
        if isinstance(arr, list) and all(isinstance(x, str) for x in arr):
            return [str(x).strip() for x in arr if str(x).strip()]
    except Exception:
        pass
    return None


async def generate_instruction_with_paraphrase(
    grade: str,
    variant_index: int,
    sem: asyncio.Semaphore,
    seen_instructions: set[tuple[str, ...]],
    lock: asyncio.Lock,
) -> list[str] | None:
    """
    LLM을 반드시 호출해서 원문(시드 템플릿)을 재작성.
    - 의도 유지, 말투/단어/문장 구조를 다르게.
    - 반환된 instruction이 이미 seen에 있으면 None (재시도 유도).
    """
    llm = _get_llm_paraphrase()
    if not llm:
        return None

    templates = base.GRADE_INSTRUCTION_TEMPLATES.get(grade, base.GRADE_INSTRUCTION_TEMPLATES["C"])
    seed = list(templates[variant_index % len(templates)])
    style_hint = random.choice(PARAPHRASE_STYLE_HINTS)

    system = (
        "당신은 지시문 재작성(Paraphrasing) 전문가입니다. "
        "**의도(Intent)는 반드시 유지**하되, 말투, 단어 선택, 문장 구조를 **완전히 다르게** 바꿔줘. "
        "스마트 게이트 2026 도메인(여권/항공편/수하물, threat_level HIGH→SECURITY_CHECK, 과금 3명→-5kg 등)은 그대로 두고, 표현만 바꿔줘."
    )
    user = (
        f"아래 지시문(여러 턴)을 재작성해줘. 이번에는 다음 스타일로: {style_hint}\n\n"
        f"원문 (JSON 배열): {json.dumps(seed, ensure_ascii=False)}\n\n"
        "반드시 **한 줄 JSON 배열만** 출력해줘. 예: [\"Phase1 요청\", \"SAVE\", \"Phase2 요청1\", \"Phase2 요청2\"]"
    )

    async with sem:
        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, lambda: llm.invoke(system + "\n\n" + user))
            text = resp.content if hasattr(resp, "content") else str(resp)
        except Exception:
            return None

    instruction = _parse_instruction_from_response(text)
    if not instruction or "SAVE" not in instruction:
        return None

    key = tuple(instruction)
    async with lock:
        if key in seen_instructions:
            return None
        seen_instructions.add(key)
    return instruction


async def generate_data_entry_paraphrase(
    grade: str,
    variant_index: int,
    sem: asyncio.Semaphore,
    seen_instructions: set[tuple[str, ...]],
    lock: asyncio.Lock,
) -> dict[str, Any]:
    """한 건 생성: LLM 재작성으로 instruction 생성 (중복 시 재시도), 나머지는 기존 로직."""
    instruction: list[str] | None = None
    for _ in range(MAX_DEDUP_RETRIES):
        instruction = await generate_instruction_with_paraphrase(
            grade, variant_index, sem, seen_instructions, lock
        )
        if instruction is not None:
            break

    if instruction is None:
        instruction = base.get_instruction_template_fallback(grade, variant_index)
        instruction[0] = instruction[0] + f" (재시도 {MAX_DEDUP_RETRIES}회 초과)"

    context, v2_code = base.get_seed_for_grade(grade)
    metrics, evaluation_log = await base.generate_mock_reasoning(grade, instruction, sem)

    return {
        "instruction": instruction,
        "context": context,
        "v2_code": v2_code,
        "metrics": metrics,
        "label": grade,
        "evaluation_log": evaluation_log,
    }


async def run_async_batch_paraphrase(
    per_grade: int,
    sem_limit: int = 10,
) -> list[dict[str, Any]]:
    """등급별 per_grade건씩 생성. instruction은 전부 LLM 재작성 + 중복 시 재시도."""
    total_entries = per_grade * 5
    total_calls = total_entries * 2  # 한 건당 API 2회: instruction + reasoning
    print(f"[INFO] 총 {total_entries}건 예정, API 호출 약 {total_calls}회 (동시 {sem_limit}개 제한). 한 건당 2회 호출이라 진행률 1당 약 2회 응답 대기.")
    sem = asyncio.Semaphore(sem_limit)
    seen_instructions: set[tuple[str, ...]] = set()
    lock = asyncio.Lock()

    grades = ["A", "B", "C", "D", "F"]
    task_specs = [(g, i) for g in grades for i in range(per_grade)]
    total = len(task_specs)

    async def one_with_progress(g: str, i: int, stagger_sec: float):
        await asyncio.sleep(stagger_sec)
        rec = await generate_data_entry_paraphrase(g, i, sem, seen_instructions, lock)
        pbar.update(1)
        return rec

    pbar = tqdm(total=total, desc="생성 중(Paraphrase)", unit="건")
    # 시작 시점을 0.15초씩 흩어서 동시 요청 폭주 방지 → 500/재시도 감소, 체감 속도 개선
    stagger = 0.15
    tasks = [one_with_progress(g, i, idx * stagger) for idx, (g, i) in enumerate(task_specs)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    pbar.close()

    out = []
    for k, r in enumerate(results):
        if isinstance(r, Exception):
            g, i = task_specs[k]
            out.append(await generate_data_entry_paraphrase(g, i, sem, seen_instructions, lock))
            tqdm.write(f"[WARN] 1건 실패 후 재시도: {r}")
        else:
            out.append(r)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="v2.1 파인튜닝 데이터 생성 (LLM 재작성 필수, 진짜 다양성)"
    )
    parser.add_argument(
        "-o", "--output",
        default="data/v21_finetuning_dataset_paraphrased.jsonl",
        help="출력 JSONL 경로 (기본: data/v21_finetuning_dataset_paraphrased.jsonl)",
    )
    parser.add_argument("--per-grade", type=int, default=20, help="등급당 생성 건수 (기본 20 → 총 100건)")
    parser.add_argument("--semaphore", type=int, default=10, help="동시 API 호출 수 (기본 10)")
    args = parser.parse_args()

    out_path = Path(args.output)
    if not out_path.is_absolute():
        out_path = (Path.cwd() / out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from app.core.config import settings
        if not getattr(settings, "GEMINI_API_KEY", None):
            print("[ERROR] GEMINI_API_KEY가 필요합니다. 이 스크립트는 LLM 재작성을 위해 API 호출이 필수입니다.")
            sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 설정 로드 실패: {e}")
        sys.exit(1)

    records = asyncio.run(run_async_batch_paraphrase(args.per_grade, args.semaphore))

    with open(out_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"[INFO] 총 {len(records)}건 저장 (LLM 재작성): {out_path}")


if __name__ == "__main__":
    main()
