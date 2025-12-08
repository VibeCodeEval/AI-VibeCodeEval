"""
Node 4 의도 분석 및 평가 결과 확인 스크립트

사용법:
    # 대화형 모드
    python test_scripts/test_node4_intent_only.py
    
    # 명령줄 인자 모드
    python test_scripts/test_node4_intent_only.py "사용자 메시지" "AI 응답" [spec_id] [--save-db]

옵션:
    --save-db: 평가 결과를 DB에 저장 (선택적, 기본값: False)

터미널에서 사용자 메시지와 AI 메시지를 입력받아 의도 분석 및 평가 결과를 출력합니다.
프롬프트 조정을 위한 빠른 테스트용입니다.
"""
import asyncio
import sys
import os
from typing import Dict, Any

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.domain.langgraph.nodes.turn_evaluator.analysis import intent_analysis
from app.domain.langgraph.nodes.turn_evaluator.routers import intent_router
from app.domain.langgraph.nodes.turn_evaluator.evaluators import (
    eval_system_prompt,
    eval_rule_setting,
    eval_generation,
    eval_optimization,
    eval_debugging,
    eval_test_case,
    eval_hint_query,
    eval_follow_up
)
from app.domain.langgraph.nodes.turn_evaluator.aggregation import aggregate_turn_log
from app.domain.langgraph.states import EvalTurnState
from app.domain.langgraph.utils.problem_info import get_problem_info_sync


async def test_intent_analysis_and_evaluation(
    user_message: str = None, 
    ai_message: str = None, 
    spec_id: int = 2098,
    save_to_db: bool = False
):
    """의도 분석 및 평가 결과 출력"""
    
    print("=" * 80)
    print("Node 4 의도 분석 및 평가 테스트")
    print("=" * 80)
    print()
    
    # 명령줄 인자로 메시지가 제공된 경우
    if user_message and ai_message:
        pass  # 이미 제공됨
    else:
        # 사용자 메시지 입력
        print("사용자 메시지를 입력하세요 (Enter로 완료):")
        user_message = input("> ").strip()
        
        if not user_message:
            print("❌ 사용자 메시지가 비어있습니다.")
            return
        
        # AI 메시지 입력
        print("\nAI 응답을 입력하세요 (Enter로 완료, 여러 줄 입력 가능, 빈 줄 두 번으로 종료):")
        ai_lines = []
        while True:
            line = input()
            if line == "" and ai_lines and ai_lines[-1] == "":
                break
            ai_lines.append(line)
        
        ai_message = "\n".join(ai_lines[:-1]).strip()  # 마지막 빈 줄 제거
        
        if not ai_message:
            print("❌ AI 메시지가 비어있습니다.")
            return
        
        # 문제 정보 (선택적)
        print("\n문제 spec_id를 입력하세요 (엔터로 건너뛰기, 기본값: 2098):")
        spec_id_input = input("> ").strip()
        spec_id = int(spec_id_input) if spec_id_input else 2098
        
        # DB 저장 옵션 (대화형 모드)
        if not save_to_db:
            print("\nDB에 저장하시겠습니까? (y/n, 기본값: n):")
            save_input = input("> ").strip().lower()
            save_to_db = save_input == "y" or save_input == "yes"
    
    # 문제 정보 가져오기
    problem_context = get_problem_info_sync(spec_id)
    
    # EvalTurnState 구성
    state: EvalTurnState = {
        "session_id": "test_session",
        "turn": 1,
        "human_message": user_message,
        "ai_message": ai_message,
        "problem_context": problem_context,
        "is_guardrail_failed": False,
        "guardrail_message": None,
        "intent_types": None,
        "intent_confidence": 0.0,
        "system_prompt_eval": None,
        "rule_setting_eval": None,
        "generation_eval": None,
        "optimization_eval": None,
        "debugging_eval": None,
        "test_case_eval": None,
        "hint_query_eval": None,
        "follow_up_eval": None,
        "llm_answer_summary": None,
        "eval_tokens": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
    }
    
    print("\n" + "=" * 80)
    print("입력 내용:")
    print("=" * 80)
    print(f"\n[사용자 메시지]")
    print(f"{user_message}")
    print(f"\n[AI 응답]")
    print(f"{ai_message[:300]}{'...' if len(ai_message) > 300 else ''}")
    print(f"\n[문제 정보]")
    problem_title = problem_context.get("basic_info", {}).get("title", "알 수 없음")
    print(f"  문제: {problem_title} (spec_id: {spec_id})")
    print("=" * 80)
    
    # 1. 의도 분석 실행
    print("\n[1단계] 의도 분석 실행 중...")
    print("-" * 80)
    
    try:
        intent_result = await intent_analysis(state)
        
        # 의도 분석 결과를 state에 반영
        state["intent_types"] = intent_result.get("intent_types", [])
        state["intent_confidence"] = intent_result.get("intent_confidence", 0.0)
        
        print(f"\n✅ 감지된 의도: {state['intent_types']}")
        print(f"✅ 신뢰도: {state['intent_confidence']:.2f}")
        
        # 2. 의도 라우팅
        print("\n[2단계] 의도 라우팅 중...")
        print("-" * 80)
        
        eval_node_names = intent_router(state)
        print(f"✅ 실행할 평가 노드: {eval_node_names}")
        
        # 3. 평가 함수 실행
        print("\n[3단계] 평가 실행 중...")
        print("-" * 80)
        
        eval_func_map = {
            "eval_system_prompt": eval_system_prompt,
            "eval_rule_setting": eval_rule_setting,
            "eval_generation": eval_generation,
            "eval_optimization": eval_optimization,
            "eval_debugging": eval_debugging,
            "eval_test_case": eval_test_case,
            "eval_hint_query": eval_hint_query,
            "eval_follow_up": eval_follow_up,
        }
        
        for node_name in eval_node_names:
            eval_func = eval_func_map.get(node_name)
            if eval_func:
                print(f"\n  [{node_name}] 실행 중...")
                eval_result = await eval_func(state)
                # state 업데이트
                state.update(eval_result)
                print(f"  ✅ {node_name} 완료")
            else:
                print(f"  ⚠️ {node_name} 함수를 찾을 수 없습니다.")
        
        # 4. 턴 로그 집계
        print("\n[4단계] 턴 로그 집계 중...")
        print("-" * 80)
        
        aggregate_result = await aggregate_turn_log(state)
        turn_log = aggregate_result.get("turn_log", {})
        turn_score = aggregate_result.get("turn_score", 0)
        
        print(f"✅ 턴 점수: {turn_score:.2f}/100")
        
        # 5. 결과 출력
        print("\n" + "=" * 80)
        print("최종 평가 결과:")
        print("=" * 80)
        
        print(f"\n[의도 분석]")
        print(f"  - 의도: {turn_log.get('intent_types', [])}")
        print(f"  - 신뢰도: {turn_log.get('intent_confidence', 0.0):.2f}")
        
        print(f"\n[평가 점수]")
        print(f"  - 턴 점수: {turn_score:.2f}/100")
        
        # 개별 평가 결과 출력
        evaluations = turn_log.get("evaluations", {})
        if evaluations:
            print(f"\n[개별 평가 결과]")
            for eval_key, eval_data in evaluations.items():
                if isinstance(eval_data, dict):
                    score = eval_data.get("score", eval_data.get("average", 0))
                    intent = eval_data.get("intent", eval_key)
                    print(f"  - {intent}: {score:.2f}/100")
        
        # 루브릭별 점수 및 판단 근거 출력
        detailed_feedback = turn_log.get("detailed_feedback", [])
        if detailed_feedback:
            print(f"\n[루브릭별 점수 및 판단 근거]")
            for feedback in detailed_feedback:
                intent = feedback.get("intent", "unknown")
                rubrics = feedback.get("rubrics", [])
                for rubric in rubrics:
                    criterion = rubric.get("criterion", "unknown")
                    score = rubric.get("score", 0)
                    reasoning = rubric.get("reasoning", "")
                    print(f"\n  [{criterion}]")
                    print(f"    점수: {score:.2f}/100")
                    if reasoning:
                        print(f"    판단 근거: {reasoning}")
        
        # 종합 평가 근거
        comprehensive_reasoning = turn_log.get("comprehensive_reasoning", "")
        if comprehensive_reasoning:
            print(f"\n[종합 평가 근거]")
            print(f"  {comprehensive_reasoning}")
        
        # 개별 평가 결과의 final_reasoning도 출력
        if evaluations:
            print(f"\n[개별 평가 상세 근거]")
            for eval_key, eval_data in evaluations.items():
                if isinstance(eval_data, dict):
                    intent = eval_data.get("intent", eval_key)
                    final_reasoning = eval_data.get("final_reasoning", "")
                    if final_reasoning:
                        print(f"\n  [{intent}]")
                        print(f"    {final_reasoning}")
        
        # 토큰 사용량
        if "eval_tokens" in state:
            tokens = state["eval_tokens"]
            print(f"\n[토큰 사용량]")
            print(f"  - Prompt: {tokens.get('prompt_tokens', 0)}")
            print(f"  - Completion: {tokens.get('completion_tokens', 0)}")
            print(f"  - Total: {tokens.get('total_tokens', 0)}")
        
        # 6. DB 저장 (선택적)
        if save_to_db:
            print("\n[5단계] DB 저장 중...")
            print("-" * 80)
            
            try:
                from app.infrastructure.persistence.session import get_db_context
                from app.application.services.evaluation_storage_service import EvaluationStorageService
                
                # session_id와 turn 입력 받기
                print("DB 저장을 위한 정보를 입력하세요:")
                session_id_input = input("  session_id (PostgreSQL id): ").strip()
                turn_input = input("  turn 번호: ").strip()
                
                if session_id_input and turn_input:
                    postgres_session_id = int(session_id_input)
                    turn_number = int(turn_input)
                    
                    async with get_db_context() as db:
                        from app.infrastructure.persistence.models.sessions import PromptMessage
                        from sqlalchemy import select
                        
                        # 먼저 메시지 존재 여부 확인
                        message_query = select(PromptMessage).where(
                            PromptMessage.session_id == postgres_session_id,
                            PromptMessage.turn == turn_number
                        )
                        message_result = await db.execute(message_query)
                        message = message_result.scalar_one_or_none()
                        
                        if not message:
                            print(f"⚠️  DB 저장 실패 - 메시지가 존재하지 않습니다.")
                            print(f"    session_id: {postgres_session_id}, turn: {turn_number}")
                            print(f"    백엔드에서 먼저 메시지를 생성해야 합니다.")
                            print(f"    또는 다른 session_id/turn을 사용해주세요.")
                        else:
                            # role 확인 (ENUM은 'USER', 'AI'만 허용)
                            role = message.role.value if hasattr(message.role, 'value') else str(message.role)
                            if role not in ['USER', 'AI']:
                                print(f"⚠️  DB 저장 실패 - 메시지의 role이 잘못되었습니다.")
                                print(f"    현재 role: {role} (허용 값: 'USER', 'AI')")
                                print(f"    백엔드에서 메시지를 저장할 때 role을 대문자로 저장해야 합니다.")
                            else:
                                storage_service = EvaluationStorageService(db)
                                
                                result = await storage_service.save_turn_evaluation(
                                    session_id=postgres_session_id,
                                    turn=turn_number,
                                    turn_log=turn_log
                                )
                                await db.commit()
                                
                                if result:
                                    print(f"✅ DB 저장 완료 - session_id: {postgres_session_id}, turn: {turn_number}")
                                else:
                                    print(f"⚠️  DB 저장 실패 - 알 수 없는 오류")
                else:
                    print("⚠️  session_id와 turn을 입력하지 않아 DB 저장을 건너뜁니다.")
                
            except ValueError as ve:
                print(f"⚠️  잘못된 입력: {str(ve)}")
            except Exception as db_error:
                print(f"⚠️  DB 저장 실패: {str(db_error)}")
                import traceback
                traceback.print_exc()
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 명령줄 인자 처리
    save_to_db = "--save-db" in sys.argv
    
    if len(sys.argv) >= 3:
        # 명령줄 인자로 메시지 제공
        user_msg = sys.argv[1]
        ai_msg = sys.argv[2]
        spec_id = int(sys.argv[3]) if len(sys.argv) >= 4 and sys.argv[3] != "--save-db" else 2098
        asyncio.run(test_intent_analysis_and_evaluation(user_msg, ai_msg, spec_id, save_to_db))
    else:
        # 대화형 모드
        asyncio.run(test_intent_analysis_and_evaluation(save_to_db=save_to_db))

