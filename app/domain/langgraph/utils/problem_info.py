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
        
        # 5. 테스트 케이스 (Judge0 코드 실행 평가용)
        "test_cases": [
    {
        "input": "4\n0 10 15 20\n5 0 9 10\n6 13 0 12\n8 8 9 0\n",
        "expected": "35",
        "description": "기본 케이스: 4개 도시"
    },
    {
        "input": "3\n0 1 2\n1 0 3\n2 3 0\n",
        "expected": "6",
        "description": "최소 케이스: 3개 도시"
    },
    {
        "input": "2\n0 10\n10 0\n",
        "expected": "20",
        "description": "최소 케이스: 2개 도시"
    },
    {
        "input": "5\n0 1 2 3 4\n1 0 5 6 7\n2 5 0 8 9\n3 6 8 0 10\n4 7 9 10 0\n",
        "expected": "21",
        "description": "5개 도시 케이스"
    },
    {
        "input": "6\n0 1 2 3 4 5\n1 0 6 7 8 9\n2 6 0 10 11 12\n3 7 10 0 13 14\n4 8 11 13 0 15\n5 9 12 14 15 0\n",
        "expected": "27",
        "description": "6개 도시 케이스"
    },
    {
        "input": "4\n0 1 100 100\n1 0 1 100\n100 1 0 1\n1 100 1 0\n",
        "expected": "4",
        "description": "비대칭 비용 행렬 (수정됨)"
    },
    {
        "input": "4\n0 0 1 1\n0 0 1 1\n1 1 0 0\n1 1 0 0\n",
        "expected": "4",
        "description": "갈 수 없는 경로 포함 (0 처리)"
    },
    {
        "input": "3\n0 5 10\n5 0 15\n10 15 0\n",
        "expected": "30",
        "description": "대칭 비용 행렬"
    },
    {
        "input": "4\n0 2 9 10\n1 0 6 4\n15 7 0 8\n6 3 12 0\n",
        "expected": "21",
        "description": "복잡한 비용 행렬"
    },
    {
        "input": "5\n0 3 4 2 7\n3 0 4 6 3\n4 4 0 5 8\n2 6 5 0 6\n7 3 8 6 0\n",
        "expected": "19",
        "description": "대규모 케이스: 5개 도시"
    }
],
        
        # 6. 채점 기준 (Rubric)
        "rubric": {
            "correctness": {
                "weight": 0.5,
                "description": "정확성 점수 (테스트 케이스 통과율)",
                "criteria": {
                    "all_passed": {
                        "score": 100,
                        "description": "모든 테스트 케이스 통과"
                    },
                    "partial_passed": {
                        "score_formula": "(통과한_테스트_케이스_수 / 전체_테스트_케이스_수) * 100",
                        "description": "일부 테스트 케이스 통과"
                    },
                    "none_passed": {
                        "score": 0,
                        "description": "테스트 케이스 통과 실패"
                    }
                }
            },
            "performance": {
                "weight": 0.25,
                "description": "성능 점수 (실행 시간 및 메모리 사용량)",
                "time_limit_sec": 1.0,  # 백준과 동일: 1초 제한
                "memory_limit_mb": 128,  # 백준과 동일: 128MB 제한
                "criteria": {
                    "time_score": {
                        "weight": 0.6,
                        "description": "실행 시간 점수",
                        "limit_sec": 1.0,
                        "scoring": {
                            "within_limit": {
                                "score": 100,
                                "description": "1초 이내: 100점"
                            },
                            "exceeded": {
                                "score_formula": "max(0, 100 * (1 - execution_time / time_limit))",
                                "description": "1초 초과 시 감점 (초과 시간에 비례)"
                            }
                        }
                    },
                    "memory_score": {
                        "weight": 0.4,
                        "description": "메모리 사용량 점수",
                        "limit_mb": 128,
                        "scoring": {
                            "within_limit": {
                                "score": 100,
                                "description": "128MB 이내: 100점"
                            },
                            "exceeded": {
                                "score_formula": "max(0, 100 * (1 - memory_used / memory_limit))",
                                "description": "128MB 초과 시 감점 (초과 메모리에 비례)"
                            }
                        }
                    }
                }
            },
            "code_quality": {
                "weight": 0.25,
                "description": "코드 품질 점수 (알고리즘 효율성, 가독성)",
                "criteria": {
                    "algorithm_efficiency": {
                        "weight": 0.6,
                        "description": "알고리즘 효율성 (비트마스킹 DP 사용: 100점, 완전 탐색: 50점, 그 외: 0점)"
                    },
                    "code_readability": {
                        "weight": 0.4,
                        "description": "코드 가독성 (변수명, 주석, 구조)"
                    }
                }
            }
        },
        
        # 7. 가드레일용 키워드 (하위 호환성 및 Intent Analyzer에서 사용)
        "keywords": [
            "외판원",
            "tsp",
            "traveling salesman",
            "dp[현재도시][방문도시]",
            "방문 상태"
        ]
    },
    2: {  # spec_id = 2 (외판원 순회 - 테스트용)
        # 1. 기본 정보
        "basic_info": {
            "problem_id": "2",
            "title": "외판원 순회",
            "description_summary": "1번 도시에서 출발하여 모든 도시를 단 한 번씩 거쳐 다시 1번 도시로 돌아오는 최소 비용의 경로를 구하는 문제.",
            "input_format": "첫째 줄에 도시의 수 N (2 ≤ N ≤ 16). 다음 N개의 줄에 비용 행렬 W가 주어짐. W[i][j]는 도시 i에서 j로 가기 위한 비용 (0은 갈 수 없음).",
            "output_format": "첫째 줄에 순회에 필요한 최소 비용을 출력."
        },
        
        # 2. 제약 조건
        "constraints": {
            "time_limit_sec": 1.0,
            "memory_limit_mb": 128,
            "variable_ranges": {
                "N": "2 <= N <= 16",
                "Cost": "0 <= W[i][j] <= 1,000,000"
            },
            "logic_reasoning": "N이 최대 16이므로, O(N!)의 완전 탐색(약 20조 연산)은 시간 초과가 발생함. 따라서 O(N^2 * 2^N) 시간 복잡도를 가지는 '비트마스킹을 이용한 DP'를 사용해야 함."
        },
        
        # 3. AI 튜터링 가이드
        "ai_guide": {
            "key_algorithms": ["Dynamic Programming", "Bitmasking", "DFS", "TSP"],
            "solution_architecture": "Top-down DFS with Memoization",
            "hint_roadmap": {
                "step_1_concept": "N이 작다는 점(16)에 주목하세요. 방문한 도시들의 상태를 효율적으로 저장할 방법이 필요합니다. 배열보다는 '비트(Bit)'를 사용해보면 어떨까요?",
                "step_2_state": "상태를 `dp[current_city][visited_bitmask]`로 정의해보세요. `visited_bitmask`의 i번째 비트가 1이면 i번 도시를 방문했다는 뜻입니다.",
                "step_3_transition": "점화식: `FindPath(curr, visited) = min(W[curr][next] + FindPath(next, visited | (1<<next)))` (단, next는 아직 방문하지 않은 도시)",
                "step_4_base_case": "모든 도시를 방문했을 때(`visited == (1<<N) - 1`), 현재 도시에서 출발 도시(0)로 돌아가는 길이 있는지 확인하고 비용을 반환해야 합니다."
            },
            "common_pitfalls": [
                "갈 수 없는 길(W[i][j] == 0)인 경우를 체크하지 않음.",
                "DP 배열을 0으로 초기화하면 '방문 안 함'과 '비용 0'이 구분되지 않음. -1이나 INF로 초기화해야 함.",
                "마지막 도시에서 시작 도시로 돌아올 수 없는 경우를 예외 처리하지 않음 (INF 반환 필요)."
            ]
        },
        
        # 4. 정답 코드 (spec_id: 10과 동일)
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
        
        # 5. 테스트 케이스 (1개만 - spec_id: 10의 첫 번째 TC 사용)
        "test_cases": [
            {
                "input": "4\n0 10 15 20\n5 0 9 10\n6 13 0 12\n8 8 9 0\n",
                "expected": "35",
                "description": "기본 케이스: 4개 도시 (외판원 문제)"
            }
        ],
        
        # 6. 채점 기준 (기본값)
        "rubric": {
            "correctness": {
                "weight": 0.5,
                "description": "정확성 점수"
            },
            "performance": {
                "weight": 0.25,
                "description": "성능 점수"
            },
            "code_quality": {
                "weight": 0.25,
                "description": "코드 품질 점수"
            }
        },
        
        # 7. 가드레일용 키워드
        "keywords": ["외판원", "tsp", "traveling salesman", "DP", "비트마스킹", "bitmasking"]
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
    # 외판원 문제의 기본 테스트 케이스 1개 제공
    logger.warning(f"[Problem Info] 기본값 반환 - spec_id: {spec_id} (문제 정보 없음, HARDCODED_PROBLEM_SPEC에 정의되지 않음)")
    logger.warning(f"[Problem Info] 기본 테스트 케이스 제공 (외판원 문제 - 백준 2098번)")
    return {
        "basic_info": {
            "problem_id": str(spec_id),
            "title": "",
            "description_summary": None,
            "input_format": None,
            "output_format": None
        },
        "constraints": {
            "time_limit_sec": 1.0,
            "memory_limit_mb": 128,
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
        "keywords": [],
        # 외판원 문제의 기본 테스트 케이스 1개 제공
        "test_cases": [
            {
                "input": "4\n0 10 15 20\n5 0 9 10\n6 13 0 12\n8 8 9 0\n",
                "expected": "35",
                "description": "기본 케이스: 4개 도시 (외판원 문제)"
            }
        ]
    }


async def get_problem_info(spec_id: int, db: Optional[Any] = None) -> Dict[str, Any]:
    """
    spec_id로 문제 정보 가져오기 (비동기 버전)
    
    [구현]
    - DB 조회 우선, 실패 시 하드코딩 딕셔너리 Fallback
    - ProblemSpec과 Problem 테이블에서 정보 조회
    - content_md, rubric_json 등을 활용하여 problem_context 구성
    
    Args:
        spec_id: 문제 스펙 ID
        db: 데이터베이스 세션 (필수)
    
    Returns:
        Dict[str, Any]: 상세한 문제 정보 (basic_info, constraints, ai_guide, solution_code 포함)
    """
    # DB 조회 시도
    if db:
        try:
            from app.infrastructure.repositories.exam_repository import ExamRepository
            exam_repo = ExamRepository(db)
            spec = await exam_repo.get_problem_spec_with_problem(spec_id)
            
            if spec and spec.problem:
                problem = spec.problem
                
                # basic_info 구성
                basic_info = {
                    "problem_id": str(problem.id),
                    "title": problem.title or "",
                    "description_summary": spec.content_md[:200] if spec.content_md else None,  # 처음 200자
                    "input_format": None,  # content_md에서 파싱 필요 시 추가
                    "output_format": None  # content_md에서 파싱 필요 시 추가
                }
                
                # constraints 구성 (rubric_json에서 가져오거나 기본값)
                constraints = {
                    "time_limit_sec": None,
                    "memory_limit_mb": None,
                    "variable_ranges": {},
                    "logic_reasoning": None
                }
                if spec.rubric_json and isinstance(spec.rubric_json, dict):
                    performance = spec.rubric_json.get("performance", {})
                    if isinstance(performance, dict):
                        constraints["time_limit_sec"] = performance.get("time_limit_sec")
                        constraints["memory_limit_mb"] = performance.get("memory_limit_mb")
                
                # ai_guide 구성 (rubric_json에서 가져오거나 기본값)
                ai_guide = {
                    "key_algorithms": [],
                    "solution_architecture": None,
                    "hint_roadmap": {},
                    "common_pitfalls": []
                }
                if spec.rubric_json and isinstance(spec.rubric_json, dict):
                    code_quality = spec.rubric_json.get("code_quality", {})
                    if isinstance(code_quality, dict):
                        ai_guide["key_algorithms"] = code_quality.get("algorithms", [])
                
                # keywords 추출
                keywords = _extract_keywords_from_problem_spec(spec)
                
                problem_context = {
                    "basic_info": basic_info,
                    "constraints": constraints,
                    "ai_guide": ai_guide,
                    "solution_code": None,  # checker_json에서 가져올 수 있으면 추가
                    "keywords": keywords,
                    "content_md": spec.content_md  # 전체 내용도 포함
                }
                
                problem_name = basic_info.get("title", "알 수 없음")
                logger.debug(f"[Problem Info] DB에서 조회 - spec_id: {spec_id}, problem_name: {problem_name}")
                return problem_context
            else:
                # DB에 spec이 없거나 problem이 없는 경우 → 하드코딩 딕셔너리로 Fallback
                logger.debug(f"[Problem Info] DB에 spec 없음 - spec_id: {spec_id}, 하드코딩 딕셔너리로 Fallback")
                if spec_id in HARDCODED_PROBLEM_SPEC:
                    problem_context = HARDCODED_PROBLEM_SPEC[spec_id].copy()
                    logger.debug(f"[Problem Info] Fallback 하드코딩 사용 - spec_id: {spec_id}")
                    return problem_context
                
        except Exception as e:
            logger.warning(f"[Problem Info] DB 조회 실패 - spec_id: {spec_id}, error: {str(e)}")
            # Fallback: 하드코딩 딕셔너리 재시도
            if spec_id in HARDCODED_PROBLEM_SPEC:
                problem_context = HARDCODED_PROBLEM_SPEC[spec_id].copy()
                logger.debug(f"[Problem Info] Fallback 하드코딩 사용 - spec_id: {spec_id}")
                return problem_context
    
    # Fallback: 하드코딩 딕셔너리 사용
    if spec_id in HARDCODED_PROBLEM_SPEC:
        problem_context = HARDCODED_PROBLEM_SPEC[spec_id].copy()
        problem_name = problem_context.get("basic_info", {}).get("title", "알 수 없음")
        logger.debug(f"[Problem Info] 하드코딩 딕셔너리에서 조회 - spec_id: {spec_id}, problem_name: {problem_name}")
        return problem_context
    
    # 기본값 반환 (문제 정보 없음)
    # 외판원 문제의 기본 테스트 케이스 1개 제공
    logger.warning(f"[Problem Info] 기본값 반환 - spec_id: {spec_id} (문제 정보 없음, HARDCODED_PROBLEM_SPEC에 정의되지 않음)")
    logger.warning(f"[Problem Info] 기본 테스트 케이스 제공 (외판원 문제 - 백준 2098번)")
    return {
        "basic_info": {
            "problem_id": str(spec_id),
            "title": "",
            "description_summary": None,
            "input_format": None,
            "output_format": None
        },
        "constraints": {
            "time_limit_sec": 1.0,
            "memory_limit_mb": 128,
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
        "keywords": [],
        # 외판원 문제의 기본 테스트 케이스 1개 제공
        "test_cases": [
            {
                "input": "4\n0 10 15 20\n5 0 9 10\n6 13 0 12\n8 8 9 0\n",
                "expected": "35",
                "description": "기본 케이스: 4개 도시 (외판원 문제)"
            }
        ]
    }


def _extract_keywords_from_problem_spec(spec: Any) -> list[str]:
    """
    ProblemSpec 모델에서 가드레일용 키워드 추출
    
    [사용 위치]
    - get_problem_info()에서 DB 조회 시 keywords 추출
    
    Args:
        spec: ProblemSpec 모델 인스턴스
    
    Returns:
        list[str]: 키워드 리스트
    """
    keywords = []
    
    # Problem title에서 키워드 추출
    if spec.problem and spec.problem.title:
        title_lower = spec.problem.title.lower()
        # 일반적인 알고리즘 키워드 체크
        algorithm_keywords = ["tsp", "외판원", "dp", "그래프", "트리", "정렬", "피보나치", "fibonacci"]
        for keyword in algorithm_keywords:
            if keyword in title_lower:
                keywords.append(keyword)
    
    # rubric_json에서 algorithms 추출
    if spec.rubric_json and isinstance(spec.rubric_json, dict):
        code_quality = spec.rubric_json.get("code_quality", {})
        if isinstance(code_quality, dict):
            algorithms = code_quality.get("algorithms", [])
            if isinstance(algorithms, list):
                keywords.extend([alg.lower() for alg in algorithms])
    
    # content_md에서 일부 키워드 추출 (간단한 방식)
    if spec.content_md:
        content_lower = spec.content_md.lower()
        common_terms = ["재귀", "반복", "동적", "그리디", "이분", "탐색"]
        for term in common_terms:
            if term in content_lower:
                keywords.append(term)
    
    return list(set(keywords))  # 중복 제거

