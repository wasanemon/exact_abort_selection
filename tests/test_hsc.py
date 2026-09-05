#!/usr/bin/env python3
"""Independent finite check of Issue #1's HSC reduction (standard library only).

No selector/index code is imported. Graph edges come directly from R/W set
intersection; degree formulas are assertions against that graph, never an oracle.
The default grid exhausts ORDERED families, including empty and repeated sets.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import platform
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRID = [(u, m) for u in range(4) for m in range(1, 4)
                if u <= 2 or m <= 2]


def require(condition, message):
    # Unlike Python assert, these checks remain active with python -O.
    if not condition:
        raise AssertionError(message)


def original_hitting_set(a, b):
    return any(all(bool(s.intersection(t)) for t in b) for s in a)


def preprocess(a, b):
    union = set()
    for s in a:
        union.update(s)
    return any(not union.intersection(t) for t in b)


def construct(a, b):
    """Rows are (family, source/bridge, reads, writes), with distinct row IDs."""
    rows = []

    def add(family, index, keys):
        reads = frozenset(keys)
        writes = frozenset(list(keys))
        rows.append((family, index, reads, writes))

    x, y, h, l0, l1 = [('aux', name) for name in ('x', 'y', 'h', 'l0', 'l1')]
    for i, s in enumerate(a):
        add('X', i, [('input', key) for key in s] + [x])
    for j, s in enumerate(b):
        for _ in range(2):
            add('Y', j, [('input', key) for key in s] + [y])
    add('D', 0, [x, l0])
    add('D', 1, [x, l1])
    add('C', 0, [h, l0])
    add('C', 1, [h, l1])
    for j in range(3 * len(a) - 2):
        add('C', j + 2, [h])
    return rows


def direct_graph(rows):
    """Deliberately test every ordered pair using actual R and W sets."""
    return [{j for j, other in enumerate(rows)
             if i != j and row[2].intersection(other[3])}
            for i, row in enumerate(rows)]


def topology_edge(i, j, rows, a, b):
    """Independently predicted gadget topology, without constructed key sets."""
    if i == j:
        return False
    f, s = rows[i][:2]
    g, t = rows[j][:2]
    if f == g:
        return True  # X, Y, D and C each form a clique.
    if (f, g) == ('X', 'Y'):
        return bool(a[s].intersection(b[t]))
    if (f, g) == ('Y', 'X'):
        return bool(b[s].intersection(a[t]))
    if {f, g} == {'X', 'D'}:
        return True
    if {f, g} == {'C', 'D'}:
        return s == t and s in (0, 1)
    return False


def reachable(graph, start):
    seen, pending = {start}, [start]
    while pending:
        v = pending.pop()
        for w in graph[v]:
            if w not in seen:
                seen.add(w)
                pending.append(w)
    return seen


def verify_case(a, b, counts):
    m = len(a)
    truth = original_hitting_set(a, b)
    rejected = preprocess(a, b)
    counts['instances'] += 1
    counts['original_yes' if truth else 'original_no'] += 1
    counts['with_empty_set'] += int(any(not s for s in a + b))
    counts['with_duplicate_family_sets'] += int(len(set(a)) < m or len(set(b)) < m)
    counts['preprocess_checks'] += 1
    if rejected:
        require(not truth, 'preprocessing falsely rejected YES')
        counts['preprocess_no'] += 1
        return

    counts['constructed'] += 1
    counts['constructed_yes' if truth else 'constructed_no'] += 1
    rows = construct(a, b)
    n = len(rows)
    require(n == 6 * m + 2, 'vertex count')
    require(all(row[2] == row[3] for row in rows), 'complete RMW')
    accesses = sum(len(row[2]) + len(row[3]) for row in rows)
    expected_accesses = 2 * sum(map(len, a)) + 4 * sum(map(len, b)) + 12 * m + 12
    require(accesses == expected_accesses, 'total R+W access formula')
    counts['access_count_checks'] += 1
    counts['vertices_checked'] += n
    counts['rw_accesses_checked'] += accesses
    counts['maximum_constructed_arity'] = max(counts['maximum_constructed_arity'],
                                             max(len(row[2]) for row in rows))

    graph = direct_graph(rows)
    for i in range(n):
        for j in range(n):
            actual = j in graph[i]
            require(actual == topology_edge(i, j, rows, a, b), 'unexpected gadget edge')
            require(actual == (i in graph[j]), 'asymmetric edge')
            if i == j:
                require(not actual, 'self edge')
            counts['ordered_pair_checks'] += 1
    counts['directed_edges_checked'] += sum(map(len, graph))
    # Check forward and reverse reachability separately: together these imply a
    # single SCC without relying on the already-checked symmetry property.
    reverse = [{i for i in range(n) if j in graph[i]} for j in range(n)]
    require(len(reachable(graph, 0)) == n, 'not connected/forward reachable')
    require(len(reachable(reverse, 0)) == n, 'not one SCC/reverse reachable')
    counts['connectivity_checks'] += 1
    counts['scc_checks'] += 1

    degrees = [len(neighbors) for neighbors in graph]
    for i, row in enumerate(rows):
        family, source = row[:2]
        if family == 'X':
            hits = sum(bool(a[source].intersection(s)) for s in b)
            expected = m + 1 + 2 * hits
        elif family == 'Y':
            hits = sum(bool(s.intersection(b[source])) for s in a)
            expected = 2 * m - 1 + hits
        elif family == 'D':
            expected = m + 2
        else:
            expected = 3 * m if source in (0, 1) else 3 * m - 1
        require(degrees[i] == expected, 'degree formula')
        require(len(reverse[i]) == degrees[i], 'in-degree differs from out-degree')
        counts['degree_checks'] += 1

    # Enumerate EVERY admissible first candidate and second candidate among
    # degree ties, so this check does not assume a favorable ID tie-break.
    maximum = max(degrees)
    if truth:
        require(maximum == 3 * m + 1, 'YES maximum degree')
    else:
        require(maximum == 3 * m, 'NO maximum degree')
    first_choices = [i for i in range(n) if degrees[i] == maximum]
    for first in first_choices:
        require((rows[first][0] == 'X') == truth, 'top-1 answer')
        counts['top1_tie_choices_checked'] += 1
        second_degree = max(degrees[i] for i in range(n) if i != first)
        for second in range(n):
            if second == first or degrees[second] != second_degree:
                continue
            has_x = rows[first][0] == 'X' or rows[second][0] == 'X'
            require(has_x == truth, 'frozen top-2 answer')
            counts['top2_tie_choices_checked'] += 1

    # Also materialize the Issue's exact descending-ID order and its opposite.
    for reverse_ids in (False, True):
        ids = list(range(1, n + 1))
        if reverse_ids:
            ids.reverse()
        top2 = sorted(range(n), key=lambda i: (degrees[i], ids[i]), reverse=True)[:2]
        require((rows[top2[0]][0] == 'X') == truth, 'ID-ordered top-1')
        require(any(rows[i][0] == 'X' for i in top2) == truth, 'ID-ordered top-2')
        counts['id_order_checks'] += 1


def serializable_case(a, b):
    return {'A': [sorted(s) for s in a], 'B': [sorted(s) for s in b]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'experiments/eas/validation/hsc.json')
    parser.add_argument('--log', type=Path,
                        default=ROOT / 'experiments/eas/validation/hsc.log')
    parser.add_argument('--grid', help='override grid as universe:m,...')
    args = parser.parse_args()
    grid = DEFAULT_GRID if not args.grid else [tuple(map(int, v.split(':')))
                                              for v in args.grid.split(',')]
    require(all(len(v) == 2 and 0 <= v[0] <= 8 and 1 <= v[1] <= 8 for v in grid),
            'grid requires 0<=universe<=8 and 1<=m<=8')
    started = time.monotonic()
    report = {
        'status': 'running',
        'description': 'Finite exhaustive gadget checks; not a proof of HSC.',
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'python': platform.python_version(),
        'command': [sys.executable, *sys.argv],
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'enumeration': 'all ordered A/B families, empty and duplicate sets included',
        'grid': [],
    }
    total, log = Counter(), []
    current = None
    try:
        for universe, m in grid:
            sets = [frozenset(i for i in range(universe) if mask & (1 << i))
                    for mask in range(1 << universe)]
            counts = Counter()
            for family in product(sets, repeat=2 * m):
                a, b = family[:m], family[m:]
                current = {'universe': universe, 'm': m, **serializable_case(a, b)}
                verify_case(a, b, counts)
            expected = (1 << universe) ** (2 * m)
            require(counts['instances'] == expected, 'enumeration count')
            report['grid'].append({'universe': universe, 'm': m,
                                   'expected_instances': expected, **dict(counts)})
            old_max = total['maximum_constructed_arity']
            total.update(counts)
            total['maximum_constructed_arity'] = max(old_max,
                                                     counts['maximum_constructed_arity'])
            line = (f'U={universe} m={m}: {counts["instances"]} instances, '
                    f'{counts["preprocess_no"]} preprocessing NO, '
                    f'{counts["constructed"]} constructed; PASS')
            print(line, flush=True)
            log.append(line)
        require(total['constructed_yes'] > 0 and total['constructed_no'] > 0,
                'grid must include constructed YES and NO cases')
        require(total['preprocess_no'] > 0, 'grid must cover preprocessing NO')
        report['status'] = 'passed'
        log.append('PASS: every generated instance was checked; no counterexample.')
    except Exception as error:
        report['status'] = 'failed'
        report['counterexample'] = current
        report['error'] = repr(error)
        log.append(f'FAIL: {error!r}; counterexample saved in JSON')
    report['totals'] = dict(total)
    report['elapsed_seconds'] = time.monotonic() - started
    log.append(json.dumps(report['totals'], sort_keys=True))
    log.append(f'status={report["status"]}, elapsed_seconds={report["elapsed_seconds"]:.6f}')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    args.log.write_text('\n'.join(log) + '\n')
    print('\n'.join(log[-3:]), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
