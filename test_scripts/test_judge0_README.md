# Judge0 코드 제출 테스트 가이드

## 파일 구조

```
test_scripts/
├── test_judge0_submit.py      # 메인 테스트 스크립트
├── example_solution.py         # 올바른 코드 예시 (TSP 문제)
├── example_solution_wrong.py   # 잘못된 코드 예시 (테스트용)
├── test_cases.json             # 테스트 케이스 정의
├── constraints.json             # 제약 조건 정의
└── test_judge0_README.md       # 이 파일
```

## 빠른 시작

### 1. 올바른 코드로 테스트

```bash
# spec_id 사용 (하드코딩 딕셔너리)
uv run python test_scripts/test_judge0_submit.py \
  --code-file test_scripts/example_solution.py \
  --spec-id 10

# 테스트 케이스 직접 제공
uv run python test_scripts/test_judge0_submit.py \
  --code-file test_scripts/example_solution.py \
  --test-cases test_scripts/test_cases.json \
  --constraints test_scripts/constraints.json
```

### 2. 잘못된 코드로 테스트

```bash
uv run python test_scripts/test_judge0_submit.py \
  --code-file test_scripts/example_solution_wrong.py \
  --test-cases test_scripts/test_cases.json \
  --constraints test_scripts/constraints.json
```

### 3. 모든 테스트 케이스 사용

```bash
uv run python test_scripts/test_judge0_submit.py \
  --code-file test_scripts/example_solution.py \
  --test-cases test_scripts/test_cases.json \
  --all-tc
```

## 파일 설명

### example_solution.py

외판원 순회(TSP) 문제를 해결하는 올바른 코드입니다.
- 비트마스킹 DP 사용
- 모든 테스트 케이스 통과 예상

### example_solution_wrong.py

잘못된 구현 예시입니다.
- 모든 도시를 방문하지 않음
- 테스트 케이스 실패 예상

### test_cases.json

테스트 케이스 정의 파일입니다.

```json
[
  {
    "input": "4\n0 10 15 20\n5 0 9 10\n6 13 0 12\n8 8 9 0\n",
    "expected": "35",
    "description": "기본 케이스: 4개 도시"
  }
]
```

**필드 설명**:
- `input`: 표준 입력 (stdin)
- `expected`: 예상 출력 (정답)
- `description`: 테스트 케이스 설명

### constraints.json

제약 조건 정의 파일입니다.

```json
{
  "time_limit_sec": 1.0,
  "memory_limit_mb": 128
}
```

**필드 설명**:
- `time_limit_sec`: 시간 제한 (초)
- `memory_limit_mb`: 메모리 제한 (MB)

## 사용 예시

### 예시 1: 기본 사용 (spec_id)

```bash
uv run python test_scripts/test_judge0_submit.py \
  --code-file test_scripts/example_solution.py \
  --spec-id 10
```

**출력 예시**:
```
[1단계] 문제 정보 가져오기 - spec_id: 10
⚠️ spec_id는 하드코딩 딕셔너리(HARDCODED_PROBLEM_SPEC)의 키로만 사용됩니다.
✅ 문제: 외판원 순회

[2단계] 테스트 케이스 추출
✅ 총 10개의 테스트 케이스 발견
⚠️ 첫 번째 테스트 케이스만 사용 (API 제한)

[3단계] 제약 조건
  - 시간 제한: 1.0초
  - 메모리 제한: 128MB
  - 언어: python

[4단계] 코드 형식 확인
  - 코드 길이: 500 문자
  - 코드 바이트 (UTF-8): 512 bytes
  - 줄바꿈: \n (LF)
  ✅ 순수 코드 (마크다운 코드 블록 없음)

[5단계] Judge0 실행
  - 테스트 케이스: 1개

[6단계] Judge0 실행 결과
✅ 테스트 케이스 1: 기본 케이스: 4개 도시
  입력: 4\n0 10 15 20\n5 0 9 10\n6 13 0 12\n8 8 9 0\n
  예상 출력: 35
  실제 출력: 35
  통과 여부: ✅ 통과
  Judge0 Status: Accepted (ID: 3)
  실행 시간: 0.123초
  메모리 사용: 1024KB

[7단계] 점수 계산
📊 Correctness 점수
  점수: 100.0점
  통과: 1/1
  통과율: 100.0%

⚡ Performance 점수
  점수: 100.0점
  시간 점수: 100.0점 (실행 시간: 0.123초)
  메모리 점수: 100.0점 (메모리: 1.00MB)

최종 결과
✅ Correctness: 100.0점
⚡ Performance: 100.0점
📈 종합 점수 (Correctness 50% + Performance 25%): 75.0점
```

### 예시 2: 테스트 케이스 직접 제공

```bash
uv run python test_scripts/test_judge0_submit.py \
  --code-file test_scripts/example_solution.py \
  --test-cases test_scripts/test_cases.json \
  --constraints test_scripts/constraints.json
```

### 예시 3: 코드 직접 입력

```bash
uv run python test_scripts/test_judge0_submit.py \
  --code "print('Hello, World!')" \
  --test-cases test_scripts/test_cases.json
```

## 옵션 설명

| 옵션 | 설명 | 기본값 | 필수 |
|------|------|--------|------|
| `--code-file` | 코드 파일 경로 | - | ✅ |
| `--code` | 코드 직접 입력 | - | ✅ |
| `--spec-id` | 문제 스펙 ID | 10 | ❌ |
| `--test-cases` | 테스트 케이스 JSON 파일 | - | ❌ |
| `--constraints` | 제약 조건 JSON 파일 | - | ❌ |
| `--language` | 프로그래밍 언어 | python | ❌ |
| `--all-tc` | 모든 TC 사용 | 첫 번째만 | ❌ |

**참고**: `--code-file` 또는 `--code` 중 하나는 필수입니다.

## 문제 해결

### 1. Judge0 연결 실패

```
❌ JUDGE0_API_URL이 설정되지 않았습니다
```

**해결**: 환경 변수 확인
```bash
# .env 파일 확인
JUDGE0_API_URL=...
JUDGE0_API_KEY=...
```

### 2. 테스트 케이스 파일 읽기 실패

```
❌ 테스트 케이스 파일을 찾을 수 없습니다
```

**해결**: 파일 경로 확인
```bash
# 상대 경로 사용
--test-cases test_scripts/test_cases.json

# 절대 경로 사용
--test-cases /full/path/to/test_cases.json
```

### 3. 코드 형식 오류

```
⚠️ 마크다운 코드 블록이 포함되어 있습니다!
```

**해결**: 코드에서 마크다운 코드 블록 제거
```python
# 잘못된 형식
code = """```python
print('Hello')
```"""

# 올바른 형식
code = """print('Hello')"""
```

## 추가 정보

- 실제 Flow와 동일한 방식으로 테스트
- Spring Boot의 `codeInline` 형식 지원
- UTF-8 인코딩, `\n` 줄바꿈 사용
- 코드 정리 없이 원본 그대로 전달 (마크다운 제거는 테스트 목적)



