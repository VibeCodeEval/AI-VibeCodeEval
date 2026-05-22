"""Judge0Client batch/단건 분기 및 결과 매핑 단위 테스트."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.judge0.client import Judge0Client


def test_map_judge0_result_passed():
    client = Judge0Client()
    tc = {"input": "1", "expected": "2"}
    raw = {
        "stdout": "2\n",
        "status_id": 3,
        "time": "0.01",
        "memory": "1024",
    }
    mapped = client._map_judge0_result_to_test_case(tc, 0, raw)
    assert mapped["passed"] is True
    assert mapped["time"] == "0.01"
    assert mapped["memory"] == "1024"


def test_map_judge0_result_wrong_answer():
    client = Judge0Client()
    tc = {"input": "1", "expected": "99"}
    raw = {"stdout": "2", "status_id": 3}
    mapped = client._map_judge0_result_to_test_case(tc, 1, raw)
    assert mapped["passed"] is False
    assert mapped["test_case_index"] == 1


@pytest.mark.asyncio
async def test_execute_test_cases_routes_single():
    client = Judge0Client()
    with patch.object(
        client, "_execute_single_test_case", new_callable=AsyncMock
    ) as mock_single:
        mock_single.return_value = {"passed": True, "test_case_index": 0}
        out = await client.execute_test_cases(
            code="print(1)",
            language="python",
            test_cases=[{"input": "", "expected": "1"}],
        )
        mock_single.assert_awaited_once()
        assert len(out) == 1


@pytest.mark.asyncio
async def test_execute_test_cases_routes_batch():
    client = Judge0Client()
    tcs = [
        {"input": "1", "expected": "1"},
        {"input": "2", "expected": "2"},
    ]
    with patch.object(
        client, "_execute_test_cases_batch_chunk", new_callable=AsyncMock
    ) as mock_batch:
        mock_batch.return_value = [
            {"passed": True, "test_case_index": 0},
            {"passed": True, "test_case_index": 1},
        ]
        out = await client.execute_test_cases(
            code="print(input())",
            language="python",
            test_cases=tcs,
        )
        mock_batch.assert_awaited_once()
        assert len(out) == 2
        assert out[0]["test_case_index"] == 0
        assert out[1]["test_case_index"] == 1


@pytest.mark.asyncio
async def test_execute_test_cases_batch_chunk_maps_worker_fields():
    client = Judge0Client()
    tcs = [{"input": "5", "expected": "10"}, {"input": "3", "expected": "6"}]

    with patch.object(
        client,
        "submit_batch",
        new_callable=AsyncMock,
        return_value=["tok-a", "tok-b"],
    ), patch.object(
        client,
        "wait_for_batch_results",
        new_callable=AsyncMock,
        return_value={
            "tok-a": {"stdout": "10", "status_id": 3, "time": "0.05", "memory": "2048"},
            "tok-b": {"stdout": "6", "status_id": 3, "time": "0.08", "memory": "3072"},
        },
    ):
        results = await client._execute_test_cases_batch_chunk(
            code="n=int(input());print(n*2)",
            language="python",
            test_cases=tcs,
            global_index_offset=0,
            cpu_time_limit=5,
            memory_limit=128,
        )

    assert len(results) == 2
    assert results[0]["passed"] is True
    assert results[0]["time"] == "0.05"
    assert results[1]["passed"] is True
    assert results[1]["memory"] == "3072"


@pytest.mark.asyncio
async def test_submit_batch_parses_tokens():
    client = Judge0Client()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = [{"token": "a"}, {"token": "b"}]
    client.client = MagicMock()
    client.client.post = AsyncMock(return_value=mock_response)

    tokens = await client.submit_batch(
        code="x",
        language="python",
        test_cases=[{"input": "", "expected": ""}, {"input": "1", "expected": "1"}],
    )
    assert tokens == ["a", "b"]
    call_kwargs = client.client.post.call_args
    assert "/submissions/batch" in call_kwargs[0][0]
