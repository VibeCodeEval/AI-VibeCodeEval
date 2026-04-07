# 에이전트 운영 가이드

> **작성일**: 2026-03-27  
> **목적**: AI-VibeCodeEval 프로젝트의 에이전트 계층 구조와 운영 규칙 정의

---

## 1. 에이전트 계층 구조

```
사용자
└── 프로젝트 마에스트로 (project_maestro.md) ← 최상위 총괄
    ├── 그래프 오케스트레이터 (graph_orchestrator.md)
    │   ├── states.py / graph.py 총괄
    │   └── 하위 에이전트 작업 지시
    │
    ├── 채팅 루프 에이전트 (chat_loop_agent.md)
    │   └── chat: n1_handle_request → n2_intent_analyzer → n3_writer + system/system_nodes
    │
    ├── 평가 오케스트레이터 (eval_orchestrator.md)
    │   ├── 평가 전략/점수 병합 규칙 관리
    │   ├── 턴 평가 에이전트 (turn_eval_agent.md)
    │   │   └── n4_eval_turn_guard + eval_turn/ 서브그래프 (8종 평가 노드)
    │   └── Holistic/점수 에이전트 (holistic_score_agent.md)
    │       └── eval: n5_integrated_evaluator → n6_holistic_flow → n7/n9 집계·최종 → n8_code_execution
    │
    └── Submit 테스트·평가 덤프 에이전트 (submit_test_agent.md)
        └── 시드·check_submit_result·export_evaluation_json·debate_redis·.maestro/DOCS 테스트 가이드
```

## 2. 에이전트 요약

| 에이전트 | 파일 | 핵심 역할 |
|----------|------|-----------|
| **프로젝트 마에스트로** | `project_maestro.md` | 프로젝트 전체 총괄, .maestro 관리, 파일/문서 구조, 모든 에이전트 조율 |
| **그래프 오케스트레이터** | `graph_orchestrator.md` | State/Graph 총괄, LangGraph 구조, 하위 에이전트 조율 |
| **채팅 루프** | `chat_loop_agent.md` | 요청 처리 → 의도 분석 → 응답 생성 → 시스템 노드 |
| **평가 오케스트레이터** | `eval_orchestrator.md` | 평가 파이프라인 전략, Agent 간 조율, 새 평가 방식 설계 |
| **턴 평가** | `turn_eval_agent.md` | 턴별 프롬프트 품질 평가, 의도별 루브릭, 서브그래프 |
| **Holistic/점수** | `holistic_score_agent.md` | 통합 평가, 전략 평가, 점수 집계, 코드 실행 |
| **Submit 테스트·평가 덤프** | `submit_test_agent.md` | `setup_submit_test_data`, `check_submit_result`, `export_evaluation_json`, `dump_debate_redis`, `debate_redis_dump`, `.maestro/DOCS` 테스트·ENV 가이드 |

## 3. 새 세션 시작 절차

```
1. Cursor에서 새 채팅 세션 열기
2. 첫 메시지로 해당 에이전트의 시스템 프롬프트 파일 내용 전달
   예: "다음은 너의 역할이야. [graph_orchestrator.md 내용 붙여넣기]"
3. 이어서 구체적인 작업 지시
4. 에이전트는 작업 후 반드시 .maestro에 기록하고 사용자에게 컨펌 요청
```

## 4. 에이전트 간 소통 규칙

에이전트는 서로 직접 대화하지 않는다. 모든 소통은 **`.maestro` 파일 시스템**을 통해 이루어진다.

### 작업 지시 (상위 → 하위)
- 그래프 오케스트레이터 또는 평가 오케스트레이터가 `.maestro/commands/pending/` 에 작업 명령 JSON 작성
- 하위 에이전트는 세션 시작 시 pending 명령을 확인하고 실행

### 작업 완료 보고 (하위 → 상위)
- 작업 완료 후 `.maestro/commands/completed/` 에 완료 보고 JSON 작성
- `.maestro/reports/daily/{YYYY-MM-DD}/` 에 변경 내역 기록 (code_changes.md, plan_changes.md, api_changes.md)

### State 변경 요청
- 하위 에이전트가 `states.py`에 필드를 추가해야 할 때는 직접 수정하지 않음
- `.maestro/commands/pending/` 에 State 변경 요청을 작성
- 그래프 오케스트레이터가 검토 후 반영

## 5. 작업 프로세스 (모든 에이전트 공통)

```
1. .maestro/maestro_state.json 읽어서 현재 상태 파악
2. 담당 범위 내의 코드 분석
3. 코드 수정 실행
4. .maestro/reports/daily/{날짜}/ 에 변경 기록
   - code_changes.md: 코드 수정 사항 (파일, 내용, 사유)
   - plan_changes.md: 계획 변경 사항
   - api_changes.md: API/인터페이스 변경 사항
5. 관련 .maestro 문서 갱신 (maestro_state.json 등)
6. 사용자에게 변경 내용 보고 및 컨펌 요청
7. 승인 시 완료, 수정 필요 시 3번으로 돌아감
```

## 6. 금지 사항 (모든 에이전트 공통)

- 담당 범위 밖의 코드를 직접 수정하지 않는다
- `states.py` State 필드 추가는 그래프 오케스트레이터만 한다
- `graph.py` 노드/엣지 변경은 그래프 오케스트레이터만 한다
- `.env`, 인증 정보, 시크릿은 절대 수정하지 않는다 (값 변경·커밋 금지). **예외**: `submit_test_agent`는 문서·`.env.example`(존재 시)에 변수 **이름·의미**만 기술한다.
- 수정 후 .maestro 기록 없이 작업을 끝내지 않는다
- 사용자 컨펌 없이 대규모 변경을 실행하지 않는다

## 7. 핵심 참조 문서

| 문서 | 경로 | 용도 |
|------|------|------|
| 프로젝트 상태 | `.maestro/maestro_state.json` | 전체 진행 상태 |
| 문서 참조 가이드 | `.maestro/DOCS_REFERENCE.md` | docs/ 파일별 설명/참조 시점 |
| 기록 관리 가이드 | `.maestro/REPORTING_GUIDE.md` | 리포트 작성 규칙 |
| 변경 이력 | `.maestro/docs/V2.1_Change_Log.md` | V2.1 변경 기록 |
| 평가 구조 | `.maestro/docs/V2.1_Evaluation_And_Score_Structure.md` | 점수/학점 구조 |
| 문서 인덱스 | `docs/문서_인덱스.md` | docs/ 전체 목록 |

## 8. 새 평가 에이전트 추가 절차

새로운 평가 방식(예: 코드 보안 평가, 멀티모델 Judge)을 추가할 때:

```
1. 평가 오케스트레이터에게 설계 요청
2. 평가 오케스트레이터가 새 에이전트 시스템 프롬프트 초안 작성
   → .maestro/agents/{새_에이전트}.md
3. 그래프 오케스트레이터에게 graph.py 노드 추가 요청
4. 그래프 오케스트레이터가 State 필드 추가 + graph.py 노드 연결
5. 새 에이전트 세션 시작하여 구현
6. 평가 오케스트레이터가 점수 병합 규칙 업데이트
7. AGENT_OVERVIEW.md 갱신
```
