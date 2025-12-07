"""
API 테스트
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """테스트 클라이언트 생성"""
    from app.main import app
    return TestClient(app)


class TestHealthAPI:
    """헬스 체크 API 테스트"""
    
    def test_root(self, client):
        """루트 엔드포인트 테스트"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
    
    def test_health(self, client):
        """헬스 체크 테스트"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "components" in data


class TestChatAPI:
    """채팅 API 테스트 (신규 API)"""
    
    def test_send_message(self, client):
        """메시지 전송 테스트 (신규 API: POST /api/chat/messages)"""
        # 주의: 실제 세션이 DB에 존재해야 합니다.
        # 테스트 전에 setup_web_test_data.py를 실행하여 테스트 데이터를 준비하세요.
        request_data = {
            "sessionId": 1,  # 실제 세션 ID (DB에 존재해야 함)
            "examParticipantId": 1,  # exam_participants.id
            "turnId": 1,
            "role": "USER",
            "content": "Hello, AI!",
            "context": {
                "problemId": 1,
                "specVersion": 1
            }
        }
        
        response = client.post("/api/chat/messages", json=request_data)
        
        # 세션이 없으면 404, 있으면 200
        if response.status_code == 404:
            # 세션이 없는 경우 (정상적인 에러 응답)
            data = response.json()
            assert "error" in data
            assert data["error"] == True
            assert "SESSION_NOT_FOUND" in data.get("error_code", "")
        elif response.status_code == 200:
            # 세션이 있는 경우 (정상 응답)
            data = response.json()
            assert "aiMessage" in data
            ai_message = data["aiMessage"]
            assert "session_id" in ai_message
            assert "turn" in ai_message
            assert "role" in ai_message
            assert "content" in ai_message
            assert "tokenCount" in ai_message
            assert "totalToken" in ai_message
        else:
            # 예상치 못한 상태 코드
            pytest.fail(f"Unexpected status code: {response.status_code}")
    
    def test_send_message_session_not_found(self, client):
        """존재하지 않는 세션 테스트 (404 에러)"""
        request_data = {
            "sessionId": 99999,  # 존재하지 않는 세션 ID
            "examParticipantId": 1,
            "turnId": 1,
            "role": "USER",
            "content": "Test message",
            "context": {
                "problemId": 1,
                "specVersion": 1
            }
        }
        
        response = client.post("/api/chat/messages", json=request_data)
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"] == True
        assert "SESSION_NOT_FOUND" in data.get("error_code", "")


class TestSessionAPI:
    """세션 API 테스트"""
    
    def test_get_session_state_not_found(self, client):
        """존재하지 않는 세션 조회"""
        response = client.get("/api/session/nonexistent-session/state")
        assert response.status_code == 404
    
    def test_delete_session(self, client):
        """세션 삭제 테스트"""
        response = client.delete("/api/session/test-session-1")
        assert response.status_code == 204

