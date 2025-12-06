"""서버 상태 빠른 확인"""
import sys
import requests
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def check_server():
    """서버 상태 확인"""
    try:
        # Health check 엔드포인트 시도
        response = requests.get("http://localhost:8000/health", timeout=2)
        if response.status_code == 200:
            print("✅ 서버 실행 중 (Health Check 성공)")
            return True
    except requests.exceptions.ConnectionError:
        print("❌ 서버가 실행되지 않음 (연결 실패)")
        return False
    except requests.exceptions.Timeout:
        print("⚠️ 서버 응답 시간 초과 (서버는 실행 중일 수 있음)")
        return None
    except Exception as e:
        print(f"⚠️ 확인 중 오류: {str(e)}")
        return None
    
    # Health check가 없으면 docs 확인
    try:
        response = requests.get("http://localhost:8000/docs", timeout=2)
        if response.status_code == 200:
            print("✅ 서버 실행 중 (Docs 접근 가능)")
            return True
    except:
        pass
    
    return False

if __name__ == "__main__":
    check_server()


