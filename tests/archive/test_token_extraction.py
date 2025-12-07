"""
LLM 응답 객체에서 토큰 사용량 추출 테스트
"""
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.config import settings

async def test_llm_response_structure():
    """LLM 응답 객체 구조 확인"""
    llm = ChatGoogleGenerativeAI(
        model=settings.DEFAULT_LLM_MODEL,
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.7,
    )
    
    messages = [
        SystemMessage(content="You are a helpful assistant."),
        HumanMessage(content="Say hello in one sentence.")
    ]
    
    response = await llm.ainvoke(messages)
    
    print(f"Response type: {type(response)}")
    print(f"Response dir: {[attr for attr in dir(response) if not attr.startswith('_')][:20]}")
    print(f"\nResponse attributes:")
    print(f"  - content: {response.content[:50]}...")
    print(f"  - response_metadata: {response.response_metadata}")
    print(f"  - usage_metadata: {getattr(response, 'usage_metadata', 'N/A')}")
    
    if response.response_metadata:
        print(f"\nresponse_metadata keys: {list(response.response_metadata.keys())}")
        if "usage_metadata" in response.response_metadata:
            usage = response.response_metadata["usage_metadata"]
            print(f"usage_metadata: {usage}")
            print(f"usage_metadata type: {type(usage)}")
            if hasattr(usage, '__dict__'):
                print(f"usage_metadata __dict__: {usage.__dict__}")
    
    # 토큰 추출 테스트
    from app.domain.langgraph.utils.token_tracking import extract_token_usage
    tokens = extract_token_usage(response)
    print(f"\nExtracted tokens: {tokens}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_llm_response_structure())


