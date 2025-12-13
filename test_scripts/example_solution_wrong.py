"""
잘못된 코드 예시 (테스트용)
이 코드는 테스트 케이스를 통과하지 못합니다.
"""
import sys

# 잘못된 구현: 단순히 첫 번째와 마지막 도시만 방문
N = int(sys.stdin.readline())
W = [list(map(int, sys.stdin.readline().split())) for _ in range(N)]

# 잘못된 로직: 모든 도시를 방문하지 않음
if N >= 2:
    result = W[0][N-1] if W[0][N-1] != 0 else 0
else:
    result = 0

print(result)



