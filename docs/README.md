# 📚 문서 폴더

이 폴더는 프로젝트 관련 문서와 예제 파일을 포함합니다.

## 📄 문서 목록

### 1. `Test_Guide.txt`
**테스트 및 디버깅 가이드**

- 서버 로그 확인 방법
- Docker 컨테이너 로그 확인 방법
- Redis 세션 데이터 확인 방법
- PostgreSQL 데이터 확인 방법
- 일반적인 문제 해결 방법

**사용 시점**: 테스트 중 문제 발생 시 참고

---

### 2. `Change_11_27_graph.txt`
**그래프 구조 변경 이력 (2025-11-27)**

- LangGraph 구조 및 진행 방식
- 각 노드의 역할 및 출력 형식
- 변경 사항 및 새로 추가된 파일
- 테스트 방법 및 오류 기록
- ERD 구조

**사용 시점**: 11월 27일 변경 사항 히스토리 확인 시

---

### 3. `Timing_Issue_Analysis.md`
**타이밍 오류 분석 문서**

- Turn 누락 문제 분석
- 백그라운드 평가 동기화 이슈
- Gemini API Rate Limit (429 에러) 분석
- 해결 방안 및 개선 사항

**사용 시점**: 타이밍 관련 문제 디버깅 시 참고

---

### 4. `main_example.py`
**LangGraph 학습용 예제 코드**

- 감정/논리 분류 챗봇 예제
- Classifier → Router → Agent 패턴
- LangGraph 기본 구조 학습용

**내용**:
```python
# 사용자 메시지를 "emotional" 또는 "logical"로 분류
# → therapist_agent 또는 logical_agent로 라우팅
# → 적절한 답변 생성
```

**사용 시점**: LangGraph 처음 배울 때 참고용

---

## 🗂️ 문서 활용 가이드

### 신규 팀원 온보딩
1. `../README.md` (메인 문서) 먼저 읽기
2. `main_example.py` (예제 코드) 실행해보기
3. `Test_Guide.txt` (테스트 방법) 숙지

### 문제 해결
1. `Test_Guide.txt` (로그 확인 방법) 참고
2. `Timing_Issue_Analysis.md` (타이밍 이슈) 확인
3. `Change_11_27_graph.txt` (변경 이력) 검토

### 히스토리 추적
1. `Change_11_27_graph.txt` (그래프 변경 이력)
2. `Timing_Issue_Analysis.md` (해결된 문제)

---

## 📝 문서 작성 규칙

새 문서를 추가할 때:
- 파일명은 명확하게 (예: `API_Integration_Guide.md`)
- 작성일 및 작성자 명시
- 이 README.md에 문서 설명 추가

---

**최종 업데이트**: 2025-11-28

