"""
Judge0 연결 확인 스크립트
"""
import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from app.core.config import settings


async def check_judge0_connection():
    """Judge0 서버 연결 확인"""
    
    print("=" * 80)
    print("Judge0 연결 확인")
    print("=" * 80)
    print()
    
    # 설정 확인
    print("📋 현재 설정:")
    print(f"   JUDGE0_API_URL: {settings.JUDGE0_API_URL}")
    print(f"   JUDGE0_USE_RAPIDAPI: {settings.JUDGE0_USE_RAPIDAPI}")
    print(f"   JUDGE0_API_KEY: {'설정됨' if settings.JUDGE0_API_KEY else '미설정'}")
    print(f"   JUDGE0_RAPIDAPI_HOST: {settings.JUDGE0_RAPIDAPI_HOST}")
    print()
    
    # 연결 테스트
    print("🔍 연결 테스트 중...")
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 헤더 준비
            headers = {"Content-Type": "application/json"}
            
            if settings.JUDGE0_USE_RAPIDAPI:
                if settings.JUDGE0_API_KEY:
                    headers["x-rapidapi-key"] = settings.JUDGE0_API_KEY
                headers["x-rapidapi-host"] = settings.JUDGE0_RAPIDAPI_HOST
            else:
                if settings.JUDGE0_API_KEY:
                    headers["X-Auth-Token"] = settings.JUDGE0_API_KEY
            
            # /about 엔드포인트로 연결 테스트
            url = f"{settings.JUDGE0_API_URL}/about"
            print(f"   URL: {url}")
            print(f"   Headers: {list(headers.keys())}")
            print()
            
            response = await client.get(url, headers=headers)
            
            print("✅ 연결 성공!")
            print(f"   Status Code: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            
    except httpx.ConnectError as e:
        print("❌ 연결 실패: 서버에 연결할 수 없습니다")
        print()
        print("🔧 해결 방법:")
        print()
        
        if settings.JUDGE0_USE_RAPIDAPI:
            print("   RapidAPI를 사용 중입니다:")
            print("   1. JUDGE0_API_URL이 올바른지 확인:")
            print(f"      현재: {settings.JUDGE0_API_URL}")
            print("      예상: https://judge0-ce.p.rapidapi.com")
            print()
            print("   2. JUDGE0_API_KEY가 올바른지 확인:")
            print(f"      현재: {'설정됨' if settings.JUDGE0_API_KEY else '미설정'}")
            print("      .env 파일에 RapidAPI Key를 설정하세요")
            print()
            print("   3. RapidAPI 구독 상태 확인:")
            print("      - RapidAPI 대시보드에서 Judge0 API 구독 확인")
            print("      - API Key가 활성화되어 있는지 확인")
        else:
            print("   로컬 Judge0 서버를 사용 중입니다:")
            print("   1. Judge0 서버가 실행 중인지 확인:")
            print("      docker run -d -p 2358:2358 judge0/judge0:latest")
            print()
            print("   2. 서버가 실행 중이라면:")
            print("      curl http://localhost:2358/about")
            print()
            print("   3. .env 파일 확인:")
            print(f"      JUDGE0_API_URL={settings.JUDGE0_API_URL}")
        
        print()
        print(f"   에러 상세: {str(e)}")
        
    except httpx.TimeoutException:
        print("❌ 타임아웃: 서버 응답이 없습니다")
        print("   서버가 실행 중인지 확인하세요")
        
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_judge0_connection())

