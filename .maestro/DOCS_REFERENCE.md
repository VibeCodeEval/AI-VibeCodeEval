# docs/ 문서 참조 가이드

> **작성일**: 2026-03-27  
> **목적**: 작업 시 어떤 `docs/` 파일을 참조해야 하는지 빠르게 찾기 위한 가이드  
> **총 문서 수**: 21개

---

## API 관련

### `API_전체_명세.md`
Worker REST API 전체 스펙 (Base URL, 공통 헤더, 엔드포인트별 요청/응답).  
**참조 시점**: API 엔드포인트 추가·변경 시, 프론트엔드 연동 시, 새 API 테스트 작성 시.  
**관련 코드**: `app/presentation/api/routes/`, `app/presentation/schemas/`  
**함께 보면 좋은 문서**: `API_현재_구현.md`, `API_DB_매핑.md`

### `API_현재_구현.md`
현재 활성 엔드포인트의 실제 구현 상태 (스펙 vs 구현 차이 포함).  
**참조 시점**: API 디버깅 시, 스펙과 실제 동작 불일치 확인 시, 구현 누락 점검 시.  
**관련 코드**: `app/presentation/api/routes/chat.py`, `session.py`  
**함께 보면 좋은 문서**: `API_전체_명세.md`

### `API_DB_매핑.md`
API 응답 필드명 ↔ DB 컬럼명 매핑표, 필드명 불일치 분석.  
**참조 시점**: API 응답에 새 필드 추가 시, DB 컬럼과 API 필드 연결 확인 시, 데이터 변환 로직 수정 시.  
**관련 코드**: `app/presentation/schemas/`, `app/infrastructure/persistence/models/`  
**함께 보면 좋은 문서**: `테이블명세서.md`, `API_전체_명세.md`

### `API_변경_이력.md`
API/엔드포인트 변경 기록 (날짜 역순). 경로·바디·응답 변경 내역.  
**참조 시점**: 이전 API 변경 사유 확인 시, 하위 호환성 영향 분석 시, 롤백 검토 시.  
**관련 코드**: `app/presentation/api/routes/`  
**함께 보면 좋은 문서**: `API_전체_명세.md`, `API_현재_구현.md`

---

## DB 관련

### `테이블명세서.md`
전체 DB 구조 한눈에 보기. 스키마 `ai_vibe_coding_test`, ENUM 정의, 엔터티별 PK/FK/컬럼·제약.  
**참조 시점**: DB 구조 전체 파악 시, 새 테이블/컬럼 추가 시, ORM 모델 수정 시, ERD 참조 시.  
**관련 코드**: `app/infrastructure/persistence/models/`, `scripts/init-db.sql`  
**함께 보면 좋은 문서**: `DB_변경_이력.md`, `API_DB_매핑.md`

### `DB_설정_가이드.md`
PostgreSQL + Redis 전체 설정, 로컬 스키마 생성, Docker→로컬 마이그레이션 방법.  
**참조 시점**: 새 개발환경 구축 시, DB 초기 설정 시, Docker↔로컬 전환 시, 연결 오류 해결 시.  
**관련 코드**: `scripts/init-db.sql`, `scripts/setup_local_db.ps1`, `docker-compose.dev.yml`  
**함께 보면 좋은 문서**: `환경_설정_가이드.md`, `Docker_백엔드_가이드.md`

### `DB_변경_이력.md`
DB 스키마 변경 요약 + init-db.sql 대비 상세 변경 이력 (제약조건·인덱스 포함).  
**참조 시점**: 스키마 변경 전 이전 이력 확인 시, init-db.sql 수정 시, 마이그레이션 SQL 작성 시.  
**관련 코드**: `scripts/init-db.sql`, `app/infrastructure/persistence/models/enums.py`  
**함께 보면 좋은 문서**: `테이블명세서.md`

---

## LangGraph / 노드 동작

### `State_흐름_및_DB_저장.md`
LangGraph 데이터 흐름, MainGraphState 구조, Redis vs Memory 차이, DB 저장 전략.  
**참조 시점**: State 필드 추가/변경 시, Redis↔PG 저장 로직 수정 시, 노드 간 데이터 흐름 파악 시.  
**관련 코드**: `app/domain/langgraph/states.py`, `app/domain/langgraph/graph.py`  
**함께 보면 좋은 문서**: `노드별_DB_접근_가이드.md`, `Node4_평가_가이드.md`

### `Node4_평가_가이드.md`
턴 평가(Node4) 의도 분석 vs 평가 역할, 평가 플로우 시나리오, I/O 스키마 (prompt_evaluations).  
**참조 시점**: 턴 평가 로직 수정 시, 의도 분석/평가 디버깅 시, prompt_evaluations JSONB 구조 확인 시.  
**관련 코드**: `app/domain/langgraph/nodes/turn_evaluator/`, `app/domain/langgraph/nodes/eval_turn_guard.py`  
**함께 보면 좋은 문서**: `노드별_DB_접근_가이드.md`, `프롬프트_명세.md`, `점수_계산_로직.md`

### `노드별_DB_접근_가이드.md`
각 노드(4번·6번)의 Redis/PG 접근 위치, 저장 시점, 호출 스택 정리.  
**참조 시점**: 노드에서 데이터 저장/조회 방식 확인 시, 새 노드 추가 시, 저장 버그 추적 시.  
**관련 코드**: `app/application/services/evaluation_storage_service.py`, `app/infrastructure/repositories/`  
**함께 보면 좋은 문서**: `State_흐름_및_DB_저장.md`, `Node4_평가_가이드.md`

### `프롬프트_명세.md`
노드별 프롬프트 상세 (Intent Analyzer, Writer, Guard, Holistic 등 각 프롬프트 구조/변수).  
**참조 시점**: 프롬프트 수정·추가 시, YAML 변수 확인 시, 새 평가 기준 추가 시.  
**관련 코드**: `app/domain/langgraph/prompts/*.yaml`  
**함께 보면 좋은 문서**: `Node4_평가_가이드.md`, `.maestro/docs/V2.1_Change_Log.md`

### `점수_계산_로직.md`
scores.py의 가중치·총점 계산 방식, 학점 환산, prompt_score 산정.  
**참조 시점**: 점수 가중치 변경 시, 총점 계산 로직 수정 시, 학점 기준 변경 시, 새 평가 항목 추가 시.  
**관련 코드**: `app/domain/langgraph/nodes/holistic_evaluator/scores.py`  
**함께 보면 좋은 문서**: `Node4_평가_가이드.md`, `.maestro/docs/V2.1_Evaluation_And_Score_Structure.md`

### `턴_로그_추출.md`
Holistic 평가에서 Redis turn_logs 추출 필드, structured_logs 구조.  
**참조 시점**: Holistic 평가 수정 시, turn_logs 필드 추가·변경 시, 파인튜닝 데이터 추출 시.  
**관련 코드**: `app/domain/langgraph/nodes/holistic_evaluator/flow.py`, `execution.py`  
**함께 보면 좋은 문서**: `노드별_DB_접근_가이드.md`, `점수_계산_로직.md`

### `루브릭_리팩토링_제안.md`
루브릭 하드코딩 문제점 분석, YAML/DB 기반 리팩토링 설계 제안.  
**참조 시점**: 루브릭 구조 변경 계획 시, 평가 기준 리팩토링 착수 시, 하드코딩 제거 방안 검토 시.  
**관련 코드**: `app/domain/langgraph/nodes/turn_evaluator/weights.py`, `grading.py`  
**함께 보면 좋은 문서**: `프롬프트_명세.md`, `점수_계산_로직.md`

### `LLM_성능_최적화.md`
Turn Evaluator LLM 이중 호출 등 성능 이슈 분석, 개선안 (캐싱·배치·병렬화).  
**참조 시점**: LLM 호출 비용/지연 최적화 시, 이중 호출 제거 시, 새 LLM 연동 검토 시.  
**관련 코드**: `app/domain/langgraph/nodes/turn_evaluator/evaluators.py`, `utils/llm_factory.py`  
**함께 보면 좋은 문서**: `Node4_평가_가이드.md`

---

## 설정 / 인프라

### `환경_설정_가이드.md`
환경 변수(.env) 설정, 로컬/Docker 개발 환경 구축, 빠른 참조 명령 모음.  
**참조 시점**: 처음 프로젝트 시작 시, 환경 변수 추가·변경 시, Docker 명령어 확인 시.  
**관련 코드**: `.env`, `env.example`, `docker-compose.dev.yml`, `app/core/config.py`  
**함께 보면 좋은 문서**: `Docker_백엔드_가이드.md`, `DB_설정_가이드.md`

### `Docker_백엔드_가이드.md`
Docker Compose 설정, Spring 백엔드 연동, 네트워크 구성, DB 동일화 방법.  
**참조 시점**: Docker 환경 수정 시, Spring 백엔드와 연동 시, 컨테이너 네트워크 이슈 해결 시.  
**관련 코드**: `Dockerfile`, `docker-compose.yml`, `docker-compose.prod.yml`  
**함께 보면 좋은 문서**: `환경_설정_가이드.md`, `DB_설정_가이드.md`

### `UV_설정_가이드.md`
uv 설치, 프로젝트 초기화, 의존성 추가·제거·동기화 방법.  
**참조 시점**: 새 패키지 추가 시, 의존성 충돌 해결 시, 새 환경에서 프로젝트 셋업 시.  
**관련 코드**: `pyproject.toml`, `requirements.txt`, `uv.lock`  
**함께 보면 좋은 문서**: `환경_설정_가이드.md`

---

## 테스트

### `테스트_가이드.md`
테스트 환경 준비 → 테스트 스크립트 사용법 → API 테스트 → 전체 플로우 시나리오.  
**참조 시점**: 테스트 실행 시, 새 테스트 작성 시, E2E 시나리오 검증 시, CI/CD 파이프라인 구성 시.  
**관련 코드**: `tests/`, `test_scripts/`, `scripts/`  
**함께 보면 좋은 문서**: `Judge0_가이드.md`, `환경_설정_가이드.md`

### `Judge0_가이드.md`
Judge0 설정·API 연동·테스트 케이스 플로우·빠른 실행·트러블슈팅 종합.  
**참조 시점**: Judge0 설정·연동 시, 코드 실행 테스트 시, 테스트 케이스 추가 시, 제출 플로우 디버깅 시.  
**관련 코드**: `app/infrastructure/judge0/`, `app/application/workers/judge_worker.py`  
**함께 보면 좋은 문서**: `테스트_가이드.md`

---

## 메타

### `문서_인덱스.md`
전체 docs/ 문서 목록, 카테고리별 분류, 빠른 참조표, 코드 위치 참조.  
**참조 시점**: 어떤 문서가 있는지 모를 때, 특정 주제의 문서를 찾을 때, 코드 위치 확인 시.  
**관련 파일**: 이 문서 자체가 인덱스  
**함께 보면 좋은 문서**: 이 파일(`DOCS_REFERENCE.md`)과 상호 보완

---

## Maestro 전용 (`/.maestro/DOCS/`)

루트 `docs/` 와 별도로, **Submit 테스트 절차·`.env`·평가 JSON·Redis 토론 덤프** 등을 정리한 문서입니다.

| 문서 | 용도 |
|------|------|
| `.maestro/DOCS/README.md` | DOCS 폴더 목차 |
| `.maestro/DOCS/Submit_테스트_ENV_평가덤프_가이드.md` | `setup_submit_test_data`, `check_submit_result`, `export_evaluation_json`, `debate_redis`, 관련 환경 변수 |

---

## 작업 시나리오별 빠른 참조

| 작업 | 참조 문서 |
|------|-----------|
| **새 API 엔드포인트 추가** | `API_전체_명세.md` → `API_DB_매핑.md` → `테이블명세서.md` |
| **평가 로직 수정** | `Node4_평가_가이드.md` → `프롬프트_명세.md` → `점수_계산_로직.md` |
| **State 필드 추가** | `State_흐름_및_DB_저장.md` → `노드별_DB_접근_가이드.md` |
| **DB 스키마 변경** | `테이블명세서.md` → `DB_변경_이력.md` → `API_DB_매핑.md` |
| **새 환경 구축** | `환경_설정_가이드.md` → `DB_설정_가이드.md` → `UV_설정_가이드.md` |
| **테스트 실행** | `테스트_가이드.md` → `Judge0_가이드.md` |
| **Submit 시드·평가 JSON·토론 Redis** | `.maestro/DOCS/Submit_테스트_ENV_평가덤프_가이드.md` |
| **프롬프트 수정** | `프롬프트_명세.md` → `Node4_평가_가이드.md` |
| **점수/학점 기준 변경** | `점수_계산_로직.md` → `루브릭_리팩토링_제안.md` |
| **Docker 환경 수정** | `Docker_백엔드_가이드.md` → `환경_설정_가이드.md` |
| **파인튜닝 데이터 작업** | `턴_로그_추출.md` → `Node4_평가_가이드.md` |
| **LLM 비용/성능 개선** | `LLM_성능_최적화.md` → `Node4_평가_가이드.md` |
