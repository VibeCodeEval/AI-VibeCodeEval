# 프론트 평가결과 DTO 명세

## 목적
- 프론트엔드는 백엔드와만 통신한다.
- 백엔드는 DB(`scores`, `prompt_evaluations`)에서 값을 조회해 아래 DTO로 가공해 반환한다.
- 이 문서는 "화면 표시 순서" 기준으로 DTO를 정의한다.

## 화면 표시 순서
1. 최종 합산 점수
2. Holistic 분석(`holistic_flow_analysis`)
3. 턴별 프롬프트 평가 (점수 상단)
4. 코드 평가 내용 (점수 상단)
5. 전체 평가 내용 (점수 상단)

## 점수 해석 원칙 (중요)
- `total_score`가 최종 성적표의 기준 점수다.
- `holistic_flow_score`는 최종 총점이 아니라, N8 토론 기반의 정성적 종합 판단 점수다.
- 현재 파이프라인은 다음 순서로 계산된다.
  - N8: `holistic_flow_score` 산출 (토론 기반 종합 판단)
  - N9: `prompt_score` 계산 시 `holistic_flow_score`를 반영한 뒤, `correctness_score`/`performance_score`와 가중합하여 `total_score` 산출
- 따라서 프론트 노출 시 라벨을 명확히 분리한다.
  - `total_score`: "최종 합산 점수"
  - `holistic_flow_score`: "토론 기반 종합 판단 점수 (참고)"

---

## DB 조회 기준

### 1) 제출 기준 최종 점수 (`scores`)
- 조건: `scores.submission_id = :submissionId`
- 주요 컬럼:
  - `prompt_score`
  - `correctness_score`
  - `perf_score`
  - `total_score`
  - `rubric_json`
  - `created_at`

예시 SQL:
```sql
SELECT
  submission_id,
  prompt_score,
  correctness_score,
  perf_score,
  total_score,
  rubric_json,
  created_at
FROM scores
WHERE submission_id = :submissionId
LIMIT 1;
```

### 2) 턴별 프롬프트 평가

**권장 (단일 조회)**: `scores.rubric_json.turn_evaluations[]` — N9 저장 시 `prompt_evaluations.details`와 동일한 스냅샷.

**대안 (레거시·감사)**: `prompt_evaluations` 테이블 직접 조회.

- 조건:
  - `prompt_evaluations.session_id = :sessionId`
  - `prompt_evaluations.evaluation_type = 'TURN_EVAL'`
- 정렬: `turn ASC`
- 주요 컬럼:
  - `turn`
  - `details` (JSON)
  - `created_at`

예시 SQL:
```sql
SELECT
  id,
  session_id,
  turn,
  evaluation_type,
  details,
  created_at
FROM prompt_evaluations
WHERE session_id = :sessionId
  AND evaluation_type = 'TURN_EVAL'
ORDER BY turn ASC;
```

---

## 백엔드 응답 DTO (권장)

```ts
export interface EvaluationResultResponseDto {
  summary: FinalScoreSummaryDto;
  holistic: HolisticAnalysisDto;
  turnEvaluations: TurnEvaluationItemDto[];
  codeEvaluation: CodeEvaluationDto;
  overallEvaluation: OverallEvaluationDto;
}
```

### 1) 최종 합산 점수 DTO
```ts
export interface FinalScoreSummaryDto {
  submissionId: number;
  grade: string; // A/B/C/D/F
  totalScore: number; // 최종 총점
  promptScore: number;
  correctnessScore: number;
  performanceScore: number;
  weights: {
    prompt: number;
    correctness: number;
    performance: number;
  };
  createdAt: string; // ISO datetime
}
```

매핑:
- `submissionId` <- `scores.submission_id`
- `grade` <- `scores.rubric_json.grade`
- `totalScore` <- `scores.total_score`
- `promptScore` <- `scores.prompt_score`
- `correctnessScore` <- `scores.correctness_score`
- `performanceScore` <- `scores.perf_score`
- `weights` <- `scores.rubric_json.weights`
- `createdAt` <- `scores.created_at`

### 2) Holistic 분석 DTO
```ts
export interface HolisticAnalysisDto {
  holisticFlowScore: number | null;
  r4ContextMaintenanceScore: number | null;
  analysisText: string | null; // holistic_flow_analysis
}
```

매핑:
- `holisticFlowScore` <- `scores.rubric_json.holistic_flow_score`
- `r4ContextMaintenanceScore` <- `scores.rubric_json.r4_context_maintenance_score`
- `analysisText` <- `scores.rubric_json.holistic_flow_analysis`

### 3) 턴별 프롬프트 평가 DTO
```ts
export interface TurnEvaluationItemDto {
  turn: number;
  turnScore: number | null;
  unifiedIntent: string | null;
  appliedRubrics: string[];
  rubricBreakdown: Record<string, number>;
  analysis: string | null;
  scoringCot: Record<string, string>;
  intentCot: string | null;
  userPromptSummary: string | null;
  llmAnswerSummary: string | null;
  createdAt: string; // ISO datetime
}
```

매핑 (`details` 기준 — 출처는 아래 둘 중 하나):

| 출처 | 경로 |
|------|------|
| **권장** | `scores.rubric_json.turn_evaluations[]` → 각 항목의 `details` |
| 대안 | `prompt_evaluations` 행 → `details` |

- `turn` <- `turn_evaluations[].turn` 또는 `prompt_evaluations.turn`
- `turnScore` <- `details.turn_score`
- `unifiedIntent` <- `details.unified_intent`
- `appliedRubrics` <- `details.applied_rubrics` (없으면 `[]`)
- `rubricBreakdown` <- `details.rubric_breakdown` (없으면 `{}`)
- `analysis` <- `details.analysis`
- `scoringCot` <- `details.scoring_cot` (없으면 `{}`)
- `intentCot` <- `details.intent_cot` (의도 분류 CoT, 없으면 `null`)
- `userPromptSummary` <- `details.user_prompt_summary`
- `llmAnswerSummary` <- `details.llm_answer_summary`
- `createdAt` <- `prompt_evaluations.created_at` (`rubric_json` 경로만 쓸 때는 `scores.created_at` 또는 `null`)

### 4) 코드 평가 내용 DTO
```ts
/** N5 Judge0 TC 집계 (rubric_json.tc_summary). 통과 TC만 시간·메모리 평균 */
export interface TcSummaryDto {
  averagePassRate: number;       // passed / total × 100 (%)
  averageTimeSec: number | null; // passed TC만 평균
  averageMemoryMb: number | null;
  testCasesPassed: number;
  testCasesTotal: number;
}

/** N6 reference_code 대비 제출 Radon CC 상승률 (rubric_json.reference_cc_summary) */
export interface ReferenceCcSummaryDto {
  referenceAvgCc: number | null;
  referenceMaxCc: number | null;
  submissionAvgCc: number | null;
  submissionMaxCc: number | null;
  /** reference 대비 submission CC 상승률(%) — N6 delta_cc_vs_reference.delta_cc_pct */
  deltaCcPct: number | null;
}

export interface CodeEvaluationDto {
  correctnessScore: number;
  performanceScore: number;
  /** N5 TC 요약. Judge0 미실행 시 null */
  tcSummary: TcSummaryDto | null;
  /** reference_code 있을 때만. 없으면 null */
  referenceCcSummary: ReferenceCcSummaryDto | null;
  correctnessDetails: {
    testCasesPassed?: number;
    testCasesTotal?: number;
    passRate?: number;
    correctnessReasoning?: string | null;
    /** Judge0 TC별 상세 (N5 → rubric_json). 실패·타임아웃 시 `[]` */
    testCases?: Array<{
      index: number;
      input: string;
      expected: string;
      actual: string;
      passed: boolean;
      statusId?: number | null;
      statusDescription?: string | null;
      timeSec?: number | null;
      memoryMb?: number | null;
      stderr?: string | null;
      compileOutput?: string | null;
    }>;
  } | null;
  performanceDetails: {
    executionTime?: number | null;
    memoryUsedMb?: number | null;
    timeLimitSec?: number | null;
    memoryLimitMb?: number | null;
    skipPerformance?: boolean;
    skipReason?: string | null;
    /** TC별 실행 시간·메모리·raw 성능 점수 (passed TC만 raw > 0) */
    testCases?: Array<{
      index: number;
      passed: boolean;
      timeSec?: number | null;
      memoryMb?: number | null;
      rawPerformanceScore?: number | null;
    }>;
  } | null;
  codeEvalReport: {
    overallSummary?: string;
    efficiencyReview?: string;
    readabilityReview?: string;
    errorHandlingReview?: string;
    scoreAdjustmentNote?: string;
  } | null;
}
```

매핑 (`scores` + `scores.rubric_json`):
- `correctnessScore` <- `scores.correctness_score`
- `performanceScore` <- `scores.perf_score`
- `tcSummary` <- `rubric_json.tc_summary` (snake_case → camelCase)

  | DTO | rubric_json |
  |-----|-------------|
  | `averagePassRate` | `average_pass_rate` |
  | `averageTimeSec` | `average_time_sec` |
  | `averageMemoryMb` | `average_memory_mb` |
  | `testCasesPassed` | `test_cases_passed` |
  | `testCasesTotal` | `test_cases_total` |

- `referenceCcSummary` <- `rubric_json.reference_cc_summary` (`deltaCcPct` <- `delta_cc_pct`, reference/submission avg·max CC)

- `correctnessDetails` <- `rubric_json.correctness_details` (`testCases` <- `test_cases`)
- `performanceDetails` <- `rubric_json.performance_details` (`testCases` <- `test_cases`)
- `codeEvalReport` <- `rubric_json.code_eval_report`

### 5) 전체 평가 내용 DTO
```ts
export interface OverallEvaluationDto {
  totalScore: number;
  grade: string;
  consensusSummary: string | null;
  debateVerdict: {
    holisticFlowScore?: number | null;
    r4ContextMaintenanceScore?: number | null;
  } | null;
  fullHolisticAnalysis: string | null;
}
```

매핑:
- `totalScore` <- `scores.total_score`
- `grade` <- `scores.rubric_json.grade`
- `fullHolisticAnalysis` <- `scores.rubric_json.holistic_flow_analysis`
- `consensusSummary` <- `rubric_json.debate_log`에서 `agent='verdict'` 항목의 `consensus_summary`
- `debateVerdict.holisticFlowScore` <- verdict의 `holistic_flow_score`
- `debateVerdict.r4ContextMaintenanceScore` <- verdict의 `r4_context_maintenance_score`

---

## 구현 메모 (백엔드)

### `scores.rubric_json` 추가 필드 (2026-05-18~)

```json
{
  "tc_summary": {
    "average_pass_rate": 100.0,
    "average_time_sec": 0.045,
    "average_memory_mb": 3.38,
    "test_cases_passed": 10,
    "test_cases_total": 10
  },
  "turn_evaluations": [
    {
      "turn": 1,
      "evaluation_type": "TURN_EVAL",
      "details": { "...": "prompt_evaluations.details 와 동일 스키마" }
    }
  ],
  "reference_cc_summary": {
    "has_reference_code": true,
    "reference_avg_cc": 5.0,
    "reference_max_cc": 6,
    "submission_avg_cc": 7.0,
    "submission_max_cc": 8,
    "delta_cc_pct": 40.0,
    "delta_cc_vs_reference": {
      "delta_cc_pct": 40.0,
      "v1_avg_cc": 5.0,
      "v2_avg_cc": 7.0,
      "v1_max_cc": 6,
      "v2_max_cc": 8
    }
  }
}
```

- `reference_cc_summary`: N6 `checker_json.reference_code` 대비 제출 코드 Radon CC. `delta_cc_pct` = 상승률(%). reference 없으면 필드 자체가 `null`.
- 상세 원본은 `code_quality_metrics.reference_radon_cc` / `delta_cc_vs_reference`에도 유지.
- `tc_summary.average_time_sec` / `average_memory_mb`: **통과(passed) TC만** 평균. 해당 TC가 없으면 `null`.
- `turn_evaluations`: N4 저장 시점의 `prompt_evaluations.details` 스냅샷. 제출 시점 단일 조회용.

### 조회 전략
- **권장**: `scores` 1건 조회만으로 최종 점수·Holistic·코드 평가·**턴별 평가**까지 구성 가능 (`rubric_json.turn_evaluations`).
- **대안**: 턴별 `created_at`·행 `id`가 필요하면 `prompt_evaluations(TURN_EVAL)` 추가 조회.
- `rubrics` 배열은 최신 구조에서 비어 있을 수 있으므로, 프론트는 `rubric_breakdown`/`applied_rubrics`를 우선 사용한다.
