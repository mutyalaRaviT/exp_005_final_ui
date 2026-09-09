//! `lineage_blocks` — lineage facts, attributed to the block that produced them.
//!
//! **Why this exists.** `convert` used to run `lineage::sas::run` once over a whole
//! file's terms. That yields correct edges with no idea which block made them, so
//! `blocklinks`, `tablegraph` and `story` cannot be answered. Running lineage once per
//! block instead costs one pass per block and attributes every fact.
//!
//! **Inputs → outputs.** block ids + folded terms → one `Edge` per `ds_lineage/2` fact,
//! each naming its block.

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
            }
        }
    }
    out
}
