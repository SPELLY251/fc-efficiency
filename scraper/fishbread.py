"""붕어빵 속 SSS — 49칸 판 뽑기의 참여권 1장당 기대 BP.

규칙(사용자 확인):
- 뽑은 칸은 판에서 빠진다(비복원).
- 판 리셋은 언제든 공짜로 할 수 있다.
- 각 보상은 아이템 또는 프리미엄 코인으로 받을 수 있다 → 더 이득인 쪽을 고른다고 가정.
- 7번 참여마다 S등급 보상 1개 추가.

두 가지 기준을 계산한다.
1) 끝까지 뽑기: 리셋하지 않고 49칸을 다 뽑음 → 1장당 = 판 평균
2) 최적 리셋: 남은 판이 불리해지면 바로 리셋 → 1장당 장기 평균의 최댓값
   (상태 = 등급별 남은 칸 수. 동적계획법 + 이분 탐색으로 정확히 계산)
"""
from functools import lru_cache


def board_average(counts, values):
    n = sum(counts)
    return sum(c * v for c, v in zip(counts, values)) / n


def optimal_per_draw(counts, values, tol=1e-6):
    """리셋이 공짜일 때 참여 1회당 얻을 수 있는 최대 장기 평균 g*.

    g를 가정하면, 각 상태에서 '계속 뽑기'의 가치 D(s)=Σ p_i (v_i − g + V(s−e_i)),
    V(s)=max(0, D(s)) (0 = 리셋). 처음 판에서 D(full)=0 이 되는 g가 답이다.
    """
    full = tuple(counts)

    def solve(g):
        @lru_cache(maxsize=None)
        def V(state):
            return max(0.0, D(state))

        @lru_cache(maxsize=None)
        def D(state):
            n = sum(state)
            if n == 0:
                return float("-inf")   # 빈 판은 리셋할 수밖에 없음
            total = 0.0
            for i, c in enumerate(state):
                if c:
                    nxt = state[:i] + (c - 1,) + state[i + 1:]
                    total += c / n * (values[i] - g + V(nxt))
            return total

        return D(full), V, D

    lo, hi = min(values), max(values)
    while hi - lo > tol * max(1.0, abs(hi)):
        mid = (lo + hi) / 2
        d, _, _ = solve(mid)
        if d > 0:
            lo = mid
        else:
            hi = mid
    g = (lo + hi) / 2
    _, V, D = solve(g)
    return g, (lambda state: D(state) > 0)   # True = 계속 뽑기, False = 리셋


def describe_policy(counts, names, keep_drawing):
    """최적 전략을 쉬운 말로: 좋은 칸이 하나씩 빠졌을 때 리셋하는지 확인."""
    full = tuple(counts)
    lines = []
    for i, name in enumerate(names):
        if full[i] == 0:
            continue
        after = full[:i] + (full[i] - 1,) + full[i + 1:]
        lines.append(f"처음에 {name}이(가) 나오면 → {'계속 뽑기' if keep_drawing(after) else '바로 리셋'}")
    return lines


def simulate_draws_per_board(counts, keep_drawing, trials=20000, seed=1):
    """최적 전략으로 판 하나당 평균 몇 번 뽑고 리셋하는지(설명용)."""
    import random
    rnd = random.Random(seed)
    total = 0
    for _ in range(trials):
        state = list(counts)
        draws = 0
        while True:
            n = sum(state)
            r = rnd.randrange(n)
            for i, c in enumerate(state):
                if r < c:
                    state[i] -= 1
                    break
                r -= c
            draws += 1
            if sum(state) == 0 or not keep_drawing(tuple(state)):
                break
        total += draws
    return total / trials
