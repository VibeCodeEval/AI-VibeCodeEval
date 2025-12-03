# Judge0 통합 가이드

## ✅ 구현 완료

1. **Judge0 API 클라이언트** (`app/infrastructure/judge0/client.py`)
2. **Judge0 Worker** (`app/application/workers/judge_worker.py`)
3. **LangGraph 노드 통합** (6c, 6d 노드)

---

## 🚀 사용 방법

### 1. Judge0 서버 실행

```bash
# Docker로 Judge0 실행
docker run -d -p 2358:2358 judge0/judge0:latest
```

또는 기존 Judge0 서버 사용:
```env
JUDGE0_API_URL=http://localhost:2358
JUDGE0_API_KEY=your_api_key  # 선택사항
```

### 2. Worker 실행

```bash
# Judge0 Worker 실행
python -m app.application.workers.judge_worker
```

또는 여러 Worker 실행 (확장):
```bash
# 터미널 1
python -m app.application.workers.judge_worker

# 터미널 2
python -m app.application.workers.judge_worker

# 터미널 3
python -m app.application.workers.judge_worker
```

### 3. API 서버 실행

```bash
# FastAPI 서버 실행
uvicorn app.main:app --reload
```

---

## 🔄 동작 흐름

```
1. 사용자 코드 제출
   ↓
2. LangGraph 6c/6d 노드 실행
   ↓
3. 큐에 작업 추가 (enqueue)
   ↓
4. 즉시 응답 반환 (폴링 시작)
   ↓
5. Judge0 Worker가 큐에서 작업 가져오기 (dequeue)
   ↓
6. Judge0 API로 코드 실행
   ↓
7. 결과를 Redis에 저장
   ↓
8. LangGraph 노드가 폴링으로 결과 확인
   ↓
9. 결과 반환
```

---

## 📝 설정

### .env 파일

```env
# Judge0 설정
JUDGE0_API_URL=http://localhost:2358
JUDGE0_API_KEY=your_api_key  # 선택사항

# 큐 시스템 설정
USE_REDIS_QUEUE=true  # Redis 사용 (프로덕션)
# USE_REDIS_QUEUE=false  # 메모리 사용 (개발/테스트)
```

---

## 🧪 테스트

### 단위 테스트

```bash
# Judge0 클라이언트 테스트
pytest tests/test_judge0_integration.py -v
```

### 수동 테스트

1. Judge0 서버 실행 확인:
```bash
curl http://localhost:2358/status
```

2. Worker 실행:
```bash
python -m app.application.workers.judge_worker
```

3. API 서버에서 코드 제출:
```bash
curl -X POST http://localhost:8000/api/chat/submit \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test-session",
    "exam_id": 1,
    "participant_id": 100,
    "spec_id": 10,
    "code": "print(\"hello\")",
    "lang": "python"
  }'
```

---

## 🔧 문제 해결

### Worker가 작업을 가져오지 못함

**원인**: Redis 연결 실패 또는 큐가 비어있음

**해결**:
1. Redis 연결 확인: `redis-cli ping`
2. 큐 확인: `redis-cli LRANGE judge_queue:pending 0 -1`
3. Worker 로그 확인

### Judge0 API 호출 실패

**원인**: Judge0 서버가 실행되지 않음

**해결**:
1. Judge0 서버 실행 확인: `curl http://localhost:2358/status`
2. `JUDGE0_API_URL` 설정 확인

### 타임아웃 발생

**원인**: Worker가 너무 느리거나 작업이 많음

**해결**:
1. Worker 개수 증가
2. `max_wait` 시간 증가 (노드 코드에서)

---

## 📊 모니터링

### Redis 큐 상태 확인

```bash
# 대기 중인 작업 수
redis-cli LLEN judge_queue:pending

# 작업 목록
redis-cli LRANGE judge_queue:pending 0 -1

# 특정 작업 상태
redis-cli GET judge_status:task_123

# 특정 작업 결과
redis-cli GET judge_result:task_123
```

---

## 🎯 다음 단계

1. ✅ Judge0 API 연동 완료
2. ⏭️ 테스트 케이스 추가 (problem_context에서 가져오기)
3. ⏭️ 성능 집계 (n회 실행, 중앙값)
4. ⏭️ 실행 리포팅 (이벤트 발행)

