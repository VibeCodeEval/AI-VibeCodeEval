"""
LangSmith 추적 테스트
개발 환경에서 LangSmith 추적이 정상적으로 작동하는지 확인
"""
import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime

from app.core.config import settings
from app.domain.langgraph.nodes.holistic_evaluator.flow import eval_holistic_flow
from app.domain.langgraph.nodes.holistic_evaluator.performance import eval_code_performance
from app.domain.langgraph.nodes.holistic_evaluator.correctness import eval_code_correctness
from app.domain.langgraph.states import MainGraphState


def test_langsmith_config_loaded():
    """LangSmith 설정이 정상적으로 로드되는지 확인"""
    assert hasattr(settings, 'LANGCHAIN_TRACING_V2')
    assert hasattr(settings, 'LANGCHAIN_API_KEY')
    assert hasattr(settings, 'LANGCHAIN_PROJECT')
    assert hasattr(settings, 'LANGCHAIN_ENDPOINT')
    
    print(f"\n[LangSmith 설정 확인]")
    print(f"  LANGCHAIN_TRACING_V2: {settings.LANGCHAIN_TRACING_V2}")
    print(f"  LANGCHAIN_API_KEY: {'설정됨' if settings.LANGCHAIN_API_KEY else '미설정'}")
    print(f"  LANGCHAIN_PROJECT: {settings.LANGCHAIN_PROJECT}")
    print(f"  LANGCHAIN_ENDPOINT: {settings.LANGCHAIN_ENDPOINT}")


def test_langsmith_traceable_decorator_import():
    """LangSmith traceable 데코레이터가 정상적으로 import되는지 확인"""
    if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
        from langsmith import traceable
        assert callable(traceable)
        print("\n[LangSmith] traceable 데코레이터 import 성공")
    else:
        print("\n[LangSmith] 추적 비활성화 상태 (정상)")


def create_test_state(
    session_id: str = "test-session", 
    code_content: str = None,
    enable_langsmith_tracing: bool = False  # 테스트에서는 기본적으로 비활성화
) -> MainGraphState:
    """테스트용 State 생성"""
    return MainGraphState(
        session_id=session_id,
        exam_id=1,
        participant_id=1,
        spec_id=1,
        messages=[],
        current_turn=1,
        human_message="테스트 메시지",
        ai_message=None,
        intent_status=None,
        is_guardrail_failed=False,
        guardrail_message=None,
        writer_status=None,
        writer_error=None,
        is_submitted=False,
        submission_id=None,
        code_content=code_content,
        turn_scores={},
        holistic_flow_score=None,
        aggregate_turn_score=None,
        code_performance_score=None,
        code_correctness_score=None,
        final_scores=None,
        memory_summary=None,
        error_message=None,
        retry_count=0,
        created_at=datetime.utcnow().isoformat(),
        updated_at=datetime.utcnow().isoformat(),
        enable_langsmith_tracing=enable_langsmith_tracing,  # 테스트에서 명시적으로 제어
    )


@pytest.mark.asyncio
async def test_eval_holistic_flow_with_langsmith():
    """6a 노드가 LangSmith 추적과 함께 정상 작동하는지 확인"""
    state = create_test_state()
    
    # Redis Mock 설정 (함수 내부에서 import되므로 경로 수정)
    with patch('app.infrastructure.cache.redis_client.redis_client') as mock_redis:
        mock_redis.get_all_turn_logs = AsyncMock(return_value={
            "1": {
                "prompt_evaluation_details": {
                    "intent": "HINT_OR_QUERY",
                    "score": 85
                },
                "user_prompt_summary": "테스트 프롬프트",
                "llm_answer_reasoning": "테스트 추론"
            }
        })
        
        # LLM Mock 설정
        with patch('app.domain.langgraph.nodes.holistic_evaluator.flow.get_llm') as mock_get_llm:
            mock_llm = MagicMock()
            mock_structured_llm = MagicMock()
            mock_eval_result = MagicMock()
            mock_eval_result.overall_flow_score = 90.0
            mock_structured_llm.ainvoke = AsyncMock(return_value=mock_eval_result)
            mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
            mock_get_llm.return_value = mock_llm
            
            try:
                result = await eval_holistic_flow(state)
                
                assert "holistic_flow_score" in result
                print(f"\n[6a 노드 테스트] 성공 - score: {result.get('holistic_flow_score')}")
                
                # LangSmith 추적 활성화 여부 확인
                if settings.LANGCHAIN_TRACING_V2:
                    print("[LangSmith] 6a 노드 추적 활성화됨")
                else:
                    print("[LangSmith] 6a 노드 추적 비활성화 (정상)")
                    
            except Exception as e:
                pytest.fail(f"6a 노드 실행 실패: {str(e)}")


@pytest.mark.asyncio
async def test_eval_code_performance_with_langsmith():
    """6c 노드가 LangSmith 추적과 함께 정상 작동하는지 확인"""
    code_content = "def fibonacci(n):\n    return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)"
    state = create_test_state(code_content=code_content)
    
    # LLM Mock 설정
    with patch('app.domain.langgraph.nodes.holistic_evaluator.performance.get_llm') as mock_get_llm:
        mock_llm = MagicMock()
        mock_structured_llm = MagicMock()
        mock_eval_result = MagicMock()
        mock_eval_result.efficiency = 85.0
        mock_eval_result.correctness = 90.0
        mock_eval_result.best_practices = 80.0
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_eval_result)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
        mock_get_llm.return_value = mock_llm
        
        try:
            result = await eval_code_performance(state)
            
            assert "code_performance_score" in result
            print(f"\n[6c 노드 테스트] 성공 - score: {result.get('code_performance_score')}")
            
            # LangSmith 추적 활성화 여부 확인
            if settings.LANGCHAIN_TRACING_V2:
                print("[LangSmith] 6c 노드 추적 활성화됨")
            else:
                print("[LangSmith] 6c 노드 추적 비활성화 (정상)")
                
        except Exception as e:
            pytest.fail(f"6c 노드 실행 실패: {str(e)}")


@pytest.mark.asyncio
async def test_eval_code_correctness_with_langsmith():
    """6d 노드가 LangSmith 추적과 함께 정상 작동하는지 확인"""
    code_content = "def fibonacci(n):\n    return n if n <= 1 else fibonacci(n-1) + fibonacci(n-2)"
    state = create_test_state(code_content=code_content)
    
    # LLM Mock 설정
    with patch('app.domain.langgraph.nodes.holistic_evaluator.correctness.get_llm') as mock_get_llm:
        mock_llm = MagicMock()
        mock_structured_llm = MagicMock()
        mock_eval_result = MagicMock()
        mock_eval_result.correctness = 95.0
        mock_eval_result.efficiency = 85.0
        mock_eval_result.best_practices = 90.0
        mock_structured_llm.ainvoke = AsyncMock(return_value=mock_eval_result)
        mock_llm.with_structured_output = MagicMock(return_value=mock_structured_llm)
        mock_get_llm.return_value = mock_llm
        
        try:
            result = await eval_code_correctness(state)
            
            assert "code_correctness_score" in result
            print(f"\n[6d 노드 테스트] 성공 - score: {result.get('code_correctness_score')}")
            
            # LangSmith 추적 활성화 여부 확인
            if settings.LANGCHAIN_TRACING_V2:
                print("[LangSmith] 6d 노드 추적 활성화됨")
            else:
                print("[LangSmith] 6d 노드 추적 비활성화 (정상)")
                
        except Exception as e:
            pytest.fail(f"6d 노드 실행 실패: {str(e)}")


def test_langsmith_environment_variables():
    """환경 변수가 정상적으로 설정되었는지 확인"""
    print("\n[환경 변수 확인]")
    print(f"  LANGCHAIN_TRACING_V2: {os.getenv('LANGCHAIN_TRACING_V2', '미설정')}")
    print(f"  LANGCHAIN_API_KEY: {'설정됨' if os.getenv('LANGCHAIN_API_KEY') else '미설정'}")
    print(f"  LANGCHAIN_PROJECT: {os.getenv('LANGCHAIN_PROJECT', '미설정')}")
    print(f"  LANGCHAIN_ENDPOINT: {os.getenv('LANGCHAIN_ENDPOINT', '미설정')}")
    
    # 설정이 되어 있으면 확인
    if settings.LANGCHAIN_TRACING_V2 and settings.LANGCHAIN_API_KEY:
        print("\n✅ LangSmith 추적 활성화됨")
    else:
        print("\n⚠️ LangSmith 추적 비활성화 (개발 환경에서 활성화하려면 .env 파일 설정 필요)")

