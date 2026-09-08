"""pipeline.blocks — the BlockId assigner (pure function, no I/O).

Why this file exists: block boundaries are a pipeline-wide contract (the
Phase-C API CONTRACT), not a language detail, so the assignment rule lives
here once and every language's run_fold.py call shares it — no language
gets to reinterpret the 7-15 line law.

THE 7-15 LINE LAW (contract-locked):
  Accumulate consecutive statements into a block until the block's line
  span reaches >= 7 source lines; close the block there, at a statement
  boundary (blocks never split a statement). A block may never grow past
  15 source lines — UNLESS a single statement, entirely on its own,
  already exceeds 15 lines, in which case it stays whole as its own
  block (a statement is never split to satisfy the cap).

Concretely, for each next candidate statement added to the current block:
  - an EMPTY block accepts the first statement unconditionally, even if
    that statement alone spans more than 15 lines (rule above);
  - a NON-EMPTY block accepts the next statement only if the combined
    span would stay <= 15 lines; if accepting it would exceed 15, the
    current block closes as-is (short of 7 lines or not — the cap wins)
    and the candidate starts a new block;
  - after accepting a statement, if the block's span is now >= 7 lines,
    the block closes (statement boundary) and the next statement starts
    a new block;
  - whatever is left accumulated when statements run out becomes the
    final block, even if it never reached 7 lines (this is the "6
    one-line statements -> one block only if file ends" case: the block
    would have kept absorbing later statements had there been any).

Span of a statement or block covering source lines l0..l1 inclusive is
`l1 - l0 + 1` (a statement entirely on one line has span 1).
"""

MIN_BLOCK_LINES = 7
MAX_BLOCK_LINES = 15


def _span(l0, l1):
    return l1 - l0 + 1


def assign_blocks(stmts):
    """stmts: an iterable of statement descriptors, in file order (ascending
    seq, ascending line position). Each descriptor is a mapping (or object
    with attributes) exposing 'seq', 'l0', 'l1' — l0/l1 are that single
    statement's own first/last source line (1-based, inclusive).

    Returns a list of (block_id, [seq, seq, ...]) tuples, block_id formatted
    "b_001", "b_002", ... (1-indexed, zero-padded to at least 3 digits, and
    naturally widening past 999 blocks since it's plain int formatting).
    Every input seq appears in exactly one block, blocks appear in file
    order, and seqs stay in their original order inside a block.
    """
    def get(st, key):
        return st[key] if isinstance(st, dict) else getattr(st, key)

    closed_blocks = []   # list of lists of statement descriptors
    cur = []              # current open block's statements
    cur_l0 = None
    cur_l1 = None

    for st in stmts:
        l0, l1 = get(st, "l0"), get(st, "l1")

        if not cur:
            # An empty block always takes the next statement, even if that
            # statement alone is longer than MAX_BLOCK_LINES — a lone
            # oversized statement stays whole as its own block.
            cur = [st]
            cur_l0, cur_l1 = l0, l1
        else:
            candidate_l1 = max(cur_l1, l1)
            candidate_span = _span(cur_l0, candidate_l1)
            if candidate_span <= MAX_BLOCK_LINES:
                cur.append(st)
                cur_l1 = candidate_l1
            else:
                # Accepting this statement would blow the 15-line cap:
                # close the current block as-is (short of 7 or not — the
                # cap forces closure) and start a fresh block with it.
                closed_blocks.append(cur)
                cur = [st]
                cur_l0, cur_l1 = l0, l1

        if _span(cur_l0, cur_l1) >= MIN_BLOCK_LINES:
            closed_blocks.append(cur)
            cur = []
            cur_l0 = cur_l1 = None

    if cur:
        closed_blocks.append(cur)

    result = []
    for i, blk in enumerate(closed_blocks, start=1):
        block_id = f"b_{i:03d}"
        result.append((block_id, [get(st, "seq") for st in blk]))
    return result


# ---------------------------------------------------------------------
# exp_42 (2026-09-05): STEP BLOCKS — for a language whose source is already
# cut into steps by its own keywords (SAS: `data`/`proc` open a step,
# `run`/`quit` close it, `libname` stands alone). `cfg` is the spec's
# LANG["blocks"] = {"open": [functor, ...], "close": [functor, ...],
# "single": [functor, ...]}; a statement's functor is the name before the
# first "(" of its folded term text (or the whole text for a bare atom).

def term_functor(term_text):
    return term_text.split("(", 1)[0].strip().strip("'")


def assign_blocks_by_steps(stmts, folded, cfg):
    opens, closes, singles = set(cfg.get("open", [])), set(cfg.get("close", [])), set(cfg.get("single", []))
    blocks, cur = [], []
    for st in stmts:
        seq = st["seq"] if isinstance(st, dict) else st.seq
        f = term_functor(folded.get(seq, ""))
        if f in singles:
            if cur:
                blocks.append(cur)
                cur = []
            blocks.append([seq])
        elif f in opens:
            if cur:
                blocks.append(cur)
            cur = [seq]
        elif f in closes:
            cur.append(seq)
            blocks.append(cur)
            cur = []
        else:
            cur.append(seq)
    if cur:
        blocks.append(cur)
    return [(f"b_{i:03d}", seqs) for i, seqs in enumerate(blocks, start=1)]
