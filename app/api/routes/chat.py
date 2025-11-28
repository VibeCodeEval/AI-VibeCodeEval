"""
채팅 API 라우터

[목적]
- 사용자와 AI 어시스턴트 간의 대화 처리
- 코드 제출 및 최종 평가 실행

[주요 엔드포인트]
1. POST /api/chat/message
   - 일반 채팅 메시지 전송
   - AI 응답 생성 및 턴별 평가 (백그라운드)
   
2. POST /api/chat/submit
   - 최종 코드 제출
   - 전체 평가 실행 (Holistic Flow, 성능, 정확성)
   - 최종 점수 산출

[처리 흐름]
1. 요청 수신 → 2. EvalService 호출 → 3. LangGraph 실행 → 4. 응답 반환

[에러 처리]
- Timeout: 60초 초과 시 타임아웃 응답
- Exception: 모든 예외 캡처 및 에러 응답 반환
"""
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.chat import ChatRequest, ChatResponse, SubmitRequest, SubmitResponse
from app.schemas.common import ErrorResponse
from app.services.eval_service import EvalService
from app.db.redis_client import redis_client, get_redis


router = APIRouter(prefix="/chat", tags=["Chat"])


async def get_eval_service() -> EvalService:
    """
    EvalService 의존성 주입
    
    [역할]
    - FastAPI의 Depends 메커니즘을 사용한 의존성 주입
    - 각 API 요청마다 EvalService 인스턴스 생성
    - Redis 클라이언트를 EvalService에 전달
    
    [반환값]
    EvalService: 평가 서비스 인스턴스
    """
    return EvalService(redis_client)


@router.post(
    "/message",
    response_model=ChatResponse,
    responses={
        500: {"model": ErrorResponse, "description": "서버 에러"}
    },
    summary="메시지 전송",
    description="""
    AI 어시스턴트에게 메시지를 전송하고 응답을 받습니다.
    
    **처리 과정:**
    1. Intent Analyzer: 의도 분석 및 가드레일 체크
    2. Writer LLM: AI 답변 생성 (Socratic 방식)
    3. Eval Turn SubGraph: 턴별 평가 (백그라운드)
    4. Redis 상태 저장
    
    **제한사항:**
    - Timeout: 60초
    - 가드레일 위반 시: 교육적 피드백 반환
    """
)
async def send_message(
    request: ChatRequest,
    eval_service: EvalService = Depends(get_eval_service)
) -> ChatResponse:
    """
    메시지 전송 및 AI 응답 받기
    
    [처리 흐름]
    1. 요청 검증 (session_id, exam_id, etc.)
    2. EvalService.process_message() 호출
       - LangGraph 메인 플로우 실행
       - Redis에서 기존 상태 로드
       - Intent Analyzer → Writer LLM → 응답 반환
       - Eval Turn SubGraph는 백그라운드로 비동기 실행
    3. 결과를 ChatResponse로 변환
    
    [에러 처리]
    - Timeout (60초): 타임아웃 응답 반환
    - LangGraph 실행 실패: 에러 메시지 포함한 응답 반환
    - 가드레일 위반: is_guardrail_failed=True, 교육적 피드백 반환
    
    [반환값]
    ChatResponse: AI 응답, 턴 번호, 에러 정보 등
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"메시지 수신 - session_id: {request.session_id}, message: {request.message[:50]}...")
        
        # 1분 타임아웃 설정 (LLM 응답 시간 고려)
        result = await asyncio.wait_for(
            eval_service.process_message(
                session_id=request.session_id,
                exam_id=request.exam_id,
                participant_id=request.participant_id,
                spec_id=request.spec_id,
                human_message=request.message,
            ),
            timeout=60.0  # 1분
        )
        
        logger.info(f"처리 완료 - session_id: {request.session_id}, has_ai_message: {bool(result.get('ai_message'))}, error: {result.get('error')}")
        
        # 에러 발생 시
        if result.get("error"):
            return ChatResponse(
                session_id=request.session_id,
                turn=result.get("turn", 0),
                ai_message=None,
                is_submitted=False,
                error=True,
                error_message=result.get("error_message"),
            )
        
        # 정상 응답
        return ChatResponse(
            session_id=result.get("session_id", request.session_id),
            turn=result.get("turn", 0),
            ai_message=result.get("ai_message"),
            is_submitted=result.get("is_submitted", False),
            error=False,
            error_message=None,
        )
    except asyncio.TimeoutError:
        # LLM 응답이 60초 이내에 완료되지 않은 경우
        # 원인: LLM API 지연, 네트워크 문제, Rate Limit 초과 등
        logger.error(f"메시지 처리 타임아웃 - session_id: {request.session_id}")
        return ChatResponse(
            session_id=request.session_id,
            turn=0,
            ai_message=None,
            is_submitted=False,
            error=True,
            error_message="요청 처리 시간이 초과되었습니다. (1분 타임아웃)",
        )
    except Exception as e:
        # 예상치 못한 모든 예외 처리
        # 예: Redis 연결 실패, LLM API 에러, 상태 직렬화 오류 등
        logger.error(f"메시지 처리 중 예외 발생: {str(e)}", exc_info=True)
        return ChatResponse(
            session_id=request.session_id,
            turn=0,
            ai_message=None,
            is_submitted=False,
            error=True,
            error_message=f"서버 오류: {str(e)}",
        )


@router.post(
    "/submit",
    response_model=SubmitResponse,
    responses={
        500: {"model": ErrorResponse, "description": "서버 에러"}
    },
    summary="코드 제출",
    description="""
    최종 코드를 제출하고 평가 결과를 받습니다.
    
    **처리 과정:**
    1. Intent Analyzer: 제출 의도 감지 (PASSED_SUBMIT)
    2. Eval Turn Guard: 모든 턴 평가 완료 대기 & 누락 턴 재평가
    3. Main Router: 제출 확인 및 평가 플로우 진입
    4. 평가 노드 실행:
       - 6a. Holistic Flow Evaluation (Chaining 전략)
       - 6b. Aggregate Turn Scores (턴별 점수 집계)
       - 6c. Code Performance (성능 평가)
       - 6d. Code Correctness (정확성 평가)
    5. Final Score Aggregation (최종 점수 산출)
    
    **제한사항:**
    - Timeout: 60초 (평가 시간 고려)
    - 제출은 세션당 1회만 가능
    """
)
async def submit_code(
    request: SubmitRequest,
    eval_service: EvalService = Depends(get_eval_service)
) -> SubmitResponse:
    """
    코드 제출 및 평가
    
    [처리 흐름]
    1. 요청 검증 (session_id, code, lang)
    2. EvalService.submit_code() 호출
       - is_submission=True로 설정
       - human_message="코드를 제출합니다."
    3. LangGraph 메인 플로우 실행
       - Intent Analyzer: PASSED_SUBMIT 반환
       - Eval Turn Guard: 모든 턴 평가 완료 확인
         * 누락된 턴이 있으면 동기적으로 재평가
       - Main Router: eval_holistic_flow로 분기
       - 평가 노드들 순차 실행 (6a → 6b → 6c → 6d → 7)
    4. 최종 점수를 SubmitResponse로 변환
    
    [최종 점수 구성]
    - prompt_score (25%): 턴별 평균 + Holistic Flow
    - performance_score (25%): 시간/공간 복잡도
    - correctness_score (50%): 테스트 케이스 통과율
    - total_score: 가중 평균
    - grade: A/B/C/D/F
    
    [반환값]
    SubmitResponse: 최종 점수, 턴별 점수, 제출 ID, 에러 정보 등
    """
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"코드 제출 수신 - session_id: {request.session_id}")
        
        # 1분 타임아웃 설정 (평가 시간 고려)
        # 평가 노드들이 순차적으로 실행되므로 충분한 시간 필요
        result = await asyncio.wait_for(
            eval_service.submit_code(
                session_id=request.session_id,
                exam_id=request.exam_id,
                participant_id=request.participant_id,
                spec_id=request.spec_id,
                code_content=request.code,
                lang=request.lang,
            ),
            timeout=120.0  # 2분
        )
        
        # 에러 발생 시
        if result.get("error"):
            return SubmitResponse(
                session_id=request.session_id,
                submission_id=None,
                is_submitted=False,
                final_scores=None,
                turn_scores=None,
                error=True,
                error_message=result.get("error_message"),
            )
        
        final_scores = result.get("final_scores")
        
        # 정상 응답
        return SubmitResponse(
            session_id=result.get("session_id", request.session_id),
            submission_id=result.get("submission_id"),
            is_submitted=True,
            final_scores=final_scores,
            turn_scores=result.get("turn_scores"),
            error=False,
            error_message=None,
        )
    except asyncio.TimeoutError:
        # 평가 프로세스가 60초 이내에 완료되지 않은 경우
        # 원인: 
        # - Eval Turn Guard의 백그라운드 평가 대기 시간 초과
        # - LLM API 지연 (Holistic Flow, Performance, Correctness 평가)
        # - Redis 작업 지연
        logger.error(f"코드 제출 타임아웃 - session_id: {request.session_id}")
        return SubmitResponse(
            session_id=request.session_id,
            submission_id=None,
            is_submitted=False,
            final_scores=None,
            turn_scores=None,
            error=True,
            error_message="요청 처리 시간이 초과되었습니다. (1분 타임아웃)",
        )
    except Exception as e:
        # 예상치 못한 모든 예외 처리
        # 예: 
        # - turn_scores 누락 (Eval Turn Guard 실패)
        # - LLM API 에러 (429 Rate Limit, 500 Server Error 등)
        # - Redis 연결 실패
        # - 상태 직렬화 오류
        logger.error(f"코드 제출 중 예외 발생: {str(e)}", exc_info=True)
        return SubmitResponse(
            session_id=request.session_id,
            submission_id=None,
            is_submitted=False,
            final_scores=None,
            turn_scores=None,
            error=True,
            error_message=f"서버 오류: {str(e)}",
        )


