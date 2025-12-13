"""
외판원 순회 (TSP) 문제 해결 코드
백준 2098번
"""
import sys

def tsp(current, visited):
    """
    외판원 순회 문제 해결 (비트마스킹 DP)
    
    Args:
        current: 현재 도시
        visited: 방문한 도시들의 비트마스크
        
    Returns:
        최소 비용
    """
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
            dp[current][visited] = min(
                dp[current][visited],
                tsp(i, visited | (1 << i)) + W[current][i]
            )
    
    return dp[current][visited]

# 입력 처리
N = int(sys.stdin.readline())
W = [list(map(int, sys.stdin.readline().split())) for _ in range(N)]

# DP 배열 초기화
dp = [[-1] * (1 << N) for _ in range(N)]

# 결과 출력
result = tsp(0, 1)
print(int(result))



