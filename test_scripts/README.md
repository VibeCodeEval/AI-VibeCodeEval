# 🧪 테스트 스크립트 폴더

이 폴더는 통합 테스트 및 시스템 검증 스크립트를 포함합니다.

---

## 📋 스크립트 목록

### ⭐ Phase 1-2 분리 테스트 (권장)

#### 1. `test_collect_turns.py` - Phase 1: Turn 수집
**역할**: 대화 턴만 수집하고 제출하지 않음 (API Quota 절약)

**실행 방법**:
```bash
cd C:\P_project\LangGraph_1
uv run python test_scripts/test_collect_turns.py
```

**동작**:
1. 2턴 대화 진행 (피보나치 문제)
2. 백그라운드 평가 완료 대기 (20초)
3. Redis 데이터 검증 (turn_logs, turn_mapping)
4. 세션 ID를 `../data/turn_sessions.json`에 저장

**결과**: 세션 ID가 저장되어 Phase 2에서 재사용 가능

---

#### 2. `test_submit_from_saved.py` - Phase 2: 제출
**역할**: 저장된 세션으로 제출만 실행 (API Quota 절약)

**실행 방법**:
```bash
# 최근 세션으로 제출
uv run python test_scripts/test_submit_from_saved.py

# 특정 세션으로 제출
uv run python test_scripts/test_submit_from_saved.py <session-id>
```

**동작**:
1. `../data/turn_sessions.json`에서 세션 ID 로드
2. Redis 데이터 검증 (turn_logs, turn_mapping, graph_state)
3. 코드 제출 API 호출
4. 결과 분석 (turn_scores, final_scores 비교)

**결과**: 상세한 제출 결과 및 검증 리포트

---

#### 3. `list_saved_sessions.py` - 세션 관리
**역할**: 저장된 세션 목록 조회 및 Redis 상태 확인

**실행 방법**:
```bash
uv run python test_scripts/list_saved_sessions.py
```

**동작**:
1. `../data/turn_sessions.json` 읽기
2. 각 세션의 Redis 데이터 존재 여부 확인
3. 사용 가능한 세션 목록 출력

**결과**:
```
[1] turns-collect-20251127-204946
    생성: 2025-11-27T20:49:46
    턴 수: 2
    상태: turns_collected
    Redis: [OK] 데이터 존재 (turn_logs: 2, graph_state: O)
```

---

### 🔍 기타 테스트 스크립트

#### 4. `test_chat_flow.py` - 전체 플로우 테스트
**역할**: 3턴 대화 + 제출 + Redis 검증 (한 번에 실행)

**실행 방법**:
```bash
uv run python test_scripts/test_chat_flow.py
```

**특징**:
- Redis 직접 확인 기능 포함
- 백그라운드 평가 대기 포함
- 전체 플로우 검증

**주의**: Gemini API Quota 소모 (15 RPM 제한)

---

#### 5. `test_gemini.py` - Gemini API 연결 테스트
**역할**: Gemini API 키 및 연결 확인

**실행 방법**:
```bash
uv run python test_scripts/test_gemini.py
```

**결과**:
```
✅ Gemini API 작동 확인!
응답: Hello! How can I help you today?
```

---

## 🎯 권장 테스트 전략

### 1. 일반 개발/디버깅
```bash
# Phase 1: Turn 수집 (API Quota 절약)
uv run python test_scripts/test_collect_turns.py

# Phase 2: 제출 테스트
uv run python test_scripts/test_submit_from_saved.py
```

**장점**:
- API 호출 최소화 (Gemini API 15 RPM 제한 회피)
- Phase 1 실패 시 Phase 2 재실행 불필요
- 각 단계별 독립적 디버깅 가능

---

### 2. 빠른 검증
```bash
# 전체 플로우 한 번에
uv run python test_scripts/test_chat_flow.py
```

**장점**:
- 전체 플로우 빠른 확인
- Redis 직접 검증 포함

**단점**:
- API Quota 소모
- 중간 실패 시 재실행 필요

---

### 3. API 연결 확인
```bash
# Gemini API 테스트
uv run python test_scripts/test_gemini.py
```

**사용 시점**:
- 서버 시작 전 API 키 확인
- 429 에러 발생 시 연결 확인

---

## 📊 데이터 파일

### `../data/turn_sessions.json`
Phase 1에서 수집한 세션 ID 저장

**구조**:
```json
[
  {
    "session_id": "turns-collect-20251127-204946",
    "created_at": "2025-11-27T20:49:46",
    "turns": 2,
    "status": "turns_collected"
  }
]
```

---

## 🔧 문제 해결

### 세션이 없다고 나올 때
```bash
# 세션 목록 확인
uv run python test_scripts/list_saved_sessions.py

# 새 세션 수집
uv run python test_scripts/test_collect_turns.py
```

---

### Redis 데이터가 만료된 경우
```bash
# 새 세션 수집 (TTL 24시간)
uv run python test_scripts/test_collect_turns.py
```

---

### API Quota 초과 (429 에러)
```bash
# 대기 후 재시도 (Gemini Free Tier: 15 RPM)
# 1분 대기 후:
uv run python test_scripts/test_collect_turns.py
```

---

## 📝 새 테스트 추가 시

1. 이 폴더에 `test_*.py` 파일 생성
2. `BASE_URL = "http://localhost:8000"` 설정
3. 데이터 파일은 `../data/` 폴더 사용
4. 이 README.md에 설명 추가

---

**최종 업데이트**: 2025-11-28

