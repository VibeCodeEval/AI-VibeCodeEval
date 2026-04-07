# Gemini API 비용 추정 (세션 단위)

> **목적**: Google AI Studio / Gemini Developer API 공식 단가를 기준으로, **대화 N턴 + 제출 1회** 같은 세션 시나리오의 **LLM 비용(USD)**을 구간 추정한다.  
> **연계 문서**: [LangGraph_API_Call_Map.md](./LangGraph_API_Call_Map.md) (호출 구조·노드별 LLM/Judge0)  
> **가격 출처**: [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) (표는 문서 발행 시점 기준; 변경 시 공식 페이지를 우선한다)

---

## 1. 공식 단가 (Paid · Standard)

| 모델 ID | 입력 (USD / 1M tokens) | 출력 (USD / 1M tokens) |
|---------|-------------------------|-------------------------|
| `gemini-2.5-flash` | $0.30 (텍스트·이미지·비디오) | $2.50 (thinking 포함) |
| `gemini-2.5-pro` | $1.25 (프롬프트 ≤200k) · $2.50 (>200k) | $10.00 (≤200k) · $15.00 (>200k) |

- **Batch / Flex / Priority** 티는 별도 표가 있음 → 대량·비동기 배치 시 공식 페이지 확인.
- **GCP Vertex AI**는 통상 유사한 $/M 구조를 쓰나, 리전·약정·통화에 따라 달라질 수 있음 → [Vertex AI Generative AI pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing).

---

## 2. 본 프로젝트에서의 모델 매핑

| 구간 | 설정 위치 | 기본 모델 |
|------|-----------|-----------|
| 채팅 n2·n3, eval_turn, N7 등 | `app/core/config.py` → `DEFAULT_LLM_MODEL` | `gemini-2.5-flash` |
| N8 토론 | `app/domain/langgraph/prompts/debate_agents.yaml` | **strict / neutral / verdict** → `gemini-2.5-pro`, **advocate** → `gemini-2.5-flash` |

N8 호출당: **Pro 5회** (R1 strict·neutral, R2 strict·neutral, final_verdict) + **Flash 2회** (R1·R2 advocate).

---

## 3. 참고 데이터 (토큰·컨텍스트 스케일)

실제보낸 JSON은 “짧은 대화” 가정보다 훨씬 큰 토큰을 쓸 수 있음을 시사한다.

| 파일 | 참고 포인트 |
|------|-------------|
| `data/15_5_평가.json` | `meta.total_tokens` **36,785**; 단일 AI 메시지 `token_count` **12,072** 등 **코드 블록 포함 응답**으로 턴당 토큰 폭증 가능 |
| `data/17_7_debate.json` | N8 결과(의견·반론·분석)가 장문 → **출력**이 크고, 실행 시 **문제·코드·Judge0/Radon·N7·턴 로그**가 **입력**에 붙어 Pro/Flash 호출당 만 토큰 단위 과금이 나가기 쉬움 |

문서화용 **보수적 시나리오**와 **실데이터 스케일 경고**를 구분해 둔다.

---

## 4. 계산 가정 (예: 대화 10턴 + 제출)

다음은 **스프레드시트·감 잡기용** 가정이다. 실제 비용은 프롬프트 길이·출력 JSON·thinking 토큰에 좌우된다.

| 항목 | 가정 |
|------|------|
| 대화 | 사용자 **10메시지** + AI **10응답** (일반 채팅) |
| 턴당 사용자 분량 | **약 200단어** → 대략 **250~300 tokens/턴** (영·한 혼용 시 상향 가능) |
| 턴당 AI 분량 | **짧은 답변 시나리오**: **300~450 tokens/턴**; 코드가 길면 `15_5`처럼 **수천~1만+** 가능 |
| 제출 | **1회** 그래프 실행: Eval Turn **과거 10턴** 서브그래프 + N7 + N8 (+ N5 Judge0는 **LLM 과금 아님**) |
| 파싱 폴백·재시도 | 미포함 (발생 시 Flash/Pro 호출 증가) |

**비용 공식 (호출 1회)**

- Flash: `cost = (input_tokens / 10^6) × 0.30 + (output_tokens / 10^6) × 2.50`
- Pro (≤200k): `cost = (input_tokens / 10^6) × 1.25 + (output_tokens / 10^6) × 10.00`

---

## 5. 시나리오별 추정 구간 (LLM만, USD)

### 5.1 짧은 대화 가정 (200단어/턴·짧은 AI)

| 블록 | 설명 | 대략 구간 |
|------|------|-----------|
| 채팅 10턴 | n2+n3 각 10회, 전부 Flash; 누적 히스토리 + 시스템 지시문 반영 | **~$0.05 ~ $0.10** |
| 제출 시 의도 | 제출 요청 1회, Flash, 긴 히스토리 | **~$0.003 ~ $0.01** |
| Eval Turn ×10 | 턴마다 Flash 다회(의도·평가·요약); 문제 컨텍스트·이전 턴 요약 포함 | **~$0.10 ~ $0.25** |
| N7 | 코드 리뷰 1회 Flash | **~$0.008 ~ $0.02** |
| N8 | Pro 5 + Flash 2; 컨텍스트 **만 토큰**대 입력 가정 | **~$0.35 ~ $0.60** |

**합계(거친 범위): 약 $0.55 ~ $1.0 / 세션**  
원화 환산은 환율 변동이 크므로 **USD 기준**을 기본으로 두고, 필요 시 `합계 USD × 환율`로 계산.

### 5.2 `15_5_평가.json` 수준 (긴 코드 응답·긴 평가 컨텍스트)

- 턴당 AI가 **수천~1만+ 토큰**이면 채팅만으로 **입력 10만~수십만 토큰** 누적 가능.
- Eval Turn 입력(평가 대상 AI 답변)·N8 입력(턴 로그 전체)이 함께 커져 **5.1 대비 수 배~한 자릿수**까지 갈 수 있음.
- 정량화는 **실제 로그의 `token_count`·빌링 대시보드**로 보정하는 것이 안전.

---

## 6. LLM 과금에 포함되지 않는 항목

| 항목 | 비고 |
|------|------|
| **Judge0 / 실행 큐** | N5 코드 실행·인프라·워커 비용 (별도) |
| **Redis / DB / 앱 서버** | 인스턴스·스토리지 |
| **Google Search Grounding** | 사용 시 [pricing](https://ai.google.dev/gemini-api/docs/pricing) 별도 |
| **Context caching** | 사용 시 저장·캐시 읽기 단가 별도 |

---

## 7. 유지보수 체크리스트

1. **분기마다** [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)에서 2.5 Flash/Pro 표를 확인한다.
2. `debate_agents.yaml`·`DEFAULT_LLM_MODEL`이 바뀌면 본 문서 **§2**를 갱신한다.
3. 비용 상한을 맞추려면 **출력 토큰**(구조화 JSON, thinking)과 **N8 입력의 turn_logs 길이**를 먼저 제한하는 편이 효과가 크다.

---

## 8. 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-05 | 초안: 공식 단가, 모델 매핑, 데이터 파일 참고, 10턴+제출 구간 추정, 비포함 항목 |
