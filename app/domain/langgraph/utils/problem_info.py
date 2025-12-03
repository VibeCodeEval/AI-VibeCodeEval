"""
문제 정보 관리 모듈
하드코딩 → DB 전환을 고려한 구조

[데이터 구조]
- HARDCODED_PROBLEM_SPEC: 상세한 문제 정보 (basic_info, constraints, ai_guide, solution_code)
- 추후 DB의 ProblemSpec.meta (JSON) 컬럼과 동일한 구조로 저장 예정
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


# 하드코딩 딕셔너리 (상세 구조)
# 추후 DB의 ProblemSpec.meta (JSON) 컬럼과 동일한 구조
HARDCODED_PROBLEM_SPEC: Dict[int, Dict[str, Any]] = {
    10: {  # spec_id = 10 (백준 2098번 - 외판원 순회)
        # 1. 기본 정보 (프론트엔드 표시 및 AI 문맥 파악용)
        "basic_info": {
            "problem_id": "2098",
            "title": "외판원 순회",
            "description_summary": "1번 도시에서 출발하여 모든 도시를 단 한 번씩 거쳐 다시 1번 도시로 돌아오는 최소 비용의 경로를 구하는 문제.",
            "input_format": "첫째 줄에 도시의 수 N (2 ≤ N ≤ 16). 다음 N개의 줄에 비용 행렬 W가 주어짐. W[i][j]는 도시 i에서 j로 가기 위한 비용 (0은 갈 수 없음).",
            "output_format": "첫째 줄에 순회에 필요한 최소 비용을 출력."
        },
        
        # 2. 제약 조건 (AI가 알고리즘을 판단하고, 사용자의 비현실적 요청을 거르는 기준)
        "constraints": {
            "time_limit_sec": 1.0,
            "memory_limit_mb": 128,
            "variable_ranges": {
                "N": "2 <= N <= 16",
                "Cost": "0 <= W[i][j] <= 1,000,000"
            },
            # AI가 이 문제를 '비트마스킹 DP'라고 확신하는 결정적 근거
            "logic_reasoning": "N이 최대 16이므로, O(N!)의 완전 탐색(약 20조 연산)은 시간 초과가 발생함. 따라서 O(N^2 * 2^N) 시간 복잡도를 가지는 '비트마스킹을 이용한 DP'를 사용해야 함."
        },
        
        # 3. AI 튜터링 가이드 (Writer LLM이 힌트를 주거나, Holistic Eval이 전략을 평가할 때 사용)
        "ai_guide": {
            "key_algorithms": ["Dynamic Programming", "Bitmasking", "DFS", "TSP"],
            "solution_architecture": "Top-down DFS with Memoization",
            
            # 힌트 로드맵 (단계별 힌트 제공용)
            "hint_roadmap": {
                "step_1_concept": "N이 작다는 점(16)에 주목하세요. 방문한 도시들의 상태를 효율적으로 저장할 방법이 필요합니다. 배열보다는 '비트(Bit)'를 사용해보면 어떨까요?",
                "step_2_state": "상태를 `dp[current_city][visited_bitmask]`로 정의해보세요. `visited_bitmask`의 i번째 비트가 1이면 i번 도시를 방문했다는 뜻입니다.",
                "step_3_transition": "점화식: `FindPath(curr, visited) = min(W[curr][next] + FindPath(next, visited | (1<<next)))` (단, next는 아직 방문하지 않은 도시)",
                "step_4_base_case": "모든 도시를 방문했을 때(`visited == (1<<N) - 1`), 현재 도시에서 출발 도시(0)로 돌아가는 길이 있는지 확인하고 비용을 반환해야 합니다."
            },
            
            # 자주 틀리는 실수 (디버깅 요청 시 체크 포인트)
            "common_pitfalls": [
                "갈 수 없는 길(W[i][j] == 0)인 경우를 체크하지 않음.",
                "DP 배열을 0으로 초기화하면 '방문 안 함'과 '비용 0'이 구분되지 않음. -1이나 INF로 초기화해야 함.",
                "마지막 도시에서 시작 도시로 돌아올 수 없는 경우를 예외 처리하지 않음 (INF 반환 필요)."
            ]
        },
        
        # 4. 정답 코드 (AI가 코드를 참고하여 구체적인 피드백을 줄 때 사용)
        "solution_code": """import sys

def tsp(current, visited):
    # 모든 도시를 방문한 경우
    if visited == (1 << N) - 1:
        # 출발 도시(0)로 돌아갈 수 있는 경우
        if W[current][0] != 0:
            return W[current][0]
        else:
            return float('inf')
    
    # 이미 계산된 경우 (Memoization)
    if dp[current][visited] != -1:
        return dp[current][visited]
    
    dp[current][visited] = float('inf')
    for i in range(N):
        # i번 도시를 아직 방문하지 않았고, 가는 길이 있는 경우
        if not (visited & (1 << i)) and W[current][i] != 0:
            dp[current][visited] = min(dp[current][visited], tsp(i, visited | (1 << i)) + W[current][i])
    
    return dp[current][visited]

N = int(sys.stdin.readline())
W = [list(map(int, sys.stdin.readline().split())) for _ in range(N)]
dp = [[-1] * (1 << N) for _ in range(N)]
print(tsp(0, 1))
""",
        
        # 5. 가드레일용 키워드 (하위 호환성 및 Intent Analyzer에서 사용)
        "keywords": [
            "외판원",
            "tsp",
            "traveling salesman",
            "dp[현재도시][방문도시]",
            "방문 상태"
        ]
    },
    # 추후 다른 문제 추가 가능
    # 11: {
    #     "basic_info": {...},
    #     "constraints": {...},
    #     "ai_guide": {...},
    #     "solution_code": "...",
    #     "keywords": [...]
    # },
}


def get_problem_info_sync(spec_id: int) -> Dict[str, Any]:
    """
    spec_id로 문제 정보 가져오기 (동기 버전)
    
    [현재 구현]
    - 하드코딩 딕셔너리 사용 (HARDCODED_PROBLEM_SPEC)
    
    [사용 위치]
    - get_initial_state() 등 동기 함수에서 사용
    - handle_request에서 problem_context로 저장
    
    Args:
        spec_id: 문제 스펙 ID
    
    Returns:
        Dict[str, Any]: 상세한 문제 정보 (basic_info, constraints, ai_guide, solution_code 포함)
    """
    # 하드코딩 딕셔너리 사용
    if spec_id in HARDCODED_PROBLEM_SPEC:
        problem_context = HARDCODED_PROBLEM_SPEC[spec_id].copy()
        problem_name = problem_context.get("basic_info", {}).get("title", "알 수 없음")
        logger.debug(f"[Problem Info] 하드코딩 딕셔너리에서 조회 - spec_id: {spec_id}, problem_name: {problem_name}")
        return problem_context
    
    # 기본값 반환 (문제 정보 없음)
    logger.debug(f"[Problem Info] 기본값 반환 - spec_id: {spec_id} (문제 정보 없음)")
    return {
        "basic_info": {
            "problem_id": str(spec_id),
            "title": "",
            "description_summary": None,
            "input_format": None,
            "output_format": None
        },
        "constraints": {
            "time_limit_sec": None,
            "memory_limit_mb": None,
            "variable_ranges": {},
            "logic_reasoning": None
        },
        "ai_guide": {
            "key_algorithms": [],
            "solution_architecture": None,
            "hint_roadmap": {},
            "common_pitfalls": []
        },
        "solution_code": None,
        "keywords": []
    }


async def get_problem_info(spec_id: int, db: Optional[Any] = None) -> Dict[str, Any]:
    """
    spec_id로 문제 정보 가져오기 (비동기 버전)
    
    [현재 구현]
    - 하드코딩 딕셔너리 사용 (HARDCODED_PROBLEM_SPEC)
    
    [추후 DB 전환]
    - db 파라미터를 받아서 DB 조회 가능
    - ProblemSpec.meta (JSON) 컬럼에서 problem_context 조회
    - 하드코딩 딕셔너리는 Fallback으로 사용
    
    Args:
        spec_id: 문제 스펙 ID
        db: 데이터베이스 세션 (선택, 추후 DB 조회용)
    
    Returns:
        Dict[str, Any]: 상세한 문제 정보 (basic_info, constraints, ai_guide, solution_code 포함)
    """
    # 현재: 하드코딩 딕셔너리 사용
    if spec_id in HARDCODED_PROBLEM_SPEC:
        problem_context = HARDCODED_PROBLEM_SPEC[spec_id].copy()
        problem_name = problem_context.get("basic_info", {}).get("title", "알 수 없음")
        logger.debug(f"[Problem Info] 하드코딩 딕셔너리에서 조회 - spec_id: {spec_id}, problem_name: {problem_name}")
        return problem_context
    
    # 추후: DB 조회로 교체 가능
    # if db:
    #     try:
    #         from app.infrastructure.repositories.exam_repository import ExamRepository
    #         exam_repo = ExamRepository(db)
    #         spec = await exam_repo.get_problem_spec(spec_id)
    #         
    #         if spec and spec.meta:
    #             # ProblemSpec.meta (JSON) 컬럼에서 problem_context 조회
    #             # meta 구조: {"basic_info": {...}, "constraints": {...}, "ai_guide": {...}, "solution_code": "..."}
    #             problem_context = spec.meta.copy()
    #             
    #             # keywords는 meta에 없을 수 있으므로 추출
    #             if "keywords" not in problem_context:
    #                 problem_context["keywords"] = _extract_keywords_from_problem_spec(spec)
    #             
    #             logger.debug(f"[Problem Info] DB에서 조회 - spec_id: {spec_id}, problem_name: {problem_context.get('basic_info', {}).get('title', '알 수 없음')}")
    #             return problem_context
    #     except Exception as e:
    #         logger.warning(f"[Problem Info] DB 조회 실패 - spec_id: {spec_id}, error: {str(e)}")
    #         # Fallback: 하드코딩 딕셔너리 재시도
    #         if spec_id in HARDCODED_PROBLEM_SPEC:
    #             problem_context = HARDCODED_PROBLEM_SPEC[spec_id].copy()
    #             logger.debug(f"[Problem Info] Fallback 하드코딩 사용 - spec_id: {spec_id}")
    #             return problem_context
    
    # 기본값 반환 (문제 정보 없음)
    logger.debug(f"[Problem Info] 기본값 반환 - spec_id: {spec_id} (문제 정보 없음)")
    return {
        "basic_info": {
            "problem_id": str(spec_id),
            "title": "",
            "description_summary": None,
            "input_format": None,
            "output_format": None
        },
        "constraints": {
            "time_limit_sec": None,
            "memory_limit_mb": None,
            "variable_ranges": {},
            "logic_reasoning": None
        },
        "ai_guide": {
            "key_algorithms": [],
            "solution_architecture": None,
            "hint_roadmap": {},
            "common_pitfalls": []
        },
        "solution_code": None,
        "keywords": []
    }


def _extract_keywords_from_problem_spec(spec: Any) -> list[str]:
    """
    ProblemSpec 모델에서 가드레일용 키워드 추출 (추후 DB 전환 시 사용)
    
    [사용 위치]
    - get_problem_info()에서 DB 조회 시 keywords가 없을 경우 호출
    
    Args:
        spec: ProblemSpec 모델 인스턴스
    
    Returns:
        list[str]: 키워드 리스트
    """
    keywords = []
    
    # meta에서 keywords 추출 (이미 있으면 사용)
    if spec.meta and isinstance(spec.meta, dict):
        if "keywords" in spec.meta and isinstance(spec.meta["keywords"], list):
            keywords.extend(spec.meta["keywords"])
    
    # ai_guide.key_algorithms에서 키워드 추출
    if spec.meta and isinstance(spec.meta, dict):
        ai_guide = spec.meta.get("ai_guide", {})
        if isinstance(ai_guide, dict):
            key_algorithms = ai_guide.get("key_algorithms", [])
            if isinstance(key_algorithms, list):
                keywords.extend([alg.lower() for alg in key_algorithms])
    
    # basic_info.title에서 키워드 추출
    if spec.meta and isinstance(spec.meta, dict):
        basic_info = spec.meta.get("basic_info", {})
        if isinstance(basic_info, dict):
            title = basic_info.get("title", "")
            if title:
                title_lower = title.lower()
                # 일반적인 알고리즘 키워드 체크
                algorithm_keywords = ["tsp", "외판원", "dp", "그래프", "트리", "정렬"]
                for keyword in algorithm_keywords:
                    if keyword in title_lower:
                        keywords.append(keyword)
    
    return list(set(keywords))  # 중복 제거

