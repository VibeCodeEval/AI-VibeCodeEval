"""
비동기 태스크 실행 확인 스크립트
Redis 큐 상태 확인
"""
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.infrastructure.cache.redis_client import redis_client
from app.domain.queue import create_queue_adapter


async def check_async_status():
    """비동기 태스크 상태 확인"""
    print("=" * 80)
    print("비동기 태스크 상태 확인")
    print("=" * 80)
    
    try:
        # Redis 연결
        await redis_client.connect()
        print("✅ Redis 연결 완료")
        
        # 큐 어댑터 생성
        queue = create_queue_adapter()
        print("✅ Queue 어댑터 생성 완료")
        
        # Redis에서 작업 큐 확인
        print("\n[1] Redis 작업 큐 확인")
        try:
            # Redis에서 judge0:queue:* 키 확인
            import redis.asyncio as redis_async
            redis_conn = await redis_async.from_url(
                f"redis://localhost:6379/0",
                decode_responses=True
            )
            
            # 모든 judge0:queue:* 키 조회
            keys = await redis_conn.keys("judge0:queue:*")
            print(f"   발견된 작업 큐 키: {len(keys)}개")
            for key in keys[:10]:  # 최대 10개만 표시
                print(f"   - {key}")
            
            await redis_conn.close()
        except Exception as e:
            print(f"   ⚠️ Redis 키 조회 실패: {str(e)}")
        
        # State 확인
        print("\n[2] Redis State 확인 (session_1000)")
        try:
            state = await redis_client.get_graph_state("session_1000")
            if state:
                print(f"   ✅ State 발견")
                print(f"   - current_turn: {state.get('current_turn', 'N/A')}")
                print(f"   - is_submitted: {state.get('is_submitted', False)}")
                print(f"   - code_content 길이: {len(state.get('code_content', '')) if state.get('code_content') else 0}")
                print(f"   - messages 개수: {len(state.get('messages', []))}")
            else:
                print("   ⚠️ State를 찾을 수 없습니다.")
        except Exception as e:
            print(f"   ⚠️ State 조회 실패: {str(e)}")
        
        # Turn Logs 확인
        print("\n[3] Turn Logs 확인")
        try:
            turn_logs = await redis_client.get_all_turn_logs("session_1000")
            if turn_logs:
                print(f"   ✅ Turn Logs 발견: {len(turn_logs)}개")
                for turn_key, turn_log in list(turn_logs.items())[:5]:
                    print(f"   - Turn {turn_key}: {turn_log.get('prompt_evaluation_details', {}).get('score', 'N/A') if isinstance(turn_log, dict) else 'N/A'}")
            else:
                print("   ⚠️ Turn Logs를 찾을 수 없습니다.")
        except Exception as e:
            print(f"   ⚠️ Turn Logs 조회 실패: {str(e)}")
        
        await redis_client.close()
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(check_async_status())

