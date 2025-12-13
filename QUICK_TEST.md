# Judge0 테스트 빠른 실행 가이드

## 준비된 파일

- `solution.py` - 테스트할 코드 (TSP 문제 해결)
- `test_cases.json` - 테스트 케이스 정의

## 실행 명령어

### PowerShell (Windows)

#### 기본 실행 (첫 번째 TC만)

```powershell
uv run python test_scripts/test_judge0_submit.py --code-file solution.py --test-cases test_cases.json
```

#### 제약 조건 포함

```powershell
uv run python test_scripts/test_judge0_submit.py --code-file solution.py --test-cases test_cases.json --constraints test_scripts/constraints.json
```

#### 모든 테스트 케이스 사용

```powershell
uv run python test_scripts/test_judge0_submit.py --code-file solution.py --test-cases test_cases.json --all-tc
```

#### spec_id 사용 (하드코딩 딕셔너리)

```powershell
uv run python test_scripts/test_judge0_submit.py --code-file solution.py --spec-id 10
```

### Linux/Mac (Bash)

#### 기본 실행 (첫 번째 TC만)

```bash
uv run python test_scripts/test_judge0_submit.py \
  --code-file solution.py \
  --test-cases test_cases.json
```

#### 제약 조건 포함

```bash
uv run python test_scripts/test_judge0_submit.py \
  --code-file solution.py \
  --test-cases test_cases.json \
  --constraints test_scripts/constraints.json
```

#### 모든 테스트 케이스 사용

```bash
uv run python test_scripts/test_judge0_submit.py \
  --code-file solution.py \
  --test-cases test_cases.json \
  --all-tc
```

#### spec_id 사용 (하드코딩 딕셔너리)

```bash
uv run python test_scripts/test_judge0_submit.py \
  --code-file solution.py \
  --spec-id 10
```

## 예상 출력

```
================================================================================
Judge0 코드 제출 및 평가 시작
================================================================================

[1단계] 직접 제공된 테스트 케이스 사용
✅ 총 4개의 테스트 케이스 발견
⚠️ 첫 번째 테스트 케이스만 사용 (API 제한) - 기본 케이스: 4개 도시

[2단계] 테스트 케이스 추출
⚠️ 첫 번째 테스트 케이스만 사용 (API 제한) - 기본 케이스: 4개 도시

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
  - 코드 형식: 원본 그대로 (실제 Flow와 동일)

[6단계] Judge0 실행 결과
================================================================================

✅ 테스트 케이스 1: 기본 케이스: 4개 도시
  입력: 4\n0 10 15 20\n5 0 9 10\n6 13 0 12\n8 8 9 0\n
  예상 출력: 35
  실제 출력: 35
  통과 여부: ✅ 통과
  Judge0 Status: Accepted (ID: 3)
  실행 시간: 0.123초
  메모리 사용: 1024KB

[7단계] 점수 계산
================================================================================

📊 Correctness 점수
  점수: 100.0점
  통과: 1/1
  통과율: 100.0%

⚡ Performance 점수
  점수: 100.0점
  시간 점수: 100.0점 (실행 시간: 0.123초)
  메모리 점수: 100.0점 (메모리: 1.00MB)

================================================================================
최종 결과
================================================================================
✅ Correctness: 100.0점
⚡ Performance: 100.0점
📈 종합 점수 (Correctness 50% + Performance 25%): 75.0점

✅ 평가 완료!
```

## 문제 해결

### Judge0 연결 실패
환경 변수 확인:
```bash
# .env 파일에 설정되어 있어야 함
JUDGE0_API_URL=...
JUDGE0_API_KEY=...
```

### 파일을 찾을 수 없음
현재 디렉토리에서 실행:
```bash
# 프로젝트 루트에서 실행
cd C:\P_project\LangGraph_1
uv run python test_scripts/test_judge0_submit.py --code-file solution.py --test-cases test_cases.json
```

