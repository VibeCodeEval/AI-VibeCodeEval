"""Judge0 Base64 인코딩/디코딩 유틸."""

import base64

from app.infrastructure.judge0.utils import (
    judge0_decode_submission_result,
    judge0_decode_text,
    judge0_encode_submission_payload,
    judge0_encode_text,
)


def test_judge0_encode_decode_roundtrip():
    raw = "print('한글\\n\\t제어\\x00문자')"
    enc = judge0_encode_text(raw)
    assert enc != raw
    assert judge0_decode_text(enc) == raw


def test_judge0_encode_submission_payload():
    payload = {
        "source_code": "print(1)",
        "stdin": "42\n",
        "expected_output": "42\n",
        "language_id": 71,
    }
    enc = judge0_encode_submission_payload(payload)
    assert enc["language_id"] == 71
    assert judge0_decode_text(enc["source_code"]) == "print(1)"
    assert judge0_decode_text(enc["stdin"]) == "42\n"


def test_judge0_decode_submission_result_plain_stdout():
    plain = "Hello\n"
    encoded = base64.b64encode(plain.encode()).decode()
    out = judge0_decode_submission_result(
        {
            "stdout": encoded,
            "stderr": None,
            "compile_output": "",
            "time": "0.01",
        }
    )
    assert out["stdout"] == plain


def test_judge0_decode_invalid_base64_returns_empty_or_safe():
    assert judge0_decode_text("!!!not-valid-base64!!!") == ""
