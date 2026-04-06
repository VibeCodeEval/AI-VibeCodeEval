"""data/conv_turn*.txt 6개를 SaveChatMessageRequest 형식 JSON으로 합칩니다."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = [
    (1, "user", "conv_turn1_user.txt"),
    (1, "assistant", "conv_turn1_assistant.txt"),
    (2, "user", "conv_turn2_user.txt"),
    (2, "assistant", "conv_turn2_assistant.txt"),
    (3, "user", "conv_turn3_user.txt"),
    (3, "assistant", "conv_turn3_assistant.txt"),
]


def main() -> None:
    out = []
    for turn, role, name in PARTS:
        text = (ROOT / "data" / name).read_text(encoding="utf-8").strip()
        out.append(
            {
                "examId": 1,
                "participantId": 1,
                "turn": turn,
                "role": role,
                "content": text,
            }
        )
    dest = ROOT / "data" / "평가용_대화_3turns.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(dest, len(out), "messages")


if __name__ == "__main__":
    main()
