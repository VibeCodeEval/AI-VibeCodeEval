# 계획 변경 기록 - 2026-04-04

> **작성일**: 2026-04-04  
> **작성자**: Antigravity (AI Agent)  
> **관련 Phase**: Phase 6 → 신규 평가 파이프라인 재설계

---

## 변경 배경

기존 평가 파이프라인(N5~N8)의 구조적 문제 발견 및 전면 재설계 결정.

### 기존 문제점
- **N5(integrated_evaluator)**: spec_extractor 미연결로 사실상 동작하지 않음 (`integrated_score = None` 항상 반환)
- **N6(holistic_flow)**: 대화 전략 평가 LLM이었으나, 코드 정적 분석과 역할 혼재
- **N7(aggregate_turn_scores)**: 단순 평균 계산만 수행 (LLM 활용 없음)
- **N8(eval_code_execution)**: Judge0 실행 역할이었으나 새 구조에서 재배치 필요

---

## 신규 평가 파이프라인 설계 (N5~N8)

### 변경 전

```
N4(eval_turn_guard) 
  → N5(integrated_evaluator, 빈 노드) 
  → N6(eval_holistic_flow, 전략 LLM) 
  → N7(aggregate_turn_scores, 평균 계산) 
  → N8(eval_code_execution, Judge0) 
  → N9(aggregate_final_scores)
```

### 변경 후

```
N4(eval_turn_guard, 단일 Turn 평가 → turn_logs 저장)
  → N5(eval_code_execution, Judge0 실행)
  → N6(eval_static_analysis, Radon CC 정적 분석)
  → N7(eval_code_agent, 코드 리뷰 LLM - 단일 에이전트)
  → N8(holistic_debate_flow, 다중 에이전트 토론 - 추후 구현)
  → N9(aggregate_final_scores, 최종 집계 + DB 저장)
```

---

## 노드별 변경 상세

### N5: eval_code_execution (신규 역할)
- **기존**: turn_analysis 기반 규칙 점수 (동작 안 함)
- **변경**: Judge0 실행 (기존 N8 로직 이식)
- **출력**: `code_correctness_score`, `code_performance_score`, `test_cases_passed`, `execution_time`, `memory_used_mb`

### N6: eval_static_analysis (신규 역할)
- **기존**: Holistic Flow LLM (전략/체이닝 평가)
- **변경**: Radon CC 정적 분석 전담 노드
- **출력**: `code_quality_metrics` (radon_cc, delta_cc, ast_pattern_matched, avg_cc, junior_grade)

### N7: eval_code_agent (완전 신규)
- **기존**: aggregate_turn_scores (단순 평균 계산)
- **변경**: 코드 리뷰 LLM 에이전트 (단일 LLM 호출)
- **입력**: 제출 코드 원문 + Judge0 결과(N5) + Radon CC(N6)
- **출력**: `code_eval_report` (효율성/가독성/예외처리 정성 리뷰 + 수치 포함)

### N8: holistic_debate_flow (추후 구현)
- **기존**: Judge0 실행
- **변경**: 다중 에이전트(Pro 3기) 토론으로 최종 Grade 도출
- **입력**: turn_logs(N4) + code_eval_report(N7)
- **출력**: `grade`, `prompt_score`, `holistic_analysis`
- ⚠️ **본 계획에서는 N8을 stub(임시 패스스루)으로 처리, 추후 별도 구현**

---

## 점수 구조 변경

### 고정 점수 (계산 기반, 불변)
- `code_correctness_score`: Judge0 TC 통과율 (N5)
- `code_performance_score`: 실행시간/메모리 점수 (N5)
- `code_quality_metrics`: Radon CC/AST 지표 (N6, 참고용)

### 에이전트 판단 점수 (N8, 추후)
- `grade`: 최종 학점 (A/B/C/D/F)
- `prompt_score`: N4 turn_scores 참고하되 holistic 맥락으로 조정

### 집계 (N9)
- `aggregate_turn_score`: N4 turn_scores 단순 평균 (N9에서 계산)
- 기존 SCORE 테이블 저장 유지, rubric_json 형식 변경

---

## 구현 범위 (이번 세션)

- [ ] N5 재작성 (`n5_integrated_evaluator.py` → eval_code_execution)
- [ ] N6 재작성 (`n6_holistic_flow.py` → eval_static_analysis)
- [ ] N7 재작성 (`n7_aggregate_turn_scores.py` → eval_code_agent)
- [ ] N8 stub 처리 (`n8_code_execution.py` → 임시 패스스루)
- [ ] `states.py` 신규 필드 추가 (`code_eval_report`, `code_quality_metrics`)
- [ ] `graph.py` 엣지 및 노드 등록 업데이트
- [ ] N9 aggregate_turn_score 계산 추가
- [ ] .maestro 기록 업데이트

---

## 미구현 범위 (추후)

- rubric_json 스키마 문서화
- N8 아키텍처 최종 결정 (아래 참조)

---

## N8 아키텍처 비교 검토 (결정 보류)

### 현재 구현: 법정형 (Courtroom / Chief Judge)

| 항목 | 내용 |
|------|------|
| 권력 구조 | 수직적 — 검사/변호인/중재자가 논쟁, 수석 심사관이 최종 판결 |
| 에이전트 역할 | 역할(Role) 기반: strict(검사) / advocate(변호인) / neutral(중재자) |
| Round 1 | **병렬** (Send() Fan-out) — Latency 대폭 감소 |
| Round 2 | 순차 반론 (서로의 R1 의견 참고) |
| 최종 결론 | final_verdict 노드(Gemini 2.5 Pro, temp=0.0)가 논거 질 기반 가중 판단 |
| 강점 | 실서비스 속도, 결정의 단호함, 안정적 점수 산정 |

### 원래 기획: P2P 합의형 (Peer-to-Peer Consensus)

| 항목 | 내용 |
|------|------|
| 권력 구조 | 수평적 — 3명의 도메인 전문가가 동등하게 토론 |
| 에이전트 역할 | 도메인(Domain) 기반: 알고리즘·성능 전문가 / QA·엣지케이스 엔지니어 / 클린코드·아키텍처 리뷰어 |
| Round 구조 | 최대 3라운드 순환 루프 (Agent1 → Agent2 → Agent3 반복) |
| 조기 종료 | 매 라운드 후 Router가 만장일치 체크 → 일치 시 즉시 종료 (Early Exit) |
| 최종 결론 | 3라운드 후 미합의 시 라우터가 **산술 평균**으로 강제 타결 |
| 강점 | 코드 도메인 세밀한 분석, 학술적 피어 리뷰, 직관적 역할 분담 |

### 두 방식 비교표

| 구분 | Courtroom (현재) | P2P 합의형 (원안) |
|------|-----------------|-----------------|
| 에이전트 페르소나 | 역할(검사/변호/중재) | 직무 도메인(성능/QA/아키텍처) |
| 토론 목적 | 좋은 정보를 심사관에게 제공 | 서로를 설득하여 만장일치 도달 |
| 실행 구조 | R1 병렬 + R2 순차 | 순환 루프 (최대 3회) |
| Latency | 낮음 (병렬 R1) | 높음 (순차 루프) |
| 결론 도출 | 심사관의 논거 기반 가중 판단 | 만장일치 or 산술 평균 Fallback |
| 코드 평가 적합성 | 역할 대립 구도로 다각도 검토 | 도메인 전문성이 직접 매핑 |
| 구현 복잡도 | 중간 (라우터 불필요) | 높음 (순환 엣지 + 합의 Router) |

### 결정 필요 사항

현재 Courtroom 방식을 유지하거나, P2P 합의형으로 전환하거나,
또는 **하이브리드** (도메인 기반 페르소나 + 병렬 R1 + 합의 Router) 채택 여부.
→ 사용자 결정 후 구현 방향 확정 필요.
