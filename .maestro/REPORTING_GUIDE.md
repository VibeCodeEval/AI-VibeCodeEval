# .maestro 기록 관리 가이드

> **작성일**: 2026-03-27  
> **목적**: 프로젝트의 모든 수정 사항을 `.maestro`에 체계적으로 기록하기 위한 규칙 정의

---

## 1. 기본 원칙

1. **모든 수정 사항은 `.maestro`에 저장**한다.
2. 수정 및 기록 후 **반드시 사용자에게 컨펌**을 받는다.
3. 기록은 **코드 수정 사항**, **계획 수정 사항**, **API 변경 사항**으로 나뉘어 저장한다.

---

## 2. 일일 보고서 구조

### 2.1 디렉토리

```
.maestro/reports/daily/{YYYY-MM-DD}/
  code_changes.md       # 코드 수정 사항
  plan_changes.md       # 계획 수정 사항
  api_changes.md        # API 변경 사항
```

- 날짜별로 폴더를 생성한다 (예: `2026-03-27/`).
- 해당 날짜에 변경이 없는 카테고리의 파일은 생성하지 않아도 된다.

### 2.2 code_changes.md (코드 수정 사항)

기록 항목:
- **수정된 파일 경로**
- **변경 내용 요약** (무엇이 바뀌었는지)
- **변경 사유** (왜 바꿨는지)
- **관련 Step/Phase** (해당되는 경우)

형식 예시:
```markdown
## [변경 카테고리명]

| 파일 | 변경 내용 | 사유 |
|------|-----------|------|
| `경로/파일.py` | 변경 설명 | 변경 이유 |
```

### 2.3 plan_changes.md (계획 수정 사항)

기록 항목:
- **변경된 계획 문서** (어떤 .maestro 문서가 변경되었는지)
- **변경 전/후 내용**
- **변경 사유**
- **영향 범위**

### 2.4 api_changes.md (API 변경 사항)

기록 항목:
- **변경된 엔드포인트** (외부 REST API)
- **내부 인터페이스 변경** (LangGraph State, Pydantic 모델 등)
- **요청/응답 스키마 변경**
- **호환성 영향**
- **변경 사유**

---

## 3. .maestro 문서 갱신 규칙

코드 수정 시 연관된 `.maestro` 문서도 함께 갱신한다:

| 상황 | 갱신 대상 |
|------|-----------|
| 모든 수정 | `maestro_state.json` (last_updated, progress, notes) |
| 코드/기능 변경 | `docs/V2.1_Change_Log.md` (변경 이력 추가) |
| 할일 완료/추가 | `docs/V2.1_할일_체크리스트.md` (체크/항목 추가) |
| 평가 구조 변경 | `docs/V2.1_Evaluation_And_Score_Structure.md` |
| Step 완료 | 해당 Step 문서의 체크리스트 갱신 |
| Phase 진행 | `maestro_state.json`의 해당 phase progress/status |
| 프롬프트 변경 | `docs/V2.1_Change_Log.md`에 프롬프트 버전/변경 내용 기록 |

---

## 4. 작업 프로세스

```
1. 코드 수정 요청 수신
2. 코드 변경 실행
3. .maestro/reports/daily/{날짜}/ 에 기록 작성
   - code_changes.md (코드 변경이 있을 때)
   - plan_changes.md (계획 변경이 있을 때)
   - api_changes.md (API 변경이 있을 때)
4. 관련 .maestro 문서 갱신
5. 사용자에게 변경 내용 보고 및 컨펌 요청
6. 승인 시 완료, 수정 필요 시 2번으로 돌아감
```

---

## 5. 기존 보고서와의 호환

- **기존 형식**: `.maestro/reports/daily/YYYY-MM-DD_daily_report.json` (2026-01-18, 2026-01-29)
- **새 형식**: `.maestro/reports/daily/YYYY-MM-DD/` 폴더 내 Markdown 파일
- 기존 JSON 보고서는 그대로 유지하고, 2026-03-27부터 새 형식을 적용한다.

---

## 6. 참조 문서

| 문서 | 경로 | 설명 |
|------|------|------|
| 프로젝트 상태 | `.maestro/maestro_state.json` | 전체 진행 상태/메트릭 |
| 변경 이력 | `.maestro/docs/V2.1_Change_Log.md` | V2.1 변경 기록 |
| 할일 체크리스트 | `.maestro/docs/V2.1_할일_체크리스트.md` | 완료/미완료 항목 |
| 작업 지시 인덱스 | `.maestro/docs/V2.1_Work_Instructions_Index.md` | Step별 지시문 링크 |
| 평가 구조 | `.maestro/docs/V2.1_Evaluation_And_Score_Structure.md` | 점수 합산/학점 산정 |
| Phase 6 계획 | `.maestro/PHASE6_PLAN.md` | Phase 6 상세 계획 |
