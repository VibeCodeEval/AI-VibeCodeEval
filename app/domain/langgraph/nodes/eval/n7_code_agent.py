"""
N7: 코드 리뷰 에이전트 (단일 LLM 호출)
제출된 코드와 객관적 지표(Judge0, Radon CC)를 바탕으로 정성(Qualitative) 리뷰를 생성합니다.
"""

import logging
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.domain.langgraph.nodes.eval_turn.utils import get_llm
from app.domain.langgraph.states import MainGraphState

logger = logging.getLogger(__name__)

class CodeEvalReport(BaseModel):
    """코드 심층 분석 결과 모델"""
    efficiency_review: str = Field(..., description="코드 효율성(속도, 메모리, 알고리즘)에 대한 구체적 수치 연계 리뷰")
    readability_review: str = Field(..., description="코드 가독성(기명, 모듈화, CC)에 대한 리뷰")
    error_handling_review: str = Field(..., description="엣지 케이스 및 예외 처리 견고성에 대한 리뷰")
    overall_summary: str = Field(..., description="코드 리뷰 종합 요약")
    score_adjustment_note: str = Field(..., description="구체적 개선 방식 및 학점 산정 시 고려해야 할 정성적 패널티 또는 가산점 의견지")


SYSTEM_PROMPT = """당신은 최고 수준의 시니어 소프트웨어 엔지니어이자 코드 리뷰 에이전트입니다. 
제출된 코드 원문과 함께 동적 실행 결과(Judge0), 정적 분석 결과(Radon CC)를 제공받아 
코드의 품질을 정성적으로 심층 분석하고, 실무 수준의 개선 방향을 도출하는 것이 당신의 역할입니다.

[분석 및 리뷰 지침]
1. 효율성 (Efficiency): 
   - Judge0의 실행 시간 및 메모리 사용량 데이터를 바탕으로 평가합니다. 
   - 알고리즘과 자료구조 선택이 문제의 제약조건 하에서 최적인지 분석하십시오.
2. 가독성 및 유지보수성 (Readability & Maintainability): 
   - 코드 원문과 Radon CC(순환 복잡도) 지표를 바탕으로 평가합니다. 
   - 변수명, 함수 분리, 불필요한 제어문의 중첩 등 구조적 깔끔함을 리뷰하십시오.
3. 예외 처리 및 안정성 (Error Handling & Robustness): 
   - 문제 요구사항(Problem Context)을 기반으로, 엣지 케이스나 예외 상황을 코드가 적절히 방어하고 있는지 분석하십시오.
4. 객관적 지표와 정성적 평가의 융합:
   - "순환 복잡도가 12로 높아 유지보수가 어렵다" 혹은 "메모리를 15MB 사용하였으나, 캐싱을 도입하면 더 줄일 수 있다"와 같이 수치를 구체적으로 언급하며 리뷰하십시오.
5. 구체적 개선 및 리팩토링 제안 (Actionable Improvements) [중요]:
   - 위 분석에서 발견된 단점(비효율성, 가독성 저하, 예외 누락 등)을 해결할 수 있는 명확하고 실천 가능한 코드 개선 방향을 제시하십시오.
   - 추상적인 조언을 피하고, 특정 로직을 어떻게 변경해야 하는지(예: 특정 자료구조 도입, 조기 종료(Early Return) 적용, 헬퍼 함수 분리 등) 구체적인 방법론을 서술하십시오.

당신의 리뷰는 후속 N8(다중 에이전트 토론) 과정에서 최종 Grade를 결정하기 위한 핵심 증거 자료로 활용됩니다.
반드시 지정된 JSON 구조로 답변을 반환하십시오."""

async def eval_code_agent(state: MainGraphState) -> Dict[str, Any]:
    session_id = state.get("session_id", "unknown")
    logger.info(f"[N7. Eval Code Agent] 코드 리뷰 생성 시작 - session_id: {session_id}")
    
    code_content = state.get("code_content", "")
    code_correctness_score = state.get("code_correctness_score")
    code_performance_score = state.get("code_performance_score")
    execution_time = state.get("execution_time")
    memory_used_mb = state.get("memory_used_mb")
    
    code_quality_metrics = state.get("code_quality_metrics", {})
    problem_context = state.get("problem_context", {})
    
    if not code_content:
        logger.warning(f"[N7] 코드 내용이 없습니다. 평가 스킵.")
        return {"code_eval_report": None}
        
    human_msg_content = f"""
== 문제 설명 ==
{problem_context.get('basic_info', {}).get('description', '설명 없음')}

== 제출 코드 ==
```python
{code_content}
```

== Judge0 실행 지표 ==
- Correctness Score: {code_correctness_score}
- Performance Score: {code_performance_score}
- Execution Time: {execution_time}초
- Memory Used: {memory_used_mb}MB

== Radon CC 정적 지표 ==
- Average CC: {code_quality_metrics.get('radon_cc', {}).get('avg_cc', 'N/A')}
- Max CC: {code_quality_metrics.get('radon_cc', {}).get('max_cc', 'N/A')}
- Delta CC (%): {code_quality_metrics.get('delta_cc', {}).get('delta_cc_pct', 'N/A')}
- Junior Grade Flag: {code_quality_metrics.get('junior_grade', False)}
"""
    
    try:
        llm = get_llm()
        structured_llm = llm.with_structured_output(CodeEvalReport)
        
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=human_msg_content)
        ]
        
        result = await structured_llm.ainvoke(messages)
        report_dict = result.dict()
        
        logger.info(f"[N7. Eval Code Agent] 리뷰 완성")
        return {"code_eval_report": report_dict}
        
    except Exception as e:
        logger.error(f"[N7. Eval Code Agent] 코드 리뷰 생성 실패: {e}", exc_info=True)
        return {"code_eval_report": None}
