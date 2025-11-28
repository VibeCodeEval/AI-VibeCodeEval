"""Gemini API 테스트"""
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

async def test_gemini():
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=os.getenv("GEMINI_API_KEY"),
            temperature=0.7,
        )
        
        response = await llm.ainvoke([
            {"role": "user", "content": "Hello, say hi!"}
        ])
        
        print("✅ Gemini API 작동 확인!")
        print(f"응답: {response.content}")
        
    except Exception as e:
        print(f"❌ 에러 발생: {str(e)}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_gemini())

