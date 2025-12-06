# GCP Vertex AI 설정 가이드

LangGraph에서 GCP Vertex AI를 사용하기 위한 설정 가이드입니다.

## 1. 사전 준비

### 1.1 GCP 프로젝트 설정
1. [Google Cloud Console](https://console.cloud.google.com/)에 접속
2. 프로젝트 생성 또는 기존 프로젝트 선택
3. Vertex AI API 활성화

### 1.2 서비스 계정 생성
1. IAM & Admin > Service Accounts 메뉴로 이동
2. "Create Service Account" 클릭
3. 서비스 계정 이름 입력 (예: `langgraph-vertex-ai`)
4. 역할 부여:
   - `Vertex AI User` (필수)
   - `Service Account User` (필수)
5. "Create Key" 클릭 > JSON 형식 선택
6. 다운로드된 JSON 파일 저장

## 2. 환경 변수 설정

### 2.1 `.env` 파일 설정

```bash
# Vertex AI 사용 활성화
USE_VERTEX_AI=true

# GCP 프로젝트 ID
GOOGLE_PROJECT_ID=your-gcp-project-id

# 서비스 계정 JSON (전체 내용을 한 줄로)
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...@....iam.gserviceaccount.com","client_id":"...","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"..."}

# Vertex AI 리전 (선택사항, 기본값: us-central1)
GOOGLE_LOCATION=us-central1

# 모델 설정
DEFAULT_LLM_MODEL=gemini-1.5-pro
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=4096
```

### 2.2 JSON 문자열 변환 방법

서비스 계정 JSON 파일을 환경 변수로 설정하려면:

**PowerShell:**
```powershell
$json = Get-Content path/to/service-account.json -Raw
$json = $json -replace "`n", "\n" -replace "`r", ""
$env:GOOGLE_SERVICE_ACCOUNT_JSON = $json
```

**Bash:**
```bash
export GOOGLE_SERVICE_ACCOUNT_JSON=$(cat path/to/service-account.json | jq -c .)
```

또는 `.env` 파일에 직접 작성:
```bash
# JSON 파일 내용을 한 줄로 변환 (개행 문자는 \n으로)
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
```

## 3. 코드 동작 방식

### 3.1 LLM Factory 패턴

모든 노드에서 `llm_factory.get_llm()`을 사용하여 LLM 인스턴스를 생성합니다:

```python
from app.domain.langgraph.utils.llm_factory import get_llm

# 노드별 LLM 생성
llm = get_llm("intent_analyzer")  # Intent Analyzer용
llm = get_llm("writer")           # Writer용
llm = get_llm("turn_evaluator")   # Turn Evaluator용
```

### 3.2 자동 전환

`USE_VERTEX_AI=true`로 설정하면:
- 모든 `ChatGoogleGenerativeAI` 호출이 `ChatVertexAI`로 자동 전환됩니다
- ADC 인증을 사용하여 인증 정보를 자동으로 처리합니다
- 파일 시스템 없이도 작동합니다 (Vercel 등 서버리스 환경 지원)

### 3.3 하위 호환성

`USE_VERTEX_AI=false` (기본값)로 설정하면:
- 기존 `ChatGoogleGenerativeAI` 방식으로 동작합니다
- `GEMINI_API_KEY`를 사용합니다

## 4. 지원 모델

### Vertex AI 모델
- `gemini-1.5-pro`
- `gemini-1.5-flash`
- `gemini-1.0-pro`

### Gemini API 모델 (USE_VERTEX_AI=false)
- `gemini-2.5-flash`
- `gemini-1.5-pro`
- 기타 Gemini API 모델

## 5. 문제 해결

### 5.1 인증 오류
```
ValueError: GOOGLE_SERVICE_ACCOUNT_JSON 환경 변수가 설정되지 않았습니다.
```
**해결:** `.env` 파일에 `GOOGLE_SERVICE_ACCOUNT_JSON` 설정 확인

### 5.2 프로젝트 ID 오류
```
ValueError: USE_VERTEX_AI=True인데 GOOGLE_PROJECT_ID가 설정되지 않았습니다.
```
**해결:** `.env` 파일에 `GOOGLE_PROJECT_ID` 설정 확인

### 5.3 JSON 파싱 오류
```
ValueError: GOOGLE_SERVICE_ACCOUNT_JSON 파싱 실패
```
**해결:** JSON 문자열이 올바른 형식인지 확인 (특수 문자 이스케이프 확인)

## 6. 테스트

환경 변수 설정 후 서버를 재시작하고 테스트:

```bash
uv run python test_scripts/test_chat_message_simple.py
```

로그에서 다음 메시지를 확인:
```
[LLM Factory] 새 LLM 인스턴스 생성 - node: intent_analyzer, type: gemini, key: ...
```

## 인증 정보 설정 방법

### 방법 1: JSON 파일 경로 사용 (로컬 개발 환경 권장) ✅

가장 간단한 방법입니다. JSON 파일을 그대로 사용합니다.

#### 설정

`.env` 파일:
```bash
USE_VERTEX_AI=true
GOOGLE_PROJECT_ID=your-gcp-project-id
GOOGLE_SERVICE_ACCOUNT_PATH=./credentials/service-account.json
GOOGLE_LOCATION=us-central1
```

#### 장점
- ✅ JSON 파일을 그대로 사용 (수정 불필요)
- ✅ 여러 줄, 들여쓰기 그대로 유지
- ✅ 설정이 간단함

#### 주의사항
- 파일 경로가 프로젝트 루트 기준 상대 경로 또는 절대 경로
- `.gitignore`에 `credentials/` 폴더 추가 권장

---

### 방법 2: JSON 문자열 사용 (서버리스 환경 권장) ✅

Vercel, AWS Lambda 등 파일 시스템이 제한적인 환경에서 사용합니다.

#### 설정 방법 A: PowerShell (Windows)

```powershell
# JSON 파일을 읽어서 한 줄로 변환
$json = Get-Content .\credentials\service-account.json -Raw
$json = $json -replace "`r`n", " " -replace "`n", " " -replace "`r", " "
$json = $json -replace '\s+', ' '  # 여러 공백을 하나로

# .env 파일에 추가
Add-Content .env "GOOGLE_SERVICE_ACCOUNT_JSON=$json"
```

또는 수동으로:
1. JSON 파일을 텍스트 에디터로 열기
2. 모든 내용 선택 (Ctrl+A)
3. 한 줄로 만들기 (엔터 제거)
4. `.env` 파일에 붙여넣기

#### 설정 방법 B: Python 스크립트 사용

```python
import json

# JSON 파일 읽기
with open('credentials/service-account.json', 'r') as f:
    data = json.load(f)

# 한 줄 JSON 문자열로 변환
json_str = json.dumps(data, separators=(',', ':'))

# .env 파일에 추가
with open('.env', 'a') as f:
    f.write(f'\nGOOGLE_SERVICE_ACCOUNT_JSON={json_str}\n')
```

#### 설정 방법 C: jq 사용 (Linux/Mac)

```bash
# JSON 파일을 한 줄로 변환
export GOOGLE_SERVICE_ACCOUNT_JSON=$(cat credentials/service-account.json | jq -c .)

# .env 파일에 추가
echo "GOOGLE_SERVICE_ACCOUNT_JSON=$GOOGLE_SERVICE_ACCOUNT_JSON" >> .env
```

#### .env 파일 예시

```bash
USE_VERTEX_AI=true
GOOGLE_PROJECT_ID=my-project-12345
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"my-project-12345","private_key_id":"abc123","private_key":"-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC...\n-----END PRIVATE KEY-----\n","client_email":"langgraph@my-project-12345.iam.gserviceaccount.com","client_id":"123456789","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_x509_cert_url":"https://www.googleapis.com/robot/v1/metadata/x509/langgraph%40my-project-12345.iam.gserviceaccount.com"}
GOOGLE_LOCATION=us-central1
```

#### 장점
- ✅ 파일 시스템 없이 작동 (서버리스 환경)
- ✅ 환경 변수로 관리 가능

#### 주의사항
- JSON 문자열에 따옴표(`"`)가 포함되어 있으므로 `.env` 파일에서 이스케이프 처리 필요
- Windows PowerShell에서는 따옴표 처리 주의

---

### 추천 설정

#### 로컬 개발 환경
```bash
USE_VERTEX_AI=true
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_SERVICE_ACCOUNT_PATH=./credentials/service-account.json
```

#### 프로덕션/서버리스 환경
```bash
USE_VERTEX_AI=true
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}  # 한 줄 JSON
```

---

## Vertex AI vs Gemini API 차이

### 현재 구조 (Gemini API)

```python
# 현재 사용 중
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.GEMINI_API_KEY,  # API Key 사용
    temperature=0.7,
)
```

**특징:**
- ✅ Consumer API (무료 티어 제공)
- ✅ API Key로 간단한 인증
- ⚠️ Rate Limit: 15 RPM (무료 티어)
- ⚠️ 프로덕션 환경에 제한적

### Vertex AI 구조

```python
# Vertex AI로 전환
from langchain_google_vertexai import ChatVertexAI

llm = ChatVertexAI(
    model_name="gemini-2.0-flash-exp",
    project="your-gcp-project-id",
    location="us-central1",
    credentials=credentials,  # Service Account 또는 ADC
    temperature=0.7,
)
```

**특징:**
- ✅ Enterprise급 서비스
- ✅ 높은 Rate Limit (프로젝트별 설정)
- ✅ GCP 통합 (로깅, 모니터링, 비용 관리)
- ⚠️ GCP 프로젝트 필요
- ⚠️ 인증 설정 복잡도 증가

### 비교표

| 항목 | Gemini API | Vertex AI |
|------|-----------|-----------|
| **인증** | API Key | Service Account / ADC |
| **Rate Limit** | 15 RPM (무료) | 프로젝트별 설정 |
| **비용** | 무료 티어 있음 | 사용량 기반 |
| **GCP 통합** | ❌ | ✅ |
| **로깅/모니터링** | 제한적 | 완전 지원 |
| **프로덕션 적합성** | ⚠️ 제한적 | ✅ 권장 |
| **설정 복잡도** | 낮음 | 중간 |

---

## 마이그레이션 체크리스트

### ✅ 준비 단계

- [ ] GCP 프로젝트 생성 및 Vertex AI API 활성화
- [ ] Service Account 생성 및 키 파일 다운로드
- [ ] `langchain-google-vertexai` 패키지 설치
- [ ] 환경 변수 설정 (.env 파일)

### ✅ 코드 변경

- [ ] `app/core/config.py`에 Vertex AI 설정 추가
- [ ] `app/domain/langgraph/utils/llm_factory.py`에서 Vertex AI 지원 확인
- [ ] 모든 노드에서 `llm_factory.get_llm()` 사용 확인

### ✅ 테스트

- [ ] 단일 노드 테스트 (Intent Analyzer)
- [ ] Writer LLM 테스트
- [ ] 평가 노드 테스트
- [ ] 전체 플로우 통합 테스트

### ✅ 배포

- [ ] 프로덕션 환경에 Service Account 키 파일 배포 (보안 주의!)
- [ ] 환경 변수 설정 확인
- [ ] Rate Limit 모니터링
- [ ] 비용 모니터링 (GCP Console)

---

## 주의사항

### 🔴 API Key로 Vertex AI 사용 불가

**중요:** Vertex AI는 **API Key 방식으로 직접 인증할 수 없습니다**. 

**대안:**
1. **Service Account 사용 (권장)**
2. **ADC 사용 (로컬 개발)**
3. **Gemini API 유지** (API Key 사용 가능)

### 🔐 보안 주의사항

- Service Account 키 파일은 **절대 Git에 커밋하지 마세요**
- `.gitignore`에 키 파일 경로 추가
- 프로덕션 환경에서는 환경 변수 또는 Secret Manager 사용

### 💰 비용 관리

- Vertex AI는 사용량 기반 과금
- GCP Console에서 비용 알림 설정 권장
- 무료 할당량 확인 (프로젝트별로 다름)

---

## 권장사항

### 개발 환경:
- ADC 사용 (`gcloud auth application-default login`)
- 간편한 설정, 키 파일 관리 불필요

### 프로덕션 환경:
- Service Account 사용
- Secret Manager 또는 환경 변수로 키 관리
- GCP 통합 기능 활용 (로깅, 모니터링)

### 하이브리드 접근:
- 개발: Gemini API (API Key)
- 프로덕션: Vertex AI (Service Account)
- `USE_VERTEX_AI` 환경 변수로 전환

---

## 참고 자료

- [LangChain Vertex AI 문서](https://python.langchain.com/docs/integrations/chat/vertex_ai)
- [GCP Vertex AI 문서](https://cloud.google.com/vertex-ai/docs)
- [서비스 계정 인증 가이드](https://cloud.google.com/docs/authentication/application-default-credentials)

