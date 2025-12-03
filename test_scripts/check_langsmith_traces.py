"""
LangSmith 추적 이력 확인 스크립트
터미널에서 LangSmith 추적 내역을 조회합니다.
"""
import sys
import os
from datetime import datetime, timedelta
from typing import Optional

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langsmith import Client
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경 변수에서 설정 읽기
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "langgraph-eval-dev")
LANGCHAIN_ENDPOINT = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")


def check_langsmith_connection():
    """LangSmith 연결 확인"""
    print(f"\n{'='*80}")
    print(f"[LangSmith 연결 확인]")
    print(f"{'='*80}")
    
    if not LANGCHAIN_TRACING_V2:
        print("⚠️ LangSmith 추적이 비활성화되어 있습니다.")
        print("   .env 파일에 LANGCHAIN_TRACING_V2=true 설정 필요")
        return None
    
    if not LANGCHAIN_API_KEY:
        print("⚠️ LangSmith API Key가 설정되지 않았습니다.")
        print("   .env 파일에 LANGCHAIN_API_KEY 설정 필요")
        return None
    
    try:
        client = Client(
            api_key=LANGCHAIN_API_KEY,
            api_url=LANGCHAIN_ENDPOINT
        )
        print(f"✅ LangSmith 연결 성공")
        print(f"   프로젝트: {LANGCHAIN_PROJECT}")
        print(f"   엔드포인트: {LANGCHAIN_ENDPOINT}")
        return client
    except Exception as e:
        print(f"❌ LangSmith 연결 실패: {str(e)}")
        return None


def list_recent_traces(client: Client, limit: int = 10, project_name: Optional[str] = None):
    """최근 추적 내역 조회"""
    print(f"\n{'='*80}")
    print(f"[최근 추적 내역 조회]")
    print(f"{'='*80}")
    
    project_name = project_name or LANGCHAIN_PROJECT
    
    try:
        # 최근 1시간 내 추적 내역 조회
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=1)
        
        runs = client.list_runs(
            project_name=project_name,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        runs_list = list(runs)
        print(f"\n발견된 추적: {len(runs_list)}개 (최근 1시간)")
        
        if not runs_list:
            print("   추적 내역이 없습니다.")
            return
        
        for i, run in enumerate(runs_list, 1):
            print(f"\n[{i}] {run.name or 'Unnamed'}")
            print(f"    Run ID: {run.id}")
            print(f"    Trace ID: {run.trace_id}")
            print(f"    시작 시간: {run.start_time}")
            print(f"    종료 시간: {run.end_time}")
            if run.end_time and run.start_time:
                duration = (run.end_time - run.start_time).total_seconds()
                print(f"    실행 시간: {duration:.2f}초")
            else:
                print(f"    실행 시간: N/A")
            print(f"    상태: {run.status}")
            if run.error:
                print(f"    에러: {run.error}")
            if run.extra:
                print(f"    태그: {run.extra.get('tags', [])}")
        
    except Exception as e:
        print(f"❌ 추적 내역 조회 실패: {str(e)}")


def list_traces_by_session(client: Client, session_id: str, project_name: Optional[str] = None):
    """특정 세션의 추적 내역 조회"""
    print(f"\n{'='*80}")
    print(f"[세션별 추적 내역 조회]")
    print(f"{'='*80}")
    print(f"Session ID: {session_id}")
    
    project_name = project_name or LANGCHAIN_PROJECT
    
    try:
        # 최근 24시간 내 추적 내역 조회
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        runs = client.list_runs(
            project_name=project_name,
            start_time=start_time,
            end_time=end_time,
            filter=f'has(tags, "{session_id}")',  # 태그로 필터링
            limit=50
        )
        
        runs_list = list(runs)
        print(f"\n발견된 추적: {len(runs_list)}개")
        
        if not runs_list:
            print("   해당 세션의 추적 내역이 없습니다.")
            print("   참고: 세션 ID는 태그로 저장되어야 합니다.")
            return
        
        for i, run in enumerate(runs_list, 1):
            print(f"\n[{i}] {run.name or 'Unnamed'}")
            print(f"    Run ID: {run.id}")
            print(f"    Trace ID: {run.trace_id}")
            print(f"    시작 시간: {run.start_time}")
            if run.end_time and run.start_time:
                duration = (run.end_time - run.start_time).total_seconds()
                print(f"    실행 시간: {duration:.2f}초")
            else:
                print(f"    실행 시간: N/A")
            print(f"    상태: {run.status}")
        
    except Exception as e:
        print(f"❌ 세션별 추적 내역 조회 실패: {str(e)}")


def list_traces_by_node(client: Client, node_name: str, project_name: Optional[str] = None):
    """특정 노드의 추적 내역 조회 (6.X 노드)"""
    print(f"\n{'='*80}")
    print(f"[노드별 추적 내역 조회]")
    print(f"{'='*80}")
    print(f"Node: {node_name}")
    
    project_name = project_name or LANGCHAIN_PROJECT
    
    try:
        # 최근 24시간 내 추적 내역 조회
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=24)
        
        # 노드 이름으로 필터링
        runs = client.list_runs(
            project_name=project_name,
            start_time=start_time,
            end_time=end_time,
            filter=f'eq(name, "{node_name}")',
            limit=20
        )
        
        runs_list = list(runs)
        print(f"\n발견된 추적: {len(runs_list)}개")
        
        if not runs_list:
            print(f"   '{node_name}' 노드의 추적 내역이 없습니다.")
            return
        
        for i, run in enumerate(runs_list, 1):
            print(f"\n[{i}] {run.name}")
            print(f"    Run ID: {run.id}")
            print(f"    Trace ID: {run.trace_id}")
            print(f"    시작 시간: {run.start_time}")
            if run.end_time and run.start_time:
                duration = (run.end_time - run.start_time).total_seconds()
                print(f"    실행 시간: {duration:.2f}초")
            else:
                print(f"    실행 시간: N/A")
            print(f"    상태: {run.status}")
            if run.extra and run.extra.get('tags'):
                print(f"    태그: {run.extra.get('tags')}")
        
    except Exception as e:
        print(f"❌ 노드별 추적 내역 조회 실패: {str(e)}")


def get_trace_details(client: Client, trace_id: str):
    """특정 추적의 상세 정보 조회"""
    print(f"\n{'='*80}")
    print(f"[추적 상세 정보]")
    print(f"{'='*80}")
    print(f"Trace ID: {trace_id}")
    
    try:
        trace = client.read_trace(trace_id)
        
        print(f"\n[기본 정보]")
        print(f"  Trace ID: {trace.id}")
        print(f"  프로젝트: {trace.project_name}")
        print(f"  시작 시간: {trace.start_time}")
        print(f"  종료 시간: {trace.end_time}")
        if trace.end_time and trace.start_time:
            duration = (trace.end_time - trace.start_time).total_seconds()
            print(f"  총 실행 시간: {duration:.2f}초")
        else:
            print(f"  총 실행 시간: N/A")
        
        # Runs 조회
        runs = client.list_runs(trace_id=trace_id)
        runs_list = list(runs)
        
        print(f"\n[포함된 Runs: {len(runs_list)}개]")
        for i, run in enumerate(runs_list, 1):
            print(f"\n  [{i}] {run.name or 'Unnamed'}")
            print(f"      Run ID: {run.id}")
            print(f"      시작 시간: {run.start_time}")
            if run.end_time and run.start_time:
                duration = (run.end_time - run.start_time).total_seconds()
                print(f"      실행 시간: {duration:.2f}초")
            else:
                print(f"      실행 시간: N/A")
            print(f"      상태: {run.status}")
            if run.error:
                print(f"      에러: {run.error}")
        
    except Exception as e:
        print(f"❌ 추적 상세 정보 조회 실패: {str(e)}")


def main():
    """메인 함수"""
    print(f"{'#'*80}")
    print(f"# LangSmith 추적 이력 확인")
    print(f"{'#'*80}")
    
    # LangSmith 연결 확인
    client = check_langsmith_connection()
    if not client:
        return
    
    # 최근 추적 내역 조회
    list_recent_traces(client, limit=10)
    
    # 6.X 노드별 추적 내역 조회
    print(f"\n{'='*80}")
    print(f"[6.X 노드 추적 내역]")
    print(f"{'='*80}")
    
    node_names = [
        "eval_holistic_flow",      # 6a
        "eval_code_performance",    # 6c
        "eval_code_correctness"     # 6d
    ]
    
    for node_name in node_names:
        list_traces_by_node(client, node_name)
    
    print(f"\n{'='*80}")
    print(f"[사용 방법]")
    print(f"{'='*80}")
    print(f"1. 최근 추적 내역: python test_scripts/check_langsmith_traces.py")
    print(f"2. 세션별 조회: list_traces_by_session(client, 'session-id')")
    print(f"3. 노드별 조회: list_traces_by_node(client, 'eval_holistic_flow')")
    print(f"4. 상세 정보: get_trace_details(client, 'trace-id')")
    print(f"\n5. LangSmith 웹사이트: https://smith.langchain.com/")
    print(f"   - 프로젝트: {LANGCHAIN_PROJECT}")
    print(f"   - Traces 탭에서 시각적으로 확인 가능")


if __name__ == "__main__":
    main()

