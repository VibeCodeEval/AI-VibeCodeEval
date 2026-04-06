# setup_submit_test_data 기본 스펙(spec_id=10, 외판원) 제출용 샘플 코드 (백준 2098 스타일)
import sys

input = sys.stdin.readline


def tsp(current, visited):
    if visited == (1 << N) - 1:
        if W[current][0] != 0:
            return W[current][0]
        return float("inf")

    if dp[current][visited] != -1:
        return dp[current][visited]

    dp[current][visited] = float("inf")
    for i in range(N):
        if visited & (1 << i) == 0 and W[current][i] != 0:
            dp[current][visited] = min(
                dp[current][visited],
                tsp(i, visited | (1 << i)) + W[current][i],
            )

    return dp[current][visited]


N = int(input())
W = [list(map(int, input().split())) for _ in range(N)]

dp = [[-1] * (1 << N) for _ in range(N)]
result = tsp(0, 1)
print(result if result != float("inf") else -1)
