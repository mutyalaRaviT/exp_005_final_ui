//! `rules_converter` — the SAS rules engine as a library.
//!
//! **Why this exists.** exp_42 shipped this engine as one binary (`main.rs`, 2794 lines
//! across nine modules). Phase 1 needs the same code callable in-process, so
//! `rust_inferred_duckdb` can fold a file and write the result straight into the store
//! without shelling out and re-parsing text. Nothing here is re-derived: the modules are
//! copied verbatim from `raw/bench_stack/rust_engine/src/`, and only the module
//! declarations and these five helpers moved out of `main.rs` into this file.
//!
//! **Inputs → outputs.** a pyDSL spec (`out/spec/sas.json`) + SAS source text
//! → tokens → node/4 terms → block ids, printed SAS, PySpark, lineage facts.
//!
//! Source: `raw/bench_stack/rust_engine/src/main.rs` at exp_42 commit 30afba6.

pub mod emit;
pub mod emit_pretty;
pub mod lineage;
pub mod interp;
pub mod parser;
pub mod spec;
pub mod term;
pub mod tokenise;

use std::fs;
use std::path::Path;

pub fn quote_atom(s: &str) -> String { format!("'{}'", s.replace('\\', "\\\\").replace('\'', "''")) }

pub fn block_ids(spec: &spec::Spec, terms: &[Option<term::Term>]) -> Vec<String> {
    // step blocks, mirroring pipeline/blocks.py assign_blocks_by_steps
    let cfg = spec.blocks.as_ref().expect("spec.blocks");
    let mut blocks: Vec<Vec<usize>> = Vec::new();
    let mut cur: Vec<usize> = Vec::new();
    for (i, t) in terms.iter().enumerate() {
        let f = t.as_ref().map(|t| t.functor().0.to_string()).unwrap_or_default();
        if cfg.single.contains(&f) {
            if !cur.is_empty() { blocks.push(std::mem::take(&mut cur)); }
            blocks.push(vec![i]);
        } else if cfg.open.contains(&f) {
            if !cur.is_empty() { blocks.push(std::mem::take(&mut cur)); }
            cur.push(i);
        } else if cfg.close.contains(&f) {
            cur.push(i);
            blocks.push(std::mem::take(&mut cur));
        } else {
            cur.push(i);
        }
    }
    if !cur.is_empty() { blocks.push(cur); }
    let mut ids = vec![String::new(); terms.len()];
    for (bi, seqs) in blocks.iter().enumerate() {
        for &i in seqs { ids[i] = format!("b_{:03}", bi + 1); }
    }
    ids
}

pub fn raw_body(t: &str) -> &str {
    match t.find(';') { Some(i) => t[i + 1..].trim(), None => t.trim() }
}

/// Walk the full token list; each grammar token is replaced by the next printed
/// text of its statement. Equal (ignoring keyword case, or raw-body-equal for a
/// datalines block) keeps the ORIGINAL spelling, so the source comes back exactly.
pub fn rebuild_source(toks: &[tokenise::Tok], printed: &[Option<Vec<String>>]) -> (String, Vec<(String, String)>) {
    let mut out = String::new();
    let mut mism = Vec::new();
    let mut stmt_i: isize = -1;
    let mut seg_has_grammar = false;
    let mut queue: std::collections::VecDeque<String> = Default::default();
    for t in toks {
        if t.kind == "eos" { seg_has_grammar = false; continue; }
        if !tokenise::GRAMMAR_KINDS.contains(&t.kind.as_str()) { out.push_str(&t.text); continue; }
        if !seg_has_grammar {
            seg_has_grammar = true;
            stmt_i += 1;
            queue = printed.get(stmt_i as usize).cloned().flatten().unwrap_or_default().into();
        }
        match queue.pop_front() {
            None => out.push_str(&t.text),
            Some(p) => {
                if p == t.text || p.eq_ignore_ascii_case(&t.text)
                   || (t.kind == "datalines" && raw_body(&p) == raw_body(&t.text)) {
                    out.push_str(&t.text);
                } else {
                    mism.push((t.text.clone(), p.clone()));
                    out.push_str(&p);
                }
            }
        }
    }
    (out, mism)
}

/// exp_42 2026-09-07: fold a source with a spec, return the node/4 rows (block id, term)
/// plus the statement spans — the shared front half of every subcommand.
pub fn fold_file(spec: &spec::Spec, text: &str) -> (Vec<tokenise::StmtToks>, Vec<Option<term::Term>>, Vec<String>) {
    let toks = tokenise::tokenise(spec, text);
    let stmts = tokenise::split_statements(&toks);
    let terms: Vec<Option<term::Term>> = stmts.iter().map(|st| parser::Parser::new(spec, &st.toks).fold()).collect();
    let ids = block_ids(spec, &terms);
    (stmts, terms, ids)
}
