# 타이밍 오류 분석 및 해결 방안

## 📌 현재 상황
- ✅ Turn 1, 2, 3의 백그라운드 평가 로그는 Redis에 정상 저장됨
- ❌ 제출 시점에 `turn_scores`가 비어있거나 일부만 존재
- ❌ Gemini API Quota 429 에러 발생 (연속 테스트 시)

---

## 🔍 문제 분류 및 관련 파일

### 1. Graph 구조 문제

#### 관련 파일:
- **`app/langgraph/graph.py`** (메인 그래프 정의)
- **`app/langgraph/nodes/eval_turn_guard.py`** (4번 가드 노드)
- **`app/langgraph/nodes/writer_router.py`** (라우팅 로직)

#### 현재 플로우:
```
일반 채팅:
1 → 2 → 3 (Writer LLM) → 5 (Main Router) → END
                ↓
         백그라운드 4번 평가
         
제출 요청:
1 → 2 → 4 (Eval Turn Guard) → 5 (Main Router) → 6a → 6b → 6c → 6d → 7 → END
```

#### 의심 포인트:
1. **백그라운드 평가와 메인 플로우의 분리**
   - 3번에서 백그라운드로 시작된 4번 평가가 완료되기 전에 제출 API가 호출될 수 있음
   - 제출 시 4번 가드에서 대기하지만, 백그라운드 태스크와 동기화가 완벽하지 않을 수 있음

2. **State 공유 문제**
   - 백그라운드 4번 평가는 별도 서브그래프로 실행
   - 메인 그래프의 `MainGraphState`와 서브그래프의 `EvalTurnState` 간 데이터 동기화
   - Redis를 통해 `turn_logs` 저장하지만, 메인 그래프의 `turn_scores`에 반영되는 시점이 4번 가드뿐

3. **4번 가드의 역할 중복**
   - 제출 시점에 누락된 턴을 재평가하는 로직
   - 하지만 백그라운드 평가가 이미 진행 중인 경우, 중복 평가 가능성

---

### 2. 타이밍 문제

#### 관련 파일:
- **`app/langgraph/nodes/writer.py`** (백그라운드 평가 시작 지점)
- **`app/services/eval_service.py`** (`_run_eval_turn_background` 메서드)
- **`app/langgraph/nodes/eval_turn_guard.py`** (대기 로직)
- **`app/langgraph/subgraph_eval_turn.py`** (실제 평가 서브그래프)

#### 타임라인 분석:

**시나리오 1: 정상 케이스 (대기 시간 충분)**
```
00:00 - Turn 1 채팅 → Writer LLM 완료
00:01 - 백그라운드 4번 평가 시작 (Task 1)
00:05 - Task 1 완료, turn_logs:1 저장
00:10 - Turn 2 채팅 → Writer LLM 완료
00:11 - 백그라운드 4번 평가 시작 (Task 2)
00:15 - Task 2 완료, turn_logs:2 저장
00:20 - Turn 3 채팅 → Writer LLM 완료
00:21 - 백그라운드 4번 평가 시작 (Task 3)
00:30 - [5초 대기] ← test_submit_with_delay.py
00:35 - 제출 API 호출
00:36 - 4번 가드 진입, 대기 시작
00:37 - Task 3 완료 (백그라운드 평가)
00:38 - 4번 가드 대기 종료, turn_scores 수집
00:39 - 6a → 6b → 6c → 6d → 7 → 성공
```

**시나리오 2: 문제 케이스 (API Quota 초과)**
```
00:00 - Turn 1 채팅 → Writer LLM 완료
00:01 - 백그라운드 4번 평가 시작 (Task 1)
00:05 - Task 1 완료, turn_logs:1 저장
00:10 - Turn 2 채팅 → Writer LLM 완료
00:11 - 백그라운드 4번 평가 시작 (Task 2)
00:15 - Task 2에서 429 에러 발생! ← API Quota 초과
00:15 - Task 2 실패, turn_logs:2 저장 안 됨
00:20 - Turn 3 채팅 → Writer LLM 완료
00:21 - 백그라운드 4번 평가 시작 (Task 3)
00:22 - Task 3에서도 429 에러 발생!
00:22 - Task 3 실패, turn_logs:3 저장 안 됨
00:30 - [5초 대기]
00:35 - 제출 API 호출
00:36 - 4번 가드 진입, 대기 시작
00:46 - 10초 타임아웃 (Task 2, 3 완료 안 됨)
00:47 - 누락된 턴 재평가 시도
00:48 - 재평가에서도 429 에러! ← 여전히 Quota 초과
00:50 - turn_scores: {'1': 85.5} ← Turn 2, 3 누락
00:51 - 6b에서 경고: "일부 턴 점수 누락"
```

**시나리오 3: 문제 케이스 (제출이 너무 빠름)**
```
00:00 - Turn 1 채팅 → Writer LLM 완료
00:01 - 백그라운드 4번 평가 시작 (Task 1)
00:10 - Turn 2 채팅 → Writer LLM 완료
00:11 - 백그라운드 4번 평가 시작 (Task 2)
00:20 - Turn 3 채팅 → Writer LLM 완료
00:21 - 백그라운드 4번 평가 시작 (Task 3)
00:22 - [즉시 제출] ← test_submit_only.py (2초 대기만)
00:24 - 제출 API 호출
00:25 - 4번 가드 진입, 대기 시작
00:26 - Task 1 완료 (5초 소요)
00:30 - Task 2 완료 (5초 소요)
00:34 - 대기 시간 10초 타임아웃
00:35 - turn_scores: {'1': 85.5, '2': 92.0} ← Turn 3 아직 진행 중
00:37 - Task 3 완료 (하지만 이미 늦음)
```

#### 타이밍 문제의 핵심:
1. **백그라운드 평가 소요 시간 불확실**
   - Intent 분석 (1-2초)
   - 4.1a-c 평가 (각 1-3초)
   - 4.2 답변 요약 (1-2초)
   - 총 5-10초 소요

2. **대기 시간 부족**
   - 현재 4번 가드 대기: 최대 10초
   - 평가가 10초 이상 걸리면 타임아웃

3. **재평가 시도 시 또 다시 LLM 호출**
   - 4번 가드에서 누락된 턴 재평가 시도
   - API Quota 초과 상태라면 재평가도 실패

---

### 3. API 할당량 문제

#### 관련 파일:
- **모든 LLM 호출 노드**
  - `app/langgraph/nodes/intent_analyzer.py`
  - `app/langgraph/nodes/writer.py`
  - `app/langgraph/subgraph_eval_turn.py` (4.X 노드들)
  - `app/langgraph/nodes/evaluators.py` (6a-d 노드들)

#### LLM 호출 횟수 분석 (3턴 + 제출 기준):

**일반 채팅 (Turn 1-3):**
```
각 턴당:
  1. Intent Analyzer: 1회
  2. Writer LLM: 1회
  3. 백그라운드 평가:
     - 4.0 Intent 분석: 1회
     - 4.1a Clarity: 1회
     - 4.1b Specificity: 1회
     - 4.1c Contextual: 1회
     - 4.2 답변 요약: 1회
  소계: 7회/턴

3턴 총: 21회
```

**제출 플로우:**
```
4번 가드: 0-3회 (재평가 필요 시)
6a Holistic Flow: 1회
6c Code Performance: 0회 (Judge0 연동 시)
6d Code Correctness: 0회 (Judge0 연동 시)

소계: 1-4회
```

**총 LLM 호출: 22-25회**

#### Gemini API 할당량 (무료 티어 기준):
- **분당 요청: 15 RPM (Requests Per Minute)**
- **일일 요청: 1,500 RPD (Requests Per Day)**

#### 문제 분석:
```
시나리오 1: 연속 테스트
00:00 - Test 1 시작 (3턴 + 제출)
00:00~01:00 - 22회 호출 (RPM 초과!)
01:00 - 429 에러 발생
01:00~02:00 - 대기 필요
02:00 - Test 2 시작 가능

시나리오 2: 빠른 재테스트
04:18 - Test 1 완료
04:24 - Test 2 즉시 시작
04:25 - Turn 2부터 429 에러 (아직 1분 경과 안 됨)
```

#### 해결 필요 사항:
1. **요청 간격 조절**
   - 각 LLM 호출 사이 최소 4초 간격 (15 RPM → 60/15 = 4초)
   - 현재는 백그라운드 평가로 동시 호출 가능

2. **재시도 로직 개선**
   - 429 에러 시 exponential backoff
   - 현재는 재시도 없이 바로 실패

3. **테스트 간격 확보**
   - 연속 테스트 시 최소 1-2분 간격

---

## 🛠️ 해결 방안

### 방안 1: Turn 정보 저장 후 제출만 별도 테스트 (추천)

#### 장점:
- ✅ API 호출 최소화 (제출 플로우만)
- ✅ 타이밍 문제 회피 (백그라운드 평가 완료 후 제출)
- ✅ 반복 테스트 용이

#### 구현 방법:
1. **Phase 1: 턴 데이터 수집 테스트**
   - 3턴 채팅만 진행 (제출 안 함)
   - 백그라운드 평가 완료 대기 (충분한 시간)
   - Redis에 turn_logs, turn_mapping 저장
   - session_id 기록

2. **Phase 2: 제출만 테스트**
   - 저장된 session_id 사용
   - Redis에서 기존 turn_logs, turn_mapping 불러오기
   - graph_state 재구성
   - 제출 API 직접 호출

#### 필요 파일:
- `test_collect_turns.py` (Phase 1)
- `test_submit_from_saved.py` (Phase 2)
- `turn_sessions.json` (session_id 저장용, 로컬 파일)

**Redis만 사용하면 됨 (로컬 DB 불필요)**

---

### 방안 2: 대기 시간 대폭 증가

#### 수정 파일:
- `app/langgraph/nodes/eval_turn_guard.py`

```python
# 현재: max_wait_seconds = 10
# 변경: max_wait_seconds = 30
```

#### 장점:
- ✅ 간단한 수정

#### 단점:
- ❌ API Quota 문제 해결 안 됨
- ❌ 근본 원인 해결 아님

---

### 방안 3: Rate Limiting 추가

#### 수정 파일:
- `app/services/eval_service.py`
- 모든 LLM 호출 노드

#### 구현:
```python
import asyncio
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, max_requests=15, period=60):
        self.max_requests = max_requests
        self.period = period
        self.requests = []
    
    async def acquire(self):
        now = datetime.now()
        # 오래된 요청 제거
        self.requests = [t for t in self.requests if now - t < timedelta(seconds=self.period)]
        
        if len(self.requests) >= self.max_requests:
            # 대기 시간 계산
            oldest = self.requests[0]
            wait_time = (oldest + timedelta(seconds=self.period) - now).total_seconds()
            await asyncio.sleep(wait_time + 1)
            self.requests = self.requests[1:]
        
        self.requests.append(now)

# 전역 rate limiter
llm_limiter = RateLimiter(max_requests=12, period=60)  # 여유 있게 12 RPM

# 사용
async def call_llm():
    await llm_limiter.acquire()
    result = await llm.ainvoke(...)
    return result
```

#### 장점:
- ✅ API Quota 문제 근본 해결
- ✅ 프로덕션 환경에도 필요

#### 단점:
- ❌ 구현 범위 큼
- ❌ 모든 LLM 호출 지점 수정 필요

---

## 📊 권장 해결 순서

### 즉시 적용 (테스트용):
1. **방안 1 구현: Turn 정보 저장 후 제출 테스트**
   - API 호출 최소화
   - 타이밍 문제 회피

### 중기 (1-2일):
2. **방안 2 적용: 대기 시간 증가**
   - 10초 → 30초
   - 임시 해결책

3. **4번 가드 로직 개선**
   - 재평가 시도 전 Redis 재확인
   - 더 상세한 로깅

### 장기 (1주):
4. **방안 3 적용: Rate Limiting**
   - 전역 rate limiter 구현
   - 모든 LLM 호출 지점 적용

5. **재시도 로직 추가**
   - 429 에러 시 exponential backoff
   - 3회 재시도 후 실패 처리

---

## 🎯 다음 테스트 계획

### Phase 1: Turn 수집 (API Quota 회복 후)
```bash
cd C:\P_project\LangGraph_1
uv run python test_collect_turns.py
# → session_id 저장
# → 20초 대기 (백그라운드 평가 완료)
# → Redis 검증
```

### Phase 2: 제출만 테스트 (즉시 가능)
```bash
uv run python test_submit_from_saved.py --session <저장된-session-id>
# → Redis에서 turn_logs 불러오기
# → graph_state 재구성
# → 제출 API 호출
# → turn_scores 검증
```

### 예상 API 호출:
- Phase 1: 21회 (3턴 × 7회)
- Phase 2: 1-4회 (제출 플로우만)
- 총: 22-25회 (기존과 동일하지만 분리 실행 가능)

---

## 📝 결론

현재 문제는:
1. **타이밍**: 백그라운드 평가 완료 전 제출
2. **API Quota**: 연속 테스트 시 RPM 초과

**즉시 해결책**:
- Turn 정보 저장 → 제출 분리 테스트
- Redis만 사용 (로컬 DB 불필요)

**장기 해결책**:
- Rate Limiting 구현
- 대기 시간 증가
- 재시도 로직 추가

