# plan_changes — 2026-05-21

## 배경

- 관리자/덤프 JSON에서 `code_scores.score.total_score`와 `rubric_json.grade`가 **직관과 불일치** (예: exam1 P4 — 총점 82, grade D).
- 토론(N8) verdict는 `holistic_flow_score` 기준 `_derive_grade`로 **B**를 내지만, N9 저장 grade는 **correctness 100% 미만 → D/F 고정** 분기였음.

## 결정

1. **최종 등급 SoT = `total_score` (0~100 가중 합)**  
   - 프롬프트 40% + 정확성(환산) 40% + 성능 20%와 **동일 축**으로 해석 가능하게 통일.
2. **Correctness·ΔCC·AST로 grade를 덮어쓰지 않음**  
   - 정확성·CC는 이미 `total_score`에 포함; 이중 감점 제거.
3. **임계값**  
   - 90/80/70/60 — debate `_GRADE_THRESHOLDS`와 동일 (유지보수 시 한곳만 바꾸도록 문서화).

## 미포함 (후속 검토)

- N8 verdict `grade`를 `total_score`와 **강제 동기화** (현재는 holistic 82 → B, total 82 → B로 우연 일치 가능).
- 기존 DB row `grade` 일괄 재계산 스크립트 (필요 시 `submission_id`별 N9 재실행).
