"""
문제 정보 관리 모듈
DB `problem_specs` + `checker_json` 우선, 비어 있거나 조회 실패 시 하드코딩(더미) 폴백.

[데이터 구조]
- HARDCODED_PROBLEM_SPEC: 로컬 더미/레거시 스펙 (Judge0 TC, 스마트 게이트 스위트 등)
- DB: `docs/AI_PROBLEM_SPEC_USAGE.md` — checker_json.test_cases, reference_code, limits

[더미 사용 시]
- logger.warning 으로 사유(spec_id, cause)를 남김.
"""

import copy
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _smart_gate_2026_test_suite_code() -> str:
    """
    스마트 게이트 2026 Judge0 검증용 테스트 스크립트.
    사용자 v2_code 끝에 붙여 실행 시, 통과하면 stdout에 "ALL_TESTS_PASSED" 출력.

    검증 내용:
    1. 보안 등급 HIGH: threat_level="HIGH"일 때 모든 승객 SECURITY_CHECK
    2. 수하물 과금: 비즈니스 30kg/이코노미 20kg 초과 시 CHARGE_FEE
    3. 누적 과금 페널티: 동일 항공편 4번째 과금 승객부터 허용 무게 -5kg
    """
    return r'''
# === 스마트 게이트 2026 검증 스위트 (Judge0) ===
def _sg_run_tests():
    class Ctx:
        pass
    class Pax:
        pass
    overcharge = {}
    try:
        rules = [SecurityRule(), PassportRule(), FlightStatusRule(), LuggageRule(overcharge)]
        gm = GateManager(rules)
        ref = 99999999  # 만료 이후 날짜
        ctx = Ctx()
        ctx.reference_date = ref
        ctx.flight_id = "F001"
        # 1. HIGH -> SECURITY_CHECK
        ctx.threat_level = "HIGH"
        p = Pax()
        p.passport_expiry = ref + 1
        p.flight_status = "BOARDING"
        p.seat_class = "ECONOMY"
        p.luggage_kg = 10
        p.flight_id = "F001"
        r = gm.process(p, ctx)
        assert r == "SECURITY_CHECK", "HIGH threat must return SECURITY_CHECK, got %r" % r
        # 2. 수하물: 비즈니스 31kg -> CHARGE_FEE
        ctx.threat_level = "LOW"
        p2 = Pax()
        p2.passport_expiry = ref + 1
        p2.flight_status = "BOARDING"
        p2.seat_class = "BUSINESS"
        p2.luggage_kg = 31
        p2.flight_id = "F002"
        r2 = gm.process(p2, ctx)
        assert r2 == "CHARGE_FEE", "BUSINESS 31kg must return CHARGE_FEE, got %r" % r2
        # 이코노미 21kg -> CHARGE_FEE
        p3 = Pax()
        p3.passport_expiry = ref + 1
        p3.flight_status = "BOARDING"
        p3.seat_class = "ECONOMY"
        p3.luggage_kg = 21
        p3.flight_id = "F003"
        r3 = gm.process(p3, ctx)
        assert r3 == "CHARGE_FEE", "ECONOMY 21kg must return CHARGE_FEE, got %r" % r3
        # 3. 누적 과금: F004에서 3명 CHARGE_FEE 후 4번째는 16kg(기준 15kg) -> CHARGE_FEE
        fid = "F004"
        for _ in range(3):
            px = Pax()
            px.passport_expiry = ref + 1
            px.flight_status = "BOARDING"
            px.seat_class = "ECONOMY"
            px.luggage_kg = 21
            px.flight_id = fid
            gm.process(px, ctx)
        p4 = Pax()
        p4.passport_expiry = ref + 1
        p4.flight_status = "BOARDING"
        p4.seat_class = "ECONOMY"
        p4.luggage_kg = 16
        p4.flight_id = fid
        r4 = gm.process(p4, ctx)
        assert r4 == "CHARGE_FEE", "4th passenger 16kg (limit 15) must return CHARGE_FEE, got %r" % r4
        print("ALL_TESTS_PASSED")
    except AssertionError as e:
        print("ASSERTION_FAILED:", str(e))
        raise
_sg_run_tests()
'''


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
            "output_format": "첫째 줄에 순회에 필요한 최소 비용을 출력.",
        },
        # 2. 제약 조건 (AI가 알고리즘을 판단하고, 사용자의 비현실적 요청을 거르는 기준)
        "constraints": {
            "time_limit_sec": 1.0,
            "memory_limit_mb": 128,
            "variable_ranges": {
                "N": "2 <= N <= 16",
                "Cost": "0 <= W[i][j] <= 1,000,000",
            },
            # AI가 이 문제를 '비트마스킹 DP'라고 확신하는 결정적 근거
            "logic_reasoning": "N이 최대 16이므로, O(N!)의 완전 탐색(약 20조 연산)은 시간 초과가 발생함. 따라서 O(N^2 * 2^N) 시간 복잡도를 가지는 '비트마스킹을 이용한 DP'를 사용해야 함.",
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
                "step_4_base_case": "모든 도시를 방문했을 때(`visited == (1<<N) - 1`), 현재 도시에서 출발 도시(0)로 돌아가는 길이 있는지 확인하고 비용을 반환해야 합니다.",
            },
            # 자주 틀리는 실수 (디버깅 요청 시 체크 포인트)
            "common_pitfalls": [
                "갈 수 없는 길(W[i][j] == 0)인 경우를 체크하지 않음.",
                "DP 배열을 0으로 초기화하면 '방문 안 함'과 '비용 0'이 구분되지 않음. -1이나 INF로 초기화해야 함.",
                "마지막 도시에서 시작 도시로 돌아올 수 없는 경우를 예외 처리하지 않음 (INF 반환 필요).",
            ],
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
                "description": "기본 케이스: 4개 도시",
            },
            {
                "input": "3\n0 1 2\n1 0 3\n2 3 0\n",
                "expected": "6",
                "description": "최소 케이스: 3개 도시",
            },
            {
                "input": "2\n0 10\n10 0\n",
                "expected": "20",
                "description": "최소 케이스: 2개 도시",
            },
            {
                "input": "5\n0 1 2 3 4\n1 0 5 6 7\n2 5 0 8 9\n3 6 8 0 10\n4 7 9 10 0\n",
                "expected": "21",
                "description": "5개 도시 케이스",
            },
            {
                "input": "6\n0 1 2 3 4 5\n1 0 6 7 8 9\n2 6 0 10 11 12\n3 7 10 0 13 14\n4 8 11 13 0 15\n5 9 12 14 15 0\n",
                "expected": "27",
                "description": "6개 도시 케이스",
            },
            {
                "input": "4\n0 1 100 100\n1 0 1 100\n100 1 0 1\n1 100 1 0\n",
                "expected": "4",
                "description": "비대칭 비용 행렬 (수정됨)",
            },
            {
                "input": "4\n0 0 1 1\n0 0 1 1\n1 1 0 0\n1 1 0 0\n",
                "expected": "4",
                "description": "갈 수 없는 경로 포함 (0 처리)",
            },
            {
                "input": "3\n0 5 10\n5 0 15\n10 15 0\n",
                "expected": "30",
                "description": "대칭 비용 행렬",
            },
            {
                "input": "4\n0 2 9 10\n1 0 6 4\n15 7 0 8\n6 3 12 0\n",
                "expected": "21",
                "description": "복잡한 비용 행렬",
            },
            {
                "input": "5\n0 3 4 2 7\n3 0 4 6 3\n4 4 0 5 8\n2 6 5 0 6\n7 3 8 6 0\n",
                "expected": "19",
                "description": "대규모 케이스: 5개 도시",
            },
        ],
        # 6. 채점 기준 (Rubric)
        "rubric": {
            "correctness": {
                "weight": 0.5,
                "description": "정확성 점수 (테스트 케이스 통과율)",
                "criteria": {
                    "all_passed": {
                        "score": 100,
                        "description": "모든 테스트 케이스 통과",
                    },
                    "partial_passed": {
                        "score_formula": "(통과한_테스트_케이스_수 / 전체_테스트_케이스_수) * 100",
                        "description": "일부 테스트 케이스 통과",
                    },
                    "none_passed": {
                        "score": 0,
                        "description": "테스트 케이스 통과 실패",
                    },
                },
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
                                "description": "1초 이내: 100점",
                            },
                            "exceeded": {
                                "score_formula": "max(0, 100 * (1 - execution_time / time_limit))",
                                "description": "1초 초과 시 감점 (초과 시간에 비례)",
                            },
                        },
                    },
                    "memory_score": {
                        "weight": 0.4,
                        "description": "메모리 사용량 점수",
                        "limit_mb": 128,
                        "scoring": {
                            "within_limit": {
                                "score": 100,
                                "description": "128MB 이내: 100점",
                            },
                            "exceeded": {
                                "score_formula": "max(0, 100 * (1 - memory_used / memory_limit))",
                                "description": "128MB 초과 시 감점 (초과 메모리에 비례)",
                            },
                        },
                    },
                },
            },
            "code_quality": {
                "weight": 0.25,
                "description": "코드 품질 점수 (알고리즘 효율성, 가독성)",
                "criteria": {
                    "algorithm_efficiency": {
                        "weight": 0.6,
                        "description": "알고리즘 효율성 (비트마스킹 DP 사용: 100점, 완전 탐색: 50점, 그 외: 0점)",
                    },
                    "code_readability": {
                        "weight": 0.4,
                        "description": "코드 가독성 (변수명, 주석, 구조)",
                    },
                },
            },
        },
        # 7. 가드레일용 키워드 (하위 호환성 및 Intent Analyzer에서 사용)
        "keywords": [
            "외판원",
            "tsp",
            "traveling salesman",
            "dp[현재도시][방문도시]",
            "방문 상태",
        ],
    },
    2: {  # spec_id = 2 (외판원 순회 - 테스트용)
        # 1. 기본 정보
        "basic_info": {
            "problem_id": "2",
            "title": "외판원 순회",
            "description_summary": "1번 도시에서 출발하여 모든 도시를 단 한 번씩 거쳐 다시 1번 도시로 돌아오는 최소 비용의 경로를 구하는 문제.",
            "input_format": "첫째 줄에 도시의 수 N (2 ≤ N ≤ 16). 다음 N개의 줄에 비용 행렬 W가 주어짐. W[i][j]는 도시 i에서 j로 가기 위한 비용 (0은 갈 수 없음).",
            "output_format": "첫째 줄에 순회에 필요한 최소 비용을 출력.",
        },
        # 2. 제약 조건
        "constraints": {
            "time_limit_sec": 1.0,
            "memory_limit_mb": 128,
            "variable_ranges": {
                "N": "2 <= N <= 16",
                "Cost": "0 <= W[i][j] <= 1,000,000",
            },
            "logic_reasoning": "N이 최대 16이므로, O(N!)의 완전 탐색(약 20조 연산)은 시간 초과가 발생함. 따라서 O(N^2 * 2^N) 시간 복잡도를 가지는 '비트마스킹을 이용한 DP'를 사용해야 함.",
        },
        # 3. AI 튜터링 가이드
        "ai_guide": {
            "key_algorithms": ["Dynamic Programming", "Bitmasking", "DFS", "TSP"],
            "solution_architecture": "Top-down DFS with Memoization",
            "hint_roadmap": {
                "step_1_concept": "N이 작다는 점(16)에 주목하세요. 방문한 도시들의 상태를 효율적으로 저장할 방법이 필요합니다. 배열보다는 '비트(Bit)'를 사용해보면 어떨까요?",
                "step_2_state": "상태를 `dp[current_city][visited_bitmask]`로 정의해보세요. `visited_bitmask`의 i번째 비트가 1이면 i번 도시를 방문했다는 뜻입니다.",
                "step_3_transition": "점화식: `FindPath(curr, visited) = min(W[curr][next] + FindPath(next, visited | (1<<next)))` (단, next는 아직 방문하지 않은 도시)",
                "step_4_base_case": "모든 도시를 방문했을 때(`visited == (1<<N) - 1`), 현재 도시에서 출발 도시(0)로 돌아가는 길이 있는지 확인하고 비용을 반환해야 합니다.",
            },
            "common_pitfalls": [
                "갈 수 없는 길(W[i][j] == 0)인 경우를 체크하지 않음.",
                "DP 배열을 0으로 초기화하면 '방문 안 함'과 '비용 0'이 구분되지 않음. -1이나 INF로 초기화해야 함.",
                "마지막 도시에서 시작 도시로 돌아올 수 없는 경우를 예외 처리하지 않음 (INF 반환 필요).",
            ],
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
                "description": "기본 케이스: 4개 도시 (외판원 문제)",
            }
        ],
        # 6. 채점 기준 (기본값)
        "rubric": {
            "correctness": {"weight": 0.5, "description": "정확성 점수"},
            "performance": {"weight": 0.25, "description": "성능 점수"},
            "code_quality": {"weight": 0.25, "description": "코드 품질 점수"},
        },
        # 7. 가드레일용 키워드
        "keywords": [
            "외판원",
            "tsp",
            "traveling salesman",
            "DP",
            "비트마스킹",
            "bitmasking",
        ],
    },
    20: {  # spec_id = 20 (스마트 게이트 2026)
        "basic_info": {
            "problem_id": "20",
            "title": "스마트 게이트 2026",
            "description_summary": "공항 게이트 보안·수하물 과금 로직을 Phase 1(기본)/Phase 2(긴급 정책)로 구현. Rule 인터페이스 분리, 전략 패턴, 상속 구조 평가.",
            "input_format": "승객 정보(여권 만료일, 항공편 상태, 수하물 무게 등) 및 정책 파라미터(threat_level, 누적 과금 등).",
            "output_format": "REJECT / WAIT / CHARGE_FEE 후 통과 / 통과 등 게이트 처리 결과.",
        },
        "constraints": {
            "time_limit_sec": 2.0,
            "memory_limit_mb": 256,
            "variable_ranges": {},
            "logic_reasoning": "Phase 1: 여권 만료(2026-02-04 이전 REJECT), 항공편 상태(BOARDING만 통과, DELAYED=WAIT, 그 외 REJECT), 수하물(이코노미 20kg/비즈니스 30kg 초과 시 CHARGE_FEE 후 통과). Phase 2: threat_level==HIGH이면 SECURITY_CHECK, 누적 과금 3명 발생 시 해당 항공편 4번째부터 허용 무게 -5kg.",
        },
        "ai_guide": {
            "key_algorithms": ["Strategy Pattern", "Rule Interface", "Inheritance"],
            "solution_architecture": "GateManager + BaseRule/SecurityRule, 전략 패턴 유지",
            "hint_roadmap": {},
            "common_pitfalls": [
                "Rule 인터페이스 없이 하드코딩",
                "SecurityRule이 BaseRule을 상속하지 않음",
                "GateManager에서 전략 패턴을 깨고 직접 분기 처리",
            ],
        },
        "solution_code": None,
        "test_cases": [],
        # Judge0 검증: v2_code 끝에 붙여 실행, stdout에 "ALL_TESTS_PASSED" 출력 시 100점
        "test_suite_code": _smart_gate_2026_test_suite_code(),
        "rubric": {
            "correctness": {"weight": 0.4, "description": "Phase 1/2 규칙 정확성"},
            "performance": {"weight": 0.1, "description": "실행 성능"},
            "code_quality": {"weight": 0.5, "description": "Rule 분리, 상속, 전략 패턴"},
        },
        "keywords": [
            "GateManager",
            "BaseRule",
            "SecurityRule",
            "전략 패턴",
            "규칙 인터페이스",
            "상속",
        ],
        "evaluation_points": [
            "Rule 인터페이스 분리",
            "SecurityRule이 BaseRule 상속",
            "GateManager 전략 패턴 유지",
        ],
        "phase_summary": {
            "phase_1": "기본 보안 통과 및 수하물 과금. 여권 만료(2026-02-04 이전 REJECT), 항공편(BOARDING만 통과, DELAYED=WAIT), 수하물(이코노미 20kg/비즈니스 30kg 초과 시 CHARGE_FEE 후 통과).",
            "phase_2": "긴급 보안 등급(HIGH) 시 SECURITY_CHECK, 누적 과금 3명 발생 시 해당 항공편 4번째부터 허용 무게 -5kg.",
        },
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

# 평가 LLM 컨텍스트 한도 (토큰 폭주 방지; 필요 시 호출부에서 max_chars 오버라이드)
DEFAULT_EVAL_PROBLEM_MAX_CHARS = 24_000


def problem_statement_for_evaluation(
    problem_context: Optional[Dict[str, Any]],
    *,
    max_chars: int = DEFAULT_EVAL_PROBLEM_MAX_CHARS,
) -> str:
    """
    평가(N4 턴 평가, N7 코드 리뷰, N8 토론 등)에 넣을 문제 본문.

    우선순위:
    1. ``content_md`` — DB ``problem_specs.content_md`` 가 ``get_problem_info`` 로 들어온 값
    2. ``basic_info.description_summary``
    3. ``basic_info.description``
    4. 제목만 (본문 없음 표시)
    """
    if not problem_context:
        return "설명 없음"

    raw = (problem_context.get("content_md") or "").strip()
    if raw:
        if len(raw) > max_chars:
            return (
                raw[:max_chars].rstrip()
                + "\n\n[… 문제 본문이 길어 일부만 표시했습니다 …]"
            )
        return raw

    basic = problem_context.get("basic_info") or {}
    summary = (basic.get("description_summary") or "").strip()
    if summary:
        return summary

    desc = (basic.get("description") or "").strip()
    if desc:
        return desc

    title = (basic.get("title") or "").strip()
    if title:
        return f"(상세 본문 없음) 문제: {title}"

    return "설명 없음"


def _normalize_spec_id(spec_id: Optional[int]) -> int:
    if spec_id is None:
        logger.warning("[Problem Info] spec_id가 None입니다. 기본값(10)으로 fallback합니다.")
        return 10
    if spec_id == 11 and 20 in HARDCODED_PROBLEM_SPEC:
        return 20
    return int(spec_id)


def _default_unknown_spec_context(spec_id: int) -> Dict[str, Any]:
    """HARDCODED에 없는 spec_id용 최소 더미(샘플 TSP TC 1건)."""
    return {
        "basic_info": {
            "problem_id": str(spec_id),
            "title": "",
            "description_summary": None,
            "input_format": None,
            "output_format": None,
        },
        "constraints": {
            "time_limit_sec": 1.0,
            "memory_limit_mb": 128,
            "variable_ranges": {},
            "logic_reasoning": None,
        },
        "ai_guide": {
            "key_algorithms": [],
            "solution_architecture": None,
            "hint_roadmap": {},
            "common_pitfalls": [],
        },
        "solution_code": None,
        "keywords": [],
        "test_cases": [
            {
                "input": "4\n0 10 15 20\n5 0 9 10\n6 13 0 12\n8 8 9 0\n",
                "expected": "35",
                "description": "기본 케이스: 4개 도시 (외판원 문제)",
            }
        ],
    }


def _merge_checker_json_into_context(
    context: Dict[str, Any], checker: Optional[Dict[str, Any]]
) -> None:
    """
    DB checker_json → problem_context (docs/AI_PROBLEM_SPEC_USAGE.md).
    - test_cases: expected_output 또는 expected → Judge0용 expected
    - reference_code → solution_code
    - limits.timeMs / memoryMb → constraints (rubric 값이 비어 있을 때만)
    - 선택: test_suite_code (스마트 게이트용 인라인 스위트)
    """
    if not checker or not isinstance(checker, dict):
        return

    if checker.get("type") is not None:
        context["checker_type"] = checker["type"]

    limits = checker.get("limits")
    if isinstance(limits, dict):
        constraints = context.setdefault(
            "constraints",
            {
                "time_limit_sec": None,
                "memory_limit_mb": None,
                "variable_ranges": {},
                "logic_reasoning": None,
            },
        )
        if limits.get("timeMs") is not None and constraints.get("time_limit_sec") is None:
            try:
                constraints["time_limit_sec"] = float(limits["timeMs"]) / 1000.0
            except (TypeError, ValueError):
                pass
        if limits.get("memoryMb") is not None and constraints.get("memory_limit_mb") is None:
            try:
                constraints["memory_limit_mb"] = int(limits["memoryMb"])
            except (TypeError, ValueError):
                pass

    raw_tcs = checker.get("test_cases")
    if isinstance(raw_tcs, list) and raw_tcs:
        normalized: List[Dict[str, Any]] = []
        for i, raw in enumerate(raw_tcs):
            if not isinstance(raw, dict):
                continue
            exp = raw.get("expected_output")
            if exp is None:
                exp = raw.get("expected")
            normalized.append(
                {
                    "input": ""
                    if raw.get("input") is None
                    else str(raw.get("input")),
                    "expected": "" if exp is None else str(exp),
                    "description": raw.get("description")
                    or str(raw.get("id") or f"TC{i + 1}"),
                }
            )
        if normalized:
            context["test_cases"] = normalized

    ref = checker.get("reference_code")
    if isinstance(ref, str) and ref.strip():
        context["solution_code"] = ref
        context["reference_code"] = ref

    tscode = checker.get("test_suite_code")
    if isinstance(tscode, str) and tscode.strip():
        context["test_suite_code"] = tscode


def _build_problem_context_from_db_row(spec: Any, spec_id: int) -> Dict[str, Any]:
    problem = getattr(spec, "problem", None)

    basic_info = {
        "problem_id": str(problem.id) if problem else str(getattr(spec, "problem_id", "")),
        "title": (problem.title or "") if problem else "",
        "description_summary": (spec.content_md[:200] if spec.content_md else None),
        "input_format": None,
        "output_format": None,
    }

    constraints = {
        "time_limit_sec": None,
        "memory_limit_mb": None,
        "variable_ranges": {},
        "logic_reasoning": None,
    }
    if spec.rubric_json and isinstance(spec.rubric_json, dict):
        performance = spec.rubric_json.get("performance", {})
        if isinstance(performance, dict):
            constraints["time_limit_sec"] = performance.get("time_limit_sec")
            constraints["memory_limit_mb"] = performance.get("memory_limit_mb")

    ai_guide = {
        "key_algorithms": [],
        "solution_architecture": None,
        "hint_roadmap": {},
        "common_pitfalls": [],
    }
    if spec.rubric_json and isinstance(spec.rubric_json, dict):
        code_quality = spec.rubric_json.get("code_quality", {})
        if isinstance(code_quality, dict):
            ai_guide["key_algorithms"] = code_quality.get("algorithms", [])

    keywords = _extract_keywords_from_problem_spec(spec)

    return {
        "basic_info": basic_info,
        "constraints": constraints,
        "ai_guide": ai_guide,
        "solution_code": None,
        "keywords": keywords,
        "content_md": spec.content_md,
        "problem_spec_id": spec_id,
    }


def _fill_eval_dummy_gaps(spec_id: int, context: Dict[str, Any], db_had_row: bool) -> None:
    """Judge0에 필요한 test_cases / 스마트 게이트 test_suite_code가 비면 내장 스펙으로 보강."""
    from app.core.config import settings

    smart = spec_id in settings.SMART_GATE_SPEC_IDS
    if smart:
        if (context.get("test_suite_code") or "").strip():
            return
        dummy = HARDCODED_PROBLEM_SPEC.get(spec_id)
        if dummy and dummy.get("test_suite_code"):
            context["test_suite_code"] = dummy["test_suite_code"]
            logger.warning(
                "[Problem Info] 스마트 게이트용 test_suite_code가 없어 내장(하드코딩) 스위트로 보강합니다. "
                "spec_id=%s db_row=%s",
                spec_id,
                db_had_row,
            )
        return

    tcs = context.get("test_cases") or []
    if tcs:
        return

    dummy = HARDCODED_PROBLEM_SPEC.get(spec_id)
    if dummy and dummy.get("test_cases"):
        context["test_cases"] = copy.deepcopy(dummy["test_cases"])
        logger.warning(
            "[Problem Info] Judge0용 test_cases가 비어 있어 내장(하드코딩) TC로 보강합니다. "
            "spec_id=%s db_row=%s",
            spec_id,
            db_had_row,
        )
        return

    context["test_cases"] = copy.deepcopy(
        _default_unknown_spec_context(spec_id)["test_cases"]
    )
    logger.warning(
        "[Problem Info] test_cases를 확보할 수 없어 기본 TSP 샘플 1건으로 보강합니다. spec_id=%s db_row=%s",
        spec_id,
        db_had_row,
    )


def _dummy_context_no_db(spec_id: int, reason: str) -> Dict[str, Any]:
    """DB 세션 없음·조회 실패·행 없음 등 — 내장 HARDCODED 또는 최소 더미."""
    if spec_id in HARDCODED_PROBLEM_SPEC:
        ctx = copy.deepcopy(HARDCODED_PROBLEM_SPEC[spec_id])
        if reason in ("sync_no_db", "no_db_session"):
            logger.info(
                "[Problem Info] 내장 스펙 사용 (DB 미연결). spec_id=%s reason=%s",
                spec_id,
                reason,
            )
        else:
            logger.warning(
                "[Problem Info] 더미/내장 스펙으로 폴백합니다. spec_id=%s reason=%s source=HARDCODED",
                spec_id,
                reason,
            )
        return ctx
    ctx = _default_unknown_spec_context(spec_id)
    logger.warning(
        "[Problem Info] 더미 스펙 사용 (알 수 없는 spec_id). spec_id=%s reason=%s source=default_tsp_sample",
        spec_id,
        reason,
    )
    return ctx


def get_problem_info_sync(spec_id: int) -> Dict[str, Any]:
    """
    동기 로드: DB 연결 없이 내장 HARDCODED 또는 최소 더미만 사용.

    DB 기반 스펙이 필요하면 get_problem_info(spec_id, db) 또는 EvalService 초기화 경로를 사용합니다.
    """
    sid = _normalize_spec_id(spec_id)
    return _dummy_context_no_db(sid, "sync_no_db")


async def get_problem_info(spec_id: int, db: Optional[Any] = None) -> Dict[str, Any]:
    """
    문제 정보 로드 (비동기).

    Args:
        spec_id: ``problem_specs.spec_id`` (PK). 제출/세션의 specId와 동일.
            ``problems.id``(문제 본체)와는 다른 값입니다.

    - DB(`problem_specs` + `checker_json`) 우선 — `docs/AI_PROBLEM_SPEC_USAGE.md` 스키마
    - 조회 실패·행 없음·checker 비어 Judge0 불가 시 내장 스펙으로 보강 (warning 로그)
    """
    sid = _normalize_spec_id(spec_id)

    if db:
        try:
            from app.infrastructure.repositories.exam_repository import \
                ExamRepository

            exam_repo = ExamRepository(db)
            spec_row = await exam_repo.get_problem_spec_with_problem(sid)

            if spec_row:
                ctx = _build_problem_context_from_db_row(spec_row, sid)
                _merge_checker_json_into_context(ctx, spec_row.checker_json)
                _fill_eval_dummy_gaps(sid, ctx, db_had_row=True)
                if not getattr(spec_row, "problem", None):
                    logger.warning(
                        "[Problem Info] problem_spec은 있으나 연결된 problem 행이 없습니다. "
                        "spec_id=%s problem_id=%s — checker_json·content_md만 반영합니다.",
                        sid,
                        getattr(spec_row, "problem_id", None),
                    )
                logger.info(
                    "[Problem Info] DB 기반 problem_context 완료 spec_id=%s checker=%s tc_count=%s",
                    sid,
                    bool(spec_row.checker_json),
                    len(ctx.get("test_cases") or []),
                )
                return ctx

            logger.warning(
                "[Problem Info] DB에 problem_spec 행이 없어 내장/더미로 폴백합니다. spec_id=%s",
                sid,
            )
            return _dummy_context_no_db(sid, "db_spec_missing")

        except Exception as e:
            logger.warning(
                "[Problem Info] DB 조회 중 예외 — 내장/더미 폴백합니다. spec_id=%s error=%s",
                sid,
                e,
            )
            return _dummy_context_no_db(sid, f"db_error:{e}")

    return _dummy_context_no_db(sid, "no_db_session")


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
        algorithm_keywords = [
            "tsp",
            "외판원",
            "dp",
            "그래프",
            "트리",
            "정렬",
            "피보나치",
            "fibonacci",
        ]
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
