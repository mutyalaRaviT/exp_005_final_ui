//! `lineage_blocks` — lineage facts, attributed to the block that produced them.
//!
//! **Why this exists.** `convert` used to run `lineage::sas::run` once over a whole
//! file's terms. That yields correct edges with no idea which block made them, so
//! `blocklinks`, `tablegraph` and `story` cannot be answered. Running lineage once per
//! block instead costs one pass per block and attributes every fact.
//!
//! **Inputs → outputs.** block ids + folded terms → one `Edge` per `ds_lineage/2` fact and
//! one per DISTINCT `ctl_lineage/3` table pair, each naming its block.
//!
//! **M3a defect 4 (2026-09-10), root cause C7.** `rust_rules_converter`'s lineage pass has
//! always emitted `ctl_lineage(Out, In, Col)` facts (lineage.rs::Facts::controls) — the
//! control-flow flavour of a flow, the columns a WHERE / ON / GROUP BY / BY read to decide
//! which rows survive. This function dropped them on the floor, so `edges.kind` was `ds`
//! for every row in the store and `tablegraph` answered 12 `ds` / 0 `ctl` where the Bench
//! answers 12 `ds` / 4 `ctl` on the same fixture (ledger rows C7). The label was never lost
//! in the engine or in the API — only here, in the store's edge writer, which is why the fix
//! is here and is purely additive: no `ds` edge changes.
//!
//! `ctl_lineage` names a COLUMN, so several facts share one table pair; the store's edge is
//! a table pair, so they are deduplicated per (src, dst, block) — the Bench's own graph
//! draws one `ctl` edge per pair too.

use rules_converter::{lineage, term::Term};

#[derive(Debug, Clone, PartialEq)]
pub struct Edge { pub src: String, pub dst: String, pub kind: String, pub block_id: String }

/// `ds_lineage('OUT','IN').` — note the argument order: the fact names the output first,
/// so the edge runs IN -> OUT.
fn parse_ds_lineage(line: &str) -> Option<(String, String)> {
    let rest = line.strip_prefix("ds_lineage(")?;
    let mut q = rest.split('\'').skip(1).step_by(2);
    let out = q.next()?.to_string();
    let inp = q.next()?.to_string();
    Some((inp, out))
}

/// `ctl_lineage('OUT','IN','col').` — same argument order as `ds_lineage`: output first,
/// so the edge runs IN -> OUT. The third argument (the controlling column) is not part of a
/// table-level edge and is dropped after deduplication.
fn parse_ctl_lineage(line: &str) -> Option<(String, String)> {
    let rest = line.strip_prefix("ctl_lineage(")?;
    let mut q = rest.split('\'').skip(1).step_by(2);
    let out = q.next()?.to_string();
    let inp = q.next()?.to_string();
    Some((inp, out))
}

pub fn edges_per_block(ids: &[String], terms: &[Option<Term>]) -> Vec<Edge> {
    let mut order: Vec<&String> = Vec::new();
    for id in ids { if !order.contains(&id) { order.push(id); } }

    let mut out = Vec::new();
    for bid in order {
        let nodes: Vec<(String, &Term)> = ids.iter().enumerate()
            .filter(|(_, x)| *x == bid)
            .filter_map(|(i, _)| terms[i].as_ref().map(|t| (bid.clone(), t)))
            .collect();
        if nodes.is_empty() { continue; }
        for line in lineage::sas::run(&nodes).text().lines() {
            if let Some((src, dst)) = parse_ds_lineage(line) {
                out.push(Edge { src, dst, kind: "ds".into(), block_id: bid.clone() });
            } else if let Some((src, dst)) = parse_ctl_lineage(line) {
                let e = Edge { src, dst, kind: "ctl".into(), block_id: bid.clone() };
                if !out.contains(&e) { out.push(e); }
            }
        }
    }
    out
}
