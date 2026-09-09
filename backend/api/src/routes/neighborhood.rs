//! `neighborhood` — `GET /api/neighborhood?file=&table=&up=&down=`.
//!
//! **Why this exists.** UI1's canvas: given a seed file (or table), walk `up` hops against
//! the data flow and `down` hops with it, and hand back a file-level graph plus a run
//! order and a plain-English story. `:8000` (`service.py::Service.neighborhood`) computes
//! this from its `mentions` index and an in-memory parse cache — not from a `lineage`
//! table — so this module does not copy its SQL, it matches its *answer*: same BFS shape,
//! same `project_edges` roll-up, same `orderer.py::compute_order` (longest-path level of
//! the SCC-condensed DAG, iterative Tarjan for cycles), same story sentences, ported
//! statement-for-statement so the two engines' output strings line up byte for byte.
//!
//! **Where the file-level facts come from.** This store's `edges` table is per-block:
//! `(src_table, dst_table, fileid, block_id)` means "this block in `fileid` read
//! `src_table` and wrote `dst_table`" (`lineage_blocks::edges_per_block`, `ds_lineage(OUT,
//! IN)` runs IN -> OUT). Rolling that up to "what does this file read / write" is:
//! `reads(fileid)` = distinct `src_table` where `edges.fileid = fileid`; `writes(fileid)` =
//! distinct `dst_table` there, unioned with `blocks.name` (every block's write target,
//! including one whose read side failed to fold) so a write is never lost just because its
//! *source* didn't parse. There is no reads-equivalent fallback: a read only exists here if
//! some statement folded far enough to produce a `ds_lineage` fact naming it. The two files
//! the grammar cannot fully fold yet (`04_build_accounts.sas`'s qualified-star block,
//! `17_compliance_check.sas`'s CROSS JOIN) lose exactly the reads those statements would
//! have named — an accepted divergence from the regex-scanning oracle, documented per file
//! in the route ledger, not papered over here.
//!
//! **The algorithm, in order:**
//! 1. Resolve `seeds` (a fileid, a bare filename resolved against the store, or a table's
//!    every reader/writer).
//! 2. `directed_reach` walks `up` hops upstream (a candidate's *writes* must cover a table
//!    the frontier *reads*) and `down` hops downstream (mirrored), exactly the way
//!    `_directed_reach` does — each hop's frontier is the previous hop's new arrivals only.
//! 3. `included` = seeds ∪ upstream ∪ downstream; `role` is `seed` / `both` / `up` / `down`
//!    from which side(s) reached it. `entries` = `included`, sorted by fileid (this is the
//!    node order the response ships — verified against the oracle's own output, which is
//!    NOT BFS-discovery order).
//! 4. `project_edges` is rebuilt from scratch, restricted to `entries` alone (a table two
//!    upstream files both touch produces an edge between them even though neither hop
//!    "discovered" the other — matches `:8000`'s `18_dashboard_mart.sas` sample exactly).
//! 5. `compute_order` mirrors `orderer.py` field for field: adjacency, back-edge DFS (cycle
//!    evidence), iterative Tarjan SCCs, Kahn-BFS levels over the SCC-condensed DAG, and the
//!    `reasoning` sentence built the same way, so `order_payload`'s fileid->label swap
//!    (longest fileid first, so no id is rewritten by a prefix of another) produces the
//!    same string.
//! 6. `story` mirrors `_story`: each seed's incoming/outgoing flows, its downstream blast
//!    radius, then one sentence per loop actually present in this neighborhood.
//!
//! No `human_edits` table exists in this store yet, so `provenance` is always `inferred`
//! and `level` is always `project` here — there is nothing to promote to `fact` or
//! `human_gold` at file granularity (block-level and human-edited answers are `edges()`'s
//! and `blocklinks()`'s job, not this one's).

use crate::types::AppState;
use axum::extract::{Query, State};
use axum::http::StatusCode;
use axum::response::Json;
use serde::Deserialize;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet, HashMap, VecDeque};

/// Hard ceiling on one neighborhood (`service.py`'s `MAX_NEIGHBORHOOD`), so a very common
/// table cannot drag the whole corpus into a single answer.
const MAX_NEIGHBORHOOD: usize = 200;

#[derive(Deserialize)]
pub struct NeighborhoodParams {
    #[serde(default)]
    file: Option<String>,
    #[serde(default)]
    table: Option<String>,
    #[serde(default)]
    up: Option<i64>,
    #[serde(default)]
    down: Option<i64>,
}

/// `urlParams.ts:3`: missing/blank -> 1, else clamp to 0..3.
fn clamp_hops(v: Option<i64>) -> i64 {
    v.unwrap_or(1).clamp(0, 3)
}

/// One file-level flow, aggregating every table that makes `src` feed `dst`
/// (`orderer.py::Flow`).
#[derive(Debug, Clone)]
struct Edge {
    src: String,
    dst: String,
    tables: Vec<String>,
}

pub async fn neighborhood(
    State(state): State<AppState>,
    Query(params): Query<NeighborhoodParams>,
) -> Result<Json<Value>, (StatusCode, String)> {
    let up = clamp_hops(params.up);
    let down = clamp_hops(params.down);
    let ise = |e: duckdb::Error| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string());

    // ---- load the store's fact tables into file<->table indexes ----------------------
    let mut writes_of_file: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut reads_of_file: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    let mut all_fileids: BTreeSet<String> = BTreeSet::new();
    {
        let conn = state.db.lock().map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;

        let mut st = conn.prepare("SELECT fileid FROM files").map_err(ise)?;
        let mut rows = st.query([]).map_err(ise)?;
        while let Some(r) = rows.next().map_err(ise)? {
            let fileid: String = r.get(0).map_err(ise)?;
            all_fileids.insert(fileid);
        }
        drop(rows);
        drop(st);

        let mut st = conn
            .prepare("SELECT fileid, name FROM blocks WHERE name IS NOT NULL AND name != ''")
            .map_err(ise)?;
        let mut rows = st.query([]).map_err(ise)?;
        while let Some(r) = rows.next().map_err(ise)? {
            let fileid: String = r.get(0).map_err(ise)?;
            let name: String = r.get(1).map_err(ise)?;
            writes_of_file.entry(fileid).or_default().insert(name);
        }
        drop(rows);
        drop(st);

        let mut st = conn.prepare("SELECT DISTINCT fileid, src_table, dst_table FROM edges").map_err(ise)?;
        let mut rows = st.query([]).map_err(ise)?;
        while let Some(r) = rows.next().map_err(ise)? {
            let fileid: String = r.get(0).map_err(ise)?;
            let src_table: String = r.get(1).map_err(ise)?;
            let dst_table: String = r.get(2).map_err(ise)?;
            reads_of_file.entry(fileid.clone()).or_default().insert(src_table);
            writes_of_file.entry(fileid).or_default().insert(dst_table);
        }
    }

    let mut writer_of_table: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for (fid, tabs) in &writes_of_file {
        for t in tabs {
            writer_of_table.entry(t.clone()).or_default().insert(fid.clone());
        }
    }
    let mut reader_of_table: BTreeMap<String, BTreeSet<String>> = BTreeMap::new();
    for (fid, tabs) in &reads_of_file {
        for t in tabs {
            reader_of_table.entry(t.clone()).or_default().insert(fid.clone());
        }
    }

    // ---- seeds -------------------------------------------------------------------------
    let seeds = resolve_seeds(params.file.as_deref(), params.table.as_deref(), &all_fileids, &writer_of_table, &reader_of_table)
        .map_err(|msg| (StatusCode::BAD_REQUEST, msg))?;

    // ---- directed reach ------------------------------------------------------------------
    let upstream = directed_reach(&seeds, up, &reads_of_file, &writer_of_table);
    let downstream = directed_reach(&seeds, down, &writes_of_file, &reader_of_table);

    let seed_set: BTreeSet<String> = seeds.iter().cloned().collect();
    let mut included: BTreeSet<String> = BTreeSet::new();
    included.extend(seed_set.iter().cloned());
    included.extend(upstream.iter().cloned());
    included.extend(downstream.iter().cloned());

    let mut roles: BTreeMap<String, &'static str> = BTreeMap::new();
    for fid in &included {
        let role = if seed_set.contains(fid) {
            "seed"
        } else if upstream.contains(fid) && downstream.contains(fid) {
            "both"
        } else if upstream.contains(fid) {
            "up"
        } else {
            "down"
        };
        roles.insert(fid.clone(), role);
    }

    // `_entries_for`: only fileids that actually exist in the store, sorted, capped.
    let entries: Vec<String> = included
        .into_iter()
        .filter(|f| all_fileids.contains(f))
        .take(MAX_NEIGHBORHOOD)
        .collect();

    let labels = build_labels(&entries);
    let raw_edges = project_edges(&entries, &reads_of_file, &writes_of_file);
    let order = compute_order(&raw_edges, &entries);

    let nodes: Vec<Value> = entries
        .iter()
        .map(|fid| {
            let folder = folder_of(fid);
            let result = &order[fid];
            json!({
                "id": fid,
                "label": labels[fid],
                "folder": folder,
                "score": result.score,
                "cyclic": result.cyclic,
                "role": roles.get(fid).copied().unwrap_or("seed"),
            })
        })
        .collect();

    let edges: Vec<Value> = raw_edges
        .iter()
        .map(|e| {
            json!({
                "src": e.src,
                "dst": e.dst,
                "tables": e.tables,
                "level": "project",
                "provenance": "inferred",
            })
        })
        .collect();

    let present: BTreeSet<&String> = entries.iter().collect();
    let seeds_out: Vec<String> = seed_set.into_iter().filter(|s| present.contains(s)).collect();

    let story = build_story(&entries, &seeds, &raw_edges, &order, &labels);
    let order_payload = build_order_payload(&order, &labels);

    Ok(Json(json!({
        "nodes": nodes,
        "edges": edges,
        "seeds": seeds_out,
        "story": story,
        "order": order_payload,
    })))
}

fn folder_of(fileid: &str) -> String {
    match fileid.rfind('/') {
        Some(i) => fileid[..i].to_string(),
        None => String::new(),
    }
}

fn basename_of(fileid: &str) -> &str {
    fileid.rsplit('/').next().unwrap_or(fileid)
}

/// `_seed_fileids` / `_resolve_file`: a fileid (has a `/`) is trusted as-is; a bare name is
/// resolved against every stored fileid with that basename; a `table=` seeds from every
/// file that reads or writes it.
fn resolve_seeds(
    file: Option<&str>,
    table: Option<&str>,
    all_fileids: &BTreeSet<String>,
    writer_of_table: &BTreeMap<String, BTreeSet<String>>,
    reader_of_table: &BTreeMap<String, BTreeSet<String>>,
) -> Result<Vec<String>, String> {
    if let Some(f) = file {
        if !f.is_empty() {
            if f.contains('/') {
                return Ok(vec![f.to_string()]);
            }
            let matches: BTreeSet<String> = all_fileids.iter().filter(|fid| basename_of(fid) == f).cloned().collect();
            return Ok(matches.into_iter().collect());
        }
    }
    if let Some(t) = table {
        if !t.is_empty() {
            let mut set: BTreeSet<String> = BTreeSet::new();
            if let Some(s) = writer_of_table.get(t) {
                set.extend(s.iter().cloned());
            }
            if let Some(s) = reader_of_table.get(t) {
                set.extend(s.iter().cloned());
            }
            return Ok(set.into_iter().collect());
        }
    }
    Err("neighborhood needs a table= or a file=".to_string())
}

/// `_directed_reach`: BFS, `hops` rounds, each round's frontier is only the PREVIOUS
/// round's new arrivals. `own_tables` is the frontier file's own reads (walking up) or
/// writes (walking down); `table_owner` maps a table to the files that sit on the other
/// side (writers, for up; readers, for down) — membership there already proves the
/// candidate is really on that side of the flow, so there is no separate pool re-check
/// (the index is built from the same fact the re-check would look up).
fn directed_reach(
    seeds: &[String],
    hops: i64,
    own_tables: &BTreeMap<String, BTreeSet<String>>,
    table_owner: &BTreeMap<String, BTreeSet<String>>,
) -> BTreeSet<String> {
    let seed_set: BTreeSet<String> = seeds.iter().cloned().collect();
    let mut reached: BTreeSet<String> = BTreeSet::new();
    let mut frontier: BTreeSet<String> = seed_set.clone();
    for _ in 0..hops.max(0) {
        let mut nxt: BTreeSet<String> = BTreeSet::new();
        for fid in &frontier {
            if let Some(terms) = own_tables.get(fid) {
                for term in terms {
                    if let Some(others) = table_owner.get(term) {
                        for other in others {
                            if reached.contains(other) || nxt.contains(other) || seed_set.contains(other) {
                                continue;
                            }
                            nxt.insert(other.clone());
                        }
                    }
                }
            }
        }
        if nxt.is_empty() {
            break;
        }
        reached.extend(nxt.iter().cloned());
        frontier = nxt;
        if reached.len() >= MAX_NEIGHBORHOOD {
            break;
        }
    }
    reached
}

/// `_labels`: the basename, qualified by folder only when two included files share a name.
fn build_labels(entries: &[String]) -> BTreeMap<String, String> {
    let mut counts: HashMap<&str, usize> = HashMap::new();
    for fid in entries {
        *counts.entry(basename_of(fid)).or_insert(0) += 1;
    }
    entries
        .iter()
        .map(|fid| {
            let name = basename_of(fid);
            let label = if counts[name] == 1 { name.to_string() } else { fid.clone() };
            (fid.clone(), label)
        })
        .collect()
}

/// `project_edges`: for every table, every writer among `entries` paired with every
/// reader among `entries` (writer != reader) becomes one edge; multiple tables between the
/// same pair fold into that one edge's `tables` list.
fn project_edges(
    entries: &[String],
    reads_of_file: &BTreeMap<String, BTreeSet<String>>,
    writes_of_file: &BTreeMap<String, BTreeSet<String>>,
) -> Vec<Edge> {
    let mut writers: BTreeMap<&str, Vec<&String>> = BTreeMap::new();
    let mut readers: BTreeMap<&str, Vec<&String>> = BTreeMap::new();
    for fid in entries {
        if let Some(tabs) = writes_of_file.get(fid) {
            for t in tabs {
                writers.entry(t.as_str()).or_default().push(fid);
            }
        }
        if let Some(tabs) = reads_of_file.get(fid) {
            for t in tabs {
                readers.entry(t.as_str()).or_default().push(fid);
            }
        }
    }

    let mut edges: BTreeMap<(String, String), BTreeSet<String>> = BTreeMap::new();
    for (table, writing_files) in &writers {
        let Some(reading_files) = readers.get(table) else { continue };
        for src in writing_files {
            for dst in reading_files {
                if src != dst {
                    edges.entry(((*src).clone(), (*dst).clone())).or_default().insert(table.to_string());
                }
            }
        }
    }

    edges
        .into_iter()
        .map(|((src, dst), tables)| Edge { src, dst, tables: tables.into_iter().collect() })
        .collect()
}

// --------------------------------------------------------------------------- compute_order

#[derive(Debug, Clone)]
struct OrderResult {
    file: String,
    score: i64,
    cyclic: bool,
    cycle_id: Option<String>,
    cycle_members: Vec<String>,
    break_suggestion: Option<(String, String)>,
    reasoning: String,
}

#[derive(Clone, PartialEq, Eq, PartialOrd, Ord, Hash, Debug)]
enum Sid {
    C(usize),
    N(String),
}

/// `_adjacency`: every node present (even with no outgoing edges), edges deduplicated.
fn adjacency(flows: &[Edge], all_nodes: &BTreeSet<String>) -> BTreeMap<String, BTreeSet<String>> {
    let mut adj: BTreeMap<String, BTreeSet<String>> = all_nodes.iter().map(|n| (n.clone(), BTreeSet::new())).collect();
    for e in flows {
        adj.entry(e.src.clone()).or_default().insert(e.dst.clone());
        adj.entry(e.dst.clone()).or_default();
    }
    adj
}

/// `_back_edges`: iterative DFS over sorted roots and sorted children; a back edge is one
/// that lands on a node still `Visiting` — the state machine's cycle evidence.
fn back_edges(adj: &BTreeMap<String, BTreeSet<String>>) -> Vec<(String, String)> {
    #[derive(PartialEq, Clone, Copy)]
    enum St {
        Unvisited,
        Visiting,
        Done,
    }
    let mut state: BTreeMap<String, St> = adj.keys().map(|k| (k.clone(), St::Unvisited)).collect();
    let mut back: Vec<(String, String)> = Vec::new();

    for root in adj.keys().cloned().collect::<Vec<_>>() {
        if state[&root] != St::Unvisited {
            continue;
        }
        let mut stack: Vec<(String, Vec<String>, usize)> =
            vec![(root.clone(), adj[&root].iter().cloned().collect(), 0)];
        *state.get_mut(&root).unwrap() = St::Visiting;
        while !stack.is_empty() {
            let top = stack.len() - 1;
            let node = stack[top].0.clone();
            let child_opt = {
                let (_, children, idx) = &mut stack[top];
                if *idx < children.len() {
                    let c = children[*idx].clone();
                    *idx += 1;
                    Some(c)
                } else {
                    None
                }
            };
            match child_opt {
                None => {
                    *state.get_mut(&node).unwrap() = St::Done;
                    stack.pop();
                }
                Some(child) => match state[&child] {
                    St::Unvisited => {
                        *state.get_mut(&child).unwrap() = St::Visiting;
                        let children: Vec<String> = adj[&child].iter().cloned().collect();
                        stack.push((child, children, 0));
                    }
                    St::Visiting => back.push((node.clone(), child)),
                    St::Done => {}
                },
            }
        }
    }
    back
}

/// `_sccs`: iterative Tarjan; only real cycles (size > 1 — a self-loop cannot occur here,
/// `project_edges` never connects a node to itself).
fn sccs(adj: &BTreeMap<String, BTreeSet<String>>) -> Vec<Vec<String>> {
    let mut index: HashMap<String, i64> = HashMap::new();
    let mut low: HashMap<String, i64> = HashMap::new();
    let mut on: HashMap<String, bool> = HashMap::new();
    let mut order: Vec<String> = Vec::new();
    let mut counter: i64 = 0;
    let mut result: Vec<Vec<String>> = Vec::new();

    for root in adj.keys().cloned().collect::<Vec<_>>() {
        if index.contains_key(&root) {
            continue;
        }
        let mut work: Vec<(String, usize)> = vec![(root, 0)];
        while let Some(&(ref node_ref, pi)) = work.last() {
            let node = node_ref.clone();
            if pi == 0 {
                index.insert(node.clone(), counter);
                low.insert(node.clone(), counter);
                counter += 1;
                order.push(node.clone());
                on.insert(node.clone(), true);
            }
            let children: Vec<String> = adj.get(&node).map(|s| s.iter().cloned().collect()).unwrap_or_default();
            let mut recurse = false;
            let mut ci = pi;
            while ci < children.len() {
                let ch = children[ci].clone();
                if !index.contains_key(&ch) {
                    let len = work.len();
                    work[len - 1] = (node.clone(), ci + 1);
                    work.push((ch, 0));
                    recurse = true;
                    break;
                }
                if *on.get(&ch).unwrap_or(&false) {
                    let li = *low.get(&node).unwrap();
                    let ic = *index.get(&ch).unwrap();
                    low.insert(node.clone(), li.min(ic));
                }
                ci += 1;
            }
            if recurse {
                continue;
            }
            work.pop();
            if let Some(&(ref parent, _)) = work.last() {
                let parent = parent.clone();
                let lp = *low.get(&parent).unwrap();
                let ln = *low.get(&node).unwrap();
                low.insert(parent, lp.min(ln));
            }
            if *low.get(&node).unwrap() == *index.get(&node).unwrap() {
                let mut comp: Vec<String> = Vec::new();
                loop {
                    let m = order.pop().unwrap();
                    on.insert(m.clone(), false);
                    let is_node = m == node;
                    comp.push(m);
                    if is_node {
                        break;
                    }
                }
                let self_loop = adj.get(&node).map(|s| s.contains(&node)).unwrap_or(false);
                if comp.len() > 1 || self_loop {
                    comp.sort();
                    result.push(comp);
                }
            }
        }
    }
    result
}

/// `compute_order`: score every entry by longest-path level of the SCC-condensed DAG (0 =
/// no flows in, it can run first), and build the same `reasoning` sentence `orderer.py`
/// does (still naming raw fileids — `order_payload`'s caller swaps those for labels).
fn compute_order(flows: &[Edge], entries: &[String]) -> BTreeMap<String, OrderResult> {
    let mut all_nodes: BTreeSet<String> = entries.iter().cloned().collect();
    for e in flows {
        all_nodes.insert(e.src.clone());
        all_nodes.insert(e.dst.clone());
    }

    let adj = adjacency(flows, &all_nodes);
    let back = back_edges(&adj);
    let cycles = sccs(&adj);
    let mut comp_of: HashMap<String, usize> = HashMap::new();
    for (i, comp) in cycles.iter().enumerate() {
        for n in comp {
            comp_of.insert(n.clone(), i);
        }
    }

    let sid = |n: &str| -> Sid {
        match comp_of.get(n) {
            Some(&i) => Sid::C(i),
            None => Sid::N(n.to_string()),
        }
    };

    let mut cadj: HashMap<Sid, BTreeSet<Sid>> = HashMap::new();
    let mut indeg: HashMap<Sid, i64> = HashMap::new();
    for n in &all_nodes {
        let s = sid(n);
        cadj.entry(s.clone()).or_default();
        indeg.entry(s).or_insert(0);
    }
    for e in flows {
        let a = sid(&e.src);
        let b = sid(&e.dst);
        if a != b {
            let inserted = cadj.entry(a).or_default().insert(b.clone());
            if inserted {
                *indeg.entry(b).or_insert(0) += 1;
            }
        }
    }

    let mut level: HashMap<Sid, i64> = HashMap::new();
    let mut queue: VecDeque<Sid> = VecDeque::new();
    let initial: BTreeSet<Sid> = indeg.iter().filter(|(_, &d)| d == 0).map(|(s, _)| s.clone()).collect();
    for s in initial {
        level.insert(s.clone(), 0);
        queue.push_back(s);
    }
    while let Some(s) = queue.pop_front() {
        let targets: BTreeSet<Sid> = cadj.get(&s).cloned().unwrap_or_default();
        for t in targets {
            let ls = *level.get(&s).unwrap();
            let cur = *level.get(&t).unwrap_or(&0);
            level.insert(t.clone(), cur.max(ls + 1));
            let d = indeg.get_mut(&t).unwrap();
            *d -= 1;
            if *d == 0 {
                queue.push_back(t);
            }
        }
    }

    // inflows: every flow landing on a node, sorted (dst, src) — `f0` is the one with the
    // lexicographically smallest src.
    let mut sorted_flows: Vec<&Edge> = flows.iter().collect();
    sorted_flows.sort_by(|a, b| (a.dst.as_str(), a.src.as_str()).cmp(&(b.dst.as_str(), b.src.as_str())));
    let mut inflows: BTreeMap<String, Vec<&Edge>> = BTreeMap::new();
    for e in &sorted_flows {
        inflows.entry(e.dst.clone()).or_default().push(e);
    }

    let mut results: BTreeMap<String, OrderResult> = BTreeMap::new();
    for n in &all_nodes {
        let s = sid(n);
        let score = *level.get(&s).unwrap_or(&0);
        let comp: Vec<String> = comp_of.get(n).map(|&i| cycles[i].clone()).unwrap_or_default();
        let comp_set: BTreeSet<&String> = comp.iter().collect();
        let cyc_back: Option<(String, String)> = if comp.is_empty() {
            None
        } else {
            back.iter().find(|(a, b)| comp_set.contains(a) && comp_set.contains(b)).cloned()
        };

        let mut parts: Vec<String> = Vec::new();
        match inflows.get(n).filter(|v| !v.is_empty()) {
            None => {
                if score == 0 {
                    parts.push(format!("score {score}: no flows in - nothing feeds {n}; it can run first"));
                } else {
                    parts.push(format!("score {score}: no direct flows in"));
                }
            }
            Some(v) => {
                let f0 = v[0];
                let t0 = &f0.tables[0];
                parts.push(format!("score {score}: {t0} -> {n}, and {t0} is only ready at level {}", (score - 1).max(0)));
            }
        }
        if !comp.is_empty() {
            let mut loop_chain = comp.clone();
            loop_chain.push(comp[0].clone());
            parts.push(format!("in a loop: {}; data feeds back into where it started", loop_chain.join(" -> ")));
            if let Some((a, b)) = &cyc_back {
                parts.push(format!("break the flow {a} -> {b} to serialize"));
            }
        }

        results.insert(
            n.clone(),
            OrderResult {
                file: n.clone(),
                score,
                cyclic: !comp.is_empty(),
                cycle_id: comp_of.get(n).map(|i| format!("cycle_{i}")),
                cycle_members: comp,
                break_suggestion: cyc_back,
                reasoning: parts.join("; "),
            },
        );
    }
    results
}

// --------------------------------------------------------------------------- story

/// `_story`: each seed's incoming/outgoing flows (in `raw_edges`' own (src,dst) order,
/// which is already what `project_edges` sorts by), its downstream blast radius, then one
/// sentence per loop actually present in this neighborhood.
fn build_story(
    entries: &[String],
    seeds: &[String],
    raw_edges: &[Edge],
    order: &BTreeMap<String, OrderResult>,
    labels: &BTreeMap<String, String>,
) -> Vec<String> {
    let _ = entries;
    let mut incoming: BTreeMap<String, Vec<&Edge>> = BTreeMap::new();
    let mut outgoing: BTreeMap<String, Vec<&Edge>> = BTreeMap::new();
    for e in raw_edges {
        outgoing.entry(e.src.clone()).or_default().push(e);
        incoming.entry(e.dst.clone()).or_default().push(e);
    }

    let mut story: Vec<String> = Vec::new();
    let mut seed_sorted: Vec<String> = seeds.iter().filter(|s| labels.contains_key(*s)).cloned().collect();
    seed_sorted.sort();
    seed_sorted.dedup();

    for seed in &seed_sorted {
        let name = &labels[seed];
        if let Some(edges) = incoming.get(seed) {
            for e in edges {
                story.push(format!("{} -> {} -> {}", labels[&e.src], e.tables.join(", "), name));
            }
        }
        if let Some(edges) = outgoing.get(seed) {
            for e in edges {
                story.push(format!("{} -> {} -> {}", name, e.tables.join(", "), labels[&e.dst]));
            }
        }
        let downstream_files = downstream(seed, &outgoing);
        let names = if downstream_files.is_empty() {
            "none".to_string()
        } else {
            downstream_files
                .iter()
                .map(|d| labels.get(d).cloned().unwrap_or_else(|| d.clone()))
                .collect::<Vec<_>>()
                .join(", ")
        };
        story.push(format!("if {name} changes, {} downstream files are affected: {names}", downstream_files.len()));
    }

    let mut seen: BTreeSet<String> = BTreeSet::new();
    for (_, result) in order.iter() {
        if !result.cyclic {
            continue;
        }
        let cid = result.cycle_id.clone().unwrap();
        if seen.contains(&cid) {
            continue;
        }
        seen.insert(cid);
        let members: Vec<String> = result.cycle_members.iter().map(|m| labels.get(m).cloned().unwrap_or_else(|| m.clone())).collect();
        let mut loop_chain = members.clone();
        if let Some(first) = members.first() {
            loop_chain.push(first.clone());
        }
        let mut sentence = format!("in a loop: {}; data feeds back into where it started", loop_chain.join(" -> "));
        if let Some((src, dst)) = &result.break_suggestion {
            sentence.push_str(&format!(
                "; break the flow {} -> {} to serialize",
                labels.get(src).cloned().unwrap_or_else(|| src.clone()),
                labels.get(dst).cloned().unwrap_or_else(|| dst.clone())
            ));
        }
        story.push(sentence);
    }
    story
}

/// `_downstream`: every file the seed's data reaches, transitively (seed excluded).
fn downstream(seed: &str, outgoing: &BTreeMap<String, Vec<&Edge>>) -> Vec<String> {
    let mut reached: BTreeSet<String> = BTreeSet::new();
    let mut queue: VecDeque<String> = VecDeque::new();
    queue.push_back(seed.to_string());
    while let Some(node) = queue.pop_front() {
        if let Some(edges) = outgoing.get(&node) {
            for e in edges {
                if !reached.contains(&e.dst) {
                    reached.insert(e.dst.clone());
                    queue.push_back(e.dst.clone());
                }
            }
        }
    }
    reached.remove(seed);
    reached.into_iter().collect()
}

/// `order_payload`: `OrderResult`s as JSON, keyed by fileid, with every raw fileid inside
/// `reasoning` swapped for its label — longest fileid first, so no id is rewritten by a
/// prefix of another.
fn build_order_payload(order: &BTreeMap<String, OrderResult>, labels: &BTreeMap<String, String>) -> Value {
    let mut swaps: Vec<(&String, &String)> = labels.iter().collect();
    swaps.sort_by(|a, b| b.0.len().cmp(&a.0.len()).then(a.0.cmp(b.0)));

    let mut payload = serde_json::Map::new();
    for (fileid, result) in order.iter() {
        let mut reasoning = result.reasoning.clone();
        for (raw, label) in &swaps {
            reasoning = reasoning.replace(raw.as_str(), label.as_str());
        }
        let break_suggestion = match &result.break_suggestion {
            Some((a, b)) => json!([a, b]),
            None => Value::Null,
        };
        let row = json!({
            "file": result.file,
            "score": result.score,
            "cyclic": result.cyclic,
            "cycle_id": result.cycle_id,
            "cycle_members": result.cycle_members,
            "break_suggestion": break_suggestion,
            "reasoning": reasoning,
            "label": labels.get(fileid).cloned().unwrap_or_else(|| fileid.clone()),
        });
        payload.insert(fileid.clone(), row);
    }
    Value::Object(payload)
}
