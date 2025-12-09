# 테스트 스크립트 사용 가이드

## 개요

프로젝트의 유닛 테스트 및 더미 데이터 생성을 위한 테스트 스크립트 사용법을 정리합니다.

---

## 1. 유닛 테스트

### Node 4 의도 분석 및 평가 테스트

**파일**: `test_scripts/test_node4_intent_only.py`

**용도**: Node 4 (Turn Evaluator)의 의도 분석 및 평가 결과를 확인하는 유닛 테스트

**사용법**:

```bash
# 대화형 모드
python test_scripts/test_node4_intent_only.py

# 명령줄 인자 모드
python test_scripts/test_node4_intent_only.py "사용자 메시지" "AI 응답" [spec_id] [--save-db]
```

**예시**:
```bash
# 대화형 모드로 실행
python test_scripts/test_node4_intent_only.py

# 명령줄로 실행
python test_scripts/test_node4_intent_only.py "비트마스킹 DP 구조 알려줘" "**[Pseudo Code]**\n1. ..." 1 --save-db
```

**출력 내용**:
- 의도 분석 결과 (의도, 신뢰도)
- 평가 점수 (턴 점수, 루브릭별 점수)
- LLM 판단 근거 (각 루브릭별 상세 근거)
- 토큰 사용량
- DB 저장 (선택적)

**옵션**:
- `--save-db`: 평가 결과를 DB에 저장 (기본값: False)
- `spec_id`: 문제 스펙 ID (기본값: 2098)

---

## 2. 더미 데이터 생성

### 2.1 채팅 세션 생성

**파일**: `test_scripts/create_chat_session.py`

**용도**: 단일 채팅 세션 생성 (session_id=1)

**사용법**:
```bash
uv run python test_scripts/create_chat_session.py
```

**생성 내용**:
- Admin 계정 (id=1)
- Exam (id=1)
- Participant (id=1)
- Problem 및 ProblemSpec
- PromptSession (id=1)

---

### 2.2 여러 채팅 세션 생성

**파일**: `test_scripts/create_dummy_chat_sessions.py`

**용도**: 여러 개의 채팅 세션을 일괄 생성

**사용법**:
```bash
# 5개 세션 생성
uv run python test_scripts/create_dummy_chat_sessions.py 5
```

**생성 내용**:
- 기본 데이터 (Admin, Exam, Participant, Problem)
- 여러 개의 PromptSession
- 각 세션별 필요한 모든 데이터 자동 생성
- API 테스트에 필요한 정보를 JSON 파일로 저장

---

### 2.3 메시지 삽입

**파일**: `test_scripts/insert_prompt_messages.py`

**용도**: 기존 세션에 메시지 삽입

**사용법**:
```bash
uv run python test_scripts/insert_prompt_messages.py
```

**입력 형식**:
- JSON 파일 또는 직접 입력
- 메시지 형식: `{"turn": 1, "role": "USER", "content": "...", "token_count": 0}`

**주의사항**:
- `role`은 반드시 `"USER"` 또는 `"AI"` (대문자)로 입력
- `turn`은 세션 내에서 고유해야 함

---

### 2.4 TSP 문제 테스트 데이터 생성

**파일**: `test_scripts/setup_tsp_test_data.py`

**용도**: TSP (Traveling Salesman Problem) 문제 테스트 데이터 생성

**사용법**:
```bash
uv run python test_scripts/setup_tsp_test_data.py
```

---

### 2.5 웹 테스트 데이터 생성

**파일**: `test_scripts/setup_web_test_data.py`

**용도**: 웹 API 테스트용 데이터 생성

**사용법**:
```bash
uv run python test_scripts/setup_web_test_data.py
```

---

## 3. 서버 및 연결 확인

### 3.1 서버 상태 확인

**파일**: `test_scripts/check_server.py`

**사용법**:
```bash
python test_scripts/check_server.py
```

---

### 3.2 Judge0 연결 확인

**파일**: `test_scripts/check_judge0_connection.py`

**사용법**:
```bash
python test_scripts/check_judge0_connection.py
```

---

## 4. 주의사항

### DB 저장 시 제약조건

1. **메시지 존재 확인**: 평가 결과를 저장하기 전에 해당 `session_id`와 `turn`에 대한 메시지가 DB에 존재해야 합니다.

2. **Role 값**: `prompt_messages.role`은 반드시 `'USER'` 또는 `'AI'` (대문자)로 저장되어야 합니다.
   - 소문자 `'user'` 또는 `'ai'`는 ENUM 제약조건 위반으로 오류 발생

3. **Foreign Key**: 평가 결과 저장 시 `prompt_messages` 테이블에 해당 메시지가 존재해야 합니다.

### 테스트 데이터 정리

테스트 후 더미 데이터를 정리하려면:
```sql
-- 주의: 프로덕션 DB에서는 실행하지 마세요!
DELETE FROM ai_vibe_coding_test.prompt_evaluations;
DELETE FROM ai_vibe_coding_test.prompt_messages;
DELETE FROM ai_vibe_coding_test.prompt_sessions;
-- ... 기타 테이블 정리
```

---

## 5. 빠른 시작

### Node 4 테스트만 빠르게 실행

```bash
# 1. 세션 생성
uv run python test_scripts/create_chat_session.py

# 2. Node 4 테스트 실행
python test_scripts/test_node4_intent_only.py
```

### 전체 테스트 데이터 준비

```bash
# 1. 여러 세션 생성
uv run python test_scripts/create_dummy_chat_sessions.py 5

# 2. 메시지 삽입 (필요시)
uv run python test_scripts/insert_prompt_messages.py
```

---

## 참고

- 모든 스크립트는 프로젝트 루트에서 실행해야 합니다.
- DB 연결 정보는 `.env` 파일에서 읽어옵니다.
- 일부 스크립트는 `uv` 패키지 매니저를 사용합니다.

