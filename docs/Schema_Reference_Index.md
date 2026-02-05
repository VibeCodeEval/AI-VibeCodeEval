# 현재 스키마 구조 확인용 문서 인덱스

> 프로젝트의 **DB·API·State 스키마**를 확인할 수 있는 문서와 코드 위치를 정리한 인덱스입니다.

---

## 1. DB 스키마 (PostgreSQL)

| 문서/파일 | 경로 | 내용 |
|-----------|------|------|
| **테이블명세서 (ERD 요약)** | **`테이블명세서.md`** (프로젝트 루트) | 스키마 `ai_vibe_coding_test`, ENUM 정의, 엔터티별 PK/FK/컬럼·제약. **전체 테이블 구조 한눈에 보기용.** |
| DB 스키마 변경 사항 | `docs/DB_Schema_Changes.md` | init-db.sql 기준 변경 이력, 제약조건·인덱스 변경 내용. |
| DB 변경 요약 | `docs/Database_Changes_Summary.md` | DB 변경 사항 요약. |
| **SQL DDL (실제 스키마)** | `scripts/init-db.sql` | CREATE TABLE / ENUM / 인덱스 등 **실제 적용 DDL**. |
| 스키마 export 스크립트 | `scripts/export_schema_sql.py` | 스키마 SQL 내보내기용. |

**ORM 모델 (코드 기준)**  
- `app/infrastructure/persistence/models/`  
  - `exams.py`, `participants.py`, `problems.py`, `sessions.py`, `submissions.py`  
  - `enums.py` — DB ENUM 대응 (IntentAnalyzerStatus, CodeIntentType, VerdictEnum 등)

---

## 2. API ↔ DB 매핑 및 API 스키마

| 문서 | 경로 | 내용 |
|------|------|------|
| **API–DB 필드 매핑** | `docs/API_DB_Mapping_Analysis.md` | API 필드명 ↔ DB 컬럼 매핑, 불일치 정리, 테이블 구조 참고(일부). |
| API 명세 | `docs/API_Specification.md` | API 스펙. |
| API 현재 구현 | `docs/API_Current_Implementation.md` | 현재 구현 상태. |

**요청/응답 스키마 (코드)**  
- `app/presentation/schemas/` — Pydantic 모델 (chat, session, common, token 등)

---

## 3. LangGraph State 스키마

| 문서 | 경로 | 내용 |
|------|------|------|
| **State 흐름 및 DB 저장** | `docs/State_Flow_and_DB_Storage.md` | MainGraphState·Redis·PostgreSQL 형식 차이, 메시지 변환, 저장 전략. |
| LangGraph State 흐름 | `docs/LangGraph_State_Flow.md` | State 필드·플로우 설명. |

**State 정의 (코드)**  
- `app/domain/langgraph/states.py`  
  - `MainGraphState` (TypedDict)  
  - `EvalTurnState`  
  - Pydantic: `IntentClassification`, `TurnAnalysis`, `IntegratedEvaluationResult` 등

---

## 4. 빠르게 찾기

| 보고 싶은 것 | 보면 되는 문서/파일 |
|--------------|----------------------|
| **DB 테이블·컬럼·관계 전체** | `테이블명세서.md` |
| **DB 실제 DDL** | `scripts/init-db.sql` |
| **API 필드 ↔ DB 컬럼** | `docs/API_DB_Mapping_Analysis.md` |
| **LangGraph State 필드·저장 방식** | `docs/State_Flow_and_DB_Storage.md`, `app/domain/langgraph/states.py` |
| **평가·턴 로그 저장 위치** | `docs/Prompt_Evaluation_Storage_Location.md`, `docs/Node4_Node6_Database_Access.md` |

---

*스키마 변경 시: `테이블명세서.md`, `scripts/init-db.sql`, `DB_Schema_Changes.md` 및 해당 ORM 모델을 함께 갱신하는 것을 권장합니다.*
