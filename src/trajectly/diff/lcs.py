from __future__ import annotations


def lcs_pairs(left: list[str], right: list[str]) -> list[tuple[int, int]]:
    m = len(left)
    n = len(right)
    table = [[0 for _ in range(n + 1)] for _ in range(m + 1)]

    for i in range(m - 1, -1, -1):
        for j in range(n - 1, -1, -1):
            if left[i] == right[j]:
                table[i][j] = 1 + table[i + 1][j + 1]
            else:
                table[i][j] = max(table[i + 1][j], table[i][j + 1])

    pairs: list[tuple[int, int]] = []
    i = 0
    j = 0
    while i < m and j < n:
        if left[i] == right[j]:
            pairs.append((i, j))
            i += 1
            j += 1
        elif table[i + 1][j] >= table[i][j + 1]:
            i += 1
        else:
            j += 1

    return pairs
