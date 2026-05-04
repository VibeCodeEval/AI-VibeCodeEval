# AI / 채점 서버 — `checker_json` 사용 가이드

이 문서는 DB의 `problem_specs.checker_json`(PostgreSQL `jsonb`)에 저장된 **테스트 케이스(TC)** 와 **`reference_code`** 를, AI 채점기·외부 judge가 어떻게 읽고 쓰면 되는지 정리한 것입니다. REST API를 거치지 않고 **DB만 조회**하는 전제와 맞춥니다.

## 1. 데이터 위치

| 항목 | 스키마 | 테이블 | 컬럼 |
|------|--------|--------|------|
| 스펙 본문·채점 메타 | `ai_vibe_coding_test` | `problem_specs` | `checker_json`, `content_md`, `rubric_json`, … |

제출 행(`submissions`)의 **`spec_id`** 로 해당 스펙을 조회하면 됩니다.

```sql
SELECT spec_id, problem_id, version, checker_json, content_md, rubric_json
FROM ai_vibe_coding_test.problem_specs
WHERE spec_id = :specId;
```

`checker_json`은 JSON 객체 하나입니다. 애플리케이션 배정 API는 그중 **`type`**, **`limits`**, **`restrictions`** 만 노출하지만, 채점기/AI는 **전체 JSON**을 파싱해 사용하면 됩니다.

## 2. `checker_json` 최상위 필드

| 키 | 타입 | 용도 |
|----|------|------|
| `type` | string | 채점 방식 힌트. 예: `"equality"` (출력 문자열 단순 비교 등). judge가 해석합니다. |
| `limits` | object | `timeMs`, `memoryMb` — 실행 시간·메모리 상한(힌트). |
| `restrictions` | object | `allowedLangs`, `forbiddenApis` — 허용 언어·금지 API 목록. |
| `test_cases` | array | 공개/샘플 TC 목록. 아래 스키마. |
| `reference_code` | string | **정답(참고) 구현** 소스. 언어는 문제·세트 정책과 일치시키는 것을 권장(예: Python). |

`test_cases`와 `reference_code`가 없으면 빈 배열/`{}`만 있는 스펙과 동일하게 취급하면 됩니다.

## 3. `test_cases[]` 항목 스키마

각 원소는 한 개의 TC를 나타냅니다.

| 키 | 타입 | 필수 | 설명 |
|----|------|------|------|
| `id` | string | 권장 | 식별자. 예: `"TC1"`, `"TC2"`. 로그·리포트에 사용. |
| `input` | string | 권장 | **표준 입력**으로 넣을 전체 텍스트(`\n` 줄바꿈). |
| `expected_output` | string | 권장 | **표준 출력**과 비교할 기대값. 마지막 개행 유무는 judge 정책에서 통일할 것. |
| `description` | string | 선택 | 사람이 읽는 짧은 설명. |
| `explanation` | string | 선택 | 왜 이 입·출력이 나오는지에 대한 메모. AI 설명 생성 시 참고 가능. |

채점기 동작 예시(개념):

1. 사용자(또는 모델)가 제출한 코드를 `input`을 stdin으로 실행한다.
2. stdout을 수집해 `expected_output`과 비교한다(`type`이 `equality`이면 문자열 정규화 후 비교 등).
3. 여러 TC에 대해 통과 비율·그룹(SAMPLE/PUBLIC/PRIVATE) 정책은 **judge 쪽**에서 정한다. (이 저장소의 `SubmissionRun` / `RunGroup`과 연동할 수 있음.)

**여러 줄 출력**은 `expected_output` 문자열 안에 `\n`을 포함해 저장합니다. (예: `"47\n47 1 4"`)

## 4. `reference_code` 사용 방식

`reference_code`는 **채점 파이프라인에서 선택적으로** 쓸 수 있는 필드입니다. 의도는 다음과 같습니다.

| 용도 | 설명 |
|------|------|
| **정답 실행 기준** | 동일 `input`에 대해 reference를 실행해 얻은 출력을 기대값으로 삼거나, 사용자 출력과 **이중 검증**할 때 사용. |
| **AI 평가 힌트** | 코드 품질·알고리즘 비교 시 “모범 답안” 컨텍스트로 LLM에 넘기되, **유출 방지 정책**은 제품 정책에 따름. |
| **디버깅** | TC 실패 시 올바른 로직 참고용(운영 환경에서는 접근 제한 권장). |

반드시 모든 스펙에 `reference_code`가 있는 것은 아닙니다. 없으면 **오직 `test_cases[].expected_output`** 만으로 채점하면 됩니다.

## 5. 이 백엔드와의 관계

- 시드 JSON(`src/main/resources/problems/*.json`)의 **`checkerJson`** 이 그대로 DB `checker_json`으로 들어갑니다.
- `GetAssignmentUseCase`는 응시 화면용으로 `limits` / `restrictions` / `type` 만 노출합니다. **TC·reference_code는 클라이언트에 내려가지 않습니다.**
- 따라서 **TC·정답 코드는 judge/AI 서버가 DB에서만 읽는 것**이 현재 설계와 일치합니다.

## 6. 버전·불변성

- 스펙은 `problem_id` + `version`으로 버전 관리됩니다. 한 번 배포된 스펙은 비즈니스 규칙상 불변에 가깝게 다루는 편이 안전합니다.
- `submissions.spec_id`는 응시 시작 시점에 고정된 스펙을 가리키므로, 채점 시 해당 `spec_id`의 `checker_json`만 보면 됩니다.

## 7. 예시 (`problem_id = 3` 류 스펙)

- `checker_json.type`: `"equality"`
- `checker_json.limits`: `timeMs: 2000`, `memoryMb: 256`
- `checker_json.test_cases`: `TC1` ~ `TC10` — 각각 `input`, `expected_output` 등
- `checker_json.reference_code`: Python 단일 스크립트 문자열

위 구조는 **관례(convention)** 이며, 향후 `type`별로 `test_cases` 외 필드를 추가할 수 있습니다. 추가 시 judge가 알 수 있도록 `type` 또는 `checker_version` 같은 키로 분기하는 것을 권장합니다.

---

*문서 목적: AI 서버·채점 워커 구현 시 `checker_json` 해석을 통일하기 위함.*
