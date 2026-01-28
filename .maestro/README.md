# 🎼 Maestro Orchestration System

> AI Agent 협업을 위한 중앙 명령 및 상태 관리 시스템

## 📁 폴더 구조

```
.maestro/
├── README.md              # 이 파일
├── maestro_state.json     # Maestro 전체 상태 (읽기 전용 - Maestro만 수정)
├── tasks/                 # Phase별 작업 정의 및 상태
│   ├── phase1_upgrade.json
│   ├── phase2_testing.json
│   ├── phase3_review.json
│   ├── phase4_features.json
│   └── phase5_finetuning.json
├── commands/              # Agent 간 명령 전달
│   ├── pending/           # 대기 중인 명령 (하부 Agent가 읽음)
│   └── completed/         # 완료된 명령 (하부 Agent가 작성)
├── reports/               # 작업 보고서
│   └── daily/             # 일일 진행 보고
└── shared/                # 공유 컨텍스트
    └── project_context.json
```

## 🔄 워크플로우

### Maestro (명령권자)
1. `maestro_state.json` 업데이트로 전체 프로젝트 상태 관리
2. `commands/pending/` 에 새 명령 파일 생성
3. `commands/completed/` 에서 완료 보고 확인
4. `tasks/*.json` 으로 Phase별 상세 진행률 추적

### 하부 Agent
1. `commands/pending/` 폴더 확인하여 할당된 작업 수령
2. 작업 수행
3. `commands/completed/` 에 완료 보고 작성
4. 해당 `tasks/*.json` 상태 업데이트

## 📋 파일 형식

### 명령 파일 (commands/)
```json
{
  "command_id": "CMD_001",
  "timestamp": "2026-01-18T10:00:00Z",
  "from": "maestro",
  "to": "agent_phase4",
  "priority": "high",
  "task_phase": "phase4",
  "action": "implement_feature",
  "description": "Rate Limiter 구현",
  "requirements": [...],
  "deadline": "2026-01-25",
  "status": "pending"
}
```

### 완료 보고 (commands/completed/)
```json
{
  "command_id": "CMD_001",
  "completed_at": "2026-01-20T15:30:00Z",
  "agent": "agent_phase4",
  "status": "completed",
  "result": {
    "files_modified": [...],
    "tests_passed": true,
    "notes": "..."
  }
}
```

## 🏷️ 상태 값

| 상태 | 설명 |
|------|------|
| `pending` | 대기 중 |
| `in_progress` | 진행 중 |
| `blocked` | 차단됨 (의존성 문제) |
| `review` | 검토 대기 |
| `completed` | 완료 |
| `cancelled` | 취소됨 |

## ⚠️ 규칙

1. **maestro_state.json**: Maestro만 수정 가능
2. **tasks/*.json**: 해당 Phase 담당 Agent만 수정 가능
3. **commands/pending/**: Maestro가 생성, 하부 Agent가 읽기만
4. **commands/completed/**: 하부 Agent가 생성, Maestro가 읽기만
5. 모든 파일은 UTF-8 JSON 형식

---
*Created by Maestro Agent - 2026-01-18*
