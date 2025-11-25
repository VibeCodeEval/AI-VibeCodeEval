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
    """채팅 API 테스트"""
    
    def test_send_message(self, client):
        """메시지 전송 테스트"""
        request_data = {
            "session_id": "test-session-1",
            "exam_id": 1,
            "participant_id": 1,
            "spec_id": 1,
            "message": "Hello, AI!"
        }
        
        response = client.post("/api/chat/message", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "turn" in data
    
    def test_submit_code(self, client):
        """코드 제출 테스트"""
        request_data = {
            "session_id": "test-session-1",
            "exam_id": 1,
            "participant_id": 1,
            "spec_id": 1,
            "code": "def hello(): return 'Hello'",
            "lang": "python"
        }
        
        response = client.post("/api/chat/submit", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "is_submitted" in data


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

