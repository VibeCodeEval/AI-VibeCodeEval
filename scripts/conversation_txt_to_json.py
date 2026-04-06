#!/usr/bin/env python3
"""
평가용_대화.txt 스타일(turnN user:/assistant: + { ... } 블록)을
SaveChatMessageRequest 호환 JSON 배열로 변환합니다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HEADER = re.compile(
    r"(?m)^(turn\s*(\d+)\s+user:|turn\s*(\d+)\s+assistant:|"
    r"turn\s*(\d+)\s+role\s*:\s*user|turn\s*(\d+)\s+role\s*:\s*assistant)\s*",
    re.IGNORECASE,
)


def _turn_from_match(m: re.Match) -> int:
    for g in m.group(2), m.group(3), m.group(4), m.group(5):
        if g is not None:
            return int(g)
    raise ValueError(m.group(0))


def _role_from_header(header_line: str) -> str:
    low = header_line.lower()
    if "assistant" in low:
        return "assistant"
    return "user"


def _extract_brace_block(text: str, start_idx: int) -> tuple[str, int]:
    if start_idx >= len(text) or text[start_idx] != "{":
        raise ValueError("expected `{` at start_idx")
    depth = 0
    i = start_idx
    while i < len(text):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                inner = text[start_idx + 1 : i]
                return inner.strip(), i + 1
        i += 1
    raise ValueError("unclosed `{`")


def parse_transcript(raw: str) -> list[dict]:
    items: list[dict] = []
    pos = 0
    while True:
        m = HEADER.search(raw, pos)
        if not m:
            break
        header_line = m.group(1)
        turn = _turn_from_match(m)
        role = _role_from_header(header_line)
        j = m.end()
        while j < len(raw) and raw[j] in " \t\r\n":
            j += 1
        if j >= len(raw) or raw[j] != "{":
            pos = m.end() + 1
            continue
        content, next_pos = _extract_brace_block(raw, j)
        items.append({"turn": turn, "role": role, "content": content})
        pos = next_pos
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path, help="평가용_대화.txt")
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument("--exam-id", type=int, default=1)
    ap.add_argument("--participant-id", type=int, default=1)
    args = ap.parse_args()
    raw = args.input.read_text(encoding="utf-8")
    if not raw.strip():
        print("입력 파일이 비어 있습니다. 에디터에서 저장 후 다시 실행하세요.", file=sys.stderr)
        return 2
    items = parse_transcript(raw)
    for d in items:
        d["examId"] = args.exam_id
        d["participantId"] = args.participant_id
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {len(items)} messages -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
