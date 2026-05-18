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


def test_parse_judge_time_and_memory_null_safe():
    from app.infrastructure.judge0.utils import (
        parse_judge_memory_kb,
        parse_judge_time_seconds,
    )

    assert parse_judge_time_seconds(None) is None
    assert parse_judge_time_seconds("0.015") == 0.015
    assert parse_judge_memory_kb(None) is None
    assert parse_judge_memory_kb("4096") == 4096


def test_is_blank_submission_code():
    from app.infrastructure.judge0.utils import is_blank_submission_code

    assert is_blank_submission_code(None) is True
    assert is_blank_submission_code("") is True
    assert is_blank_submission_code("   \n\t  ") is True
    assert is_blank_submission_code("print(1)") is False


def test_resolve_judge0_language_normalizes_api_values():
    from app.infrastructure.judge0.utils import resolve_judge0_language

    assert resolve_judge0_language("python3.11") == "python"
    assert resolve_judge0_language("java") == "java"
    assert resolve_judge0_language("C++") == "cpp"
    assert resolve_judge0_language(None) == "python"


def test_judge0_client_language_id_rapidapi_mapping():
    from app.infrastructure.judge0.client import Judge0Client

    client = Judge0Client(api_url="http://localhost:2358", use_rapidapi=False)
    assert client._get_language_id("java") == 62
    assert client._get_language_id("python3") == 71
    assert client._get_language_id("cpp") == 54
