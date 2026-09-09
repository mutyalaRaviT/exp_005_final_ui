"""Run-order state machine. All state lives in plain dicts.

UNVISITED --push--> VISITING --children done--> DONE
An edge into a VISITING node is a back edge => cycle evidence.
Score = longest-path level of the SCC-condensed DAG (0 = run first).

All user-facing strings use data-flow notation: ``x -> y`` reads as
"data moves from x into y".
"""
from dataclasses import dataclass

UNVISITED, VISITING, DONE = "UNVISITED", "VISITING", "DONE"


@dataclass(frozen=True)
class Flow:
    """One file-level data flow: ``src -> dst`` carrying ``tables``."""
    src: str
    dst: str
    tables: tuple[str, ...]


@dataclass
class OrderResult:
    file: str
    score: int
    cyclic: bool
    cycle_id: str | None
    cycle_members: list[str]
    break_suggestion: tuple[str, str] | None
    reasoning: str


def _adjacency(flows, nodes):
    adj = {n: [] for n in nodes}
    for f in sorted(flows, key=lambda f: (f.src, f.dst)):
        adj.setdefault(f.src, []).append(f.dst)
        adj.setdefault(f.dst, [])
    return adj


def _back_edges(adj):
    """Iterative DFS over sorted roots; returns back edges found while the
    target was VISITING (the state machine's cycle evidence)."""
    state = {n: UNVISITED for n in adj}
    back = []
    for root in sorted(adj):
        if state[root] != UNVISITED:
            continue
        stack = [(root, iter(sorted(adj[root])))]
        state[root] = VISITING
        while stack:
            node, it = stack[-1]
            child = next(it, None)
            if child is None:
                state[node] = DONE
                stack.pop()
            elif state[child] == UNVISITED:
                state[child] = VISITING
                stack.append((child, iter(sorted(adj[child]))))
            elif state[child] == VISITING:
                back.append((node, child))
    return back


def _sccs(adj):
    """Iterative Tarjan; returns list of sorted member-lists, only real
    cycles (size>1 or self-loop)."""
    index, low, on, order = {}, {}, {}, []
    result, counter = [], [0]
    for root in sorted(adj):
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                index[node] = low[node] = counter[0]
                counter[0] += 1
                order.append(node)
                on[node] = True
            recurse = False
            children = sorted(adj[node])
            for ci in range(pi, len(children)):
                ch = children[ci]
                if ch not in index:
                    work[-1] = (node, ci + 1)
                    work.append((ch, 0))
                    recurse = True
                    break
                if on.get(ch):
                    low[node] = min(low[node], index[ch])
            if recurse:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                comp = []
                while True:
                    m = order.pop()
                    on[m] = False
                    comp.append(m)
                    if m == node:
                        break
                if len(comp) > 1 or node in adj[node]:
                    result.append(sorted(comp))
    return result


def compute_order(flows, nodes=None):
    """Score every file by run order. 0 = no flows in, it can run first."""
    all_nodes = sorted(set(nodes or []) |
                       {f.src for f in flows} | {f.dst for f in flows})
    adj = _adjacency(flows, all_nodes)
    back = _back_edges(adj)
    cycles = _sccs(adj)
    comp_of = {n: i for i, comp in enumerate(cycles) for n in comp}

    # condensed DAG: super-node per cycle, singleton otherwise
    def sid(n):
        return ("c", comp_of[n]) if n in comp_of else ("n", n)

    cadj, indeg = {}, {}
    for n in all_nodes:
        cadj.setdefault(sid(n), set())
        indeg.setdefault(sid(n), 0)
    for f in flows:
        a, b = sid(f.src), sid(f.dst)
        if a != b and b not in cadj[a]:
            cadj[a].add(b)
            indeg[b] += 1
    level, queue = {}, sorted([s for s, d in indeg.items() if d == 0])
    for s in queue:
        level[s] = 0
    while queue:
        s = queue.pop(0)
        for t in sorted(cadj[s]):
            level[t] = max(level.get(t, 0), level[s] + 1)
            indeg[t] -= 1
            if indeg[t] == 0:
                queue.append(t)
    inflows = {}
    for f in sorted(flows, key=lambda f: (f.dst, f.src)):
        inflows.setdefault(f.dst, []).append(f)
    results = {}
    for n in all_nodes:
        score = level[sid(n)]
        comp = cycles[comp_of[n]] if n in comp_of else []
        cyc_back = next(((a, b) for a, b in back
                         if a in comp and b in comp), None)
        parts = []
        if not inflows.get(n):
            parts.append(f"score {score}: no flows in - nothing feeds {n}; "
                         "it can run first" if score == 0 else
                         f"score {score}: no direct flows in")
        else:
            f0 = inflows[n][0]
            parts.append(f"score {score}: {f0.tables[0]} -> {n}, and "
                         f"{f0.tables[0]} is only ready at level "
                         f"{max(score - 1, 0)}")
        if comp:
            loop = " -> ".join(comp + [comp[0]])
            parts.append(f"in a loop: {loop}; data feeds back into where "
                         "it started")
            if cyc_back:
                parts.append(f"break the flow {cyc_back[0]} -> {cyc_back[1]} "
                             "to serialize")
        results[n] = OrderResult(
            file=n, score=score, cyclic=bool(comp),
            cycle_id=f"cycle_{comp_of[n]}" if comp else None,
            cycle_members=comp, break_suggestion=cyc_back,
            reasoning="; ".join(parts))
    return results
