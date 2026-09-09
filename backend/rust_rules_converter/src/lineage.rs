//! lineage.rs — the mirror of codegen/lineage_common.pl + sas_lineage.pl +
//! pyspark_lineage.pl (exp_42, 2026-09-07). Same four facts, same sorted text
//! output, so `diff` proves the two engines agree. Every function names the
//! Prolog clause it copies.
use crate::term::Term;
use std::collections::{BTreeSet, HashMap};

fn lower(s: &str) -> String { s.to_lowercase() }
fn atom(s: &str) -> Term { Term::atom(s) }

/// lineage_common.pl: ds_key/2
pub fn ds_key(d: &Term) -> String {
    match d.functor() {
        ("ds", 2) => format!("{}.{}", lower(d.args()[0].atom_text()), lower(d.args()[1].atom_text())),
        ("ds", 1) => format!("work.{}", lower(d.args()[0].atom_text())),
        _ => panic!("not a dataset ref: {}", d),
    }
}

/// lineage_common.pl: the dynamic facts schema/2, ds_lineage/2, col_lineage/4, ctl_lineage/3
#[derive(Default)]
pub struct Facts {
    schema: HashMap<String, Vec<String>>,
    facts: BTreeSet<String>,      // every non-schema fact as its writeq text (sort/2 = byte order, deduped)
}

impl Facts {
    // set_schema/2, schema_or_empty/2
    pub fn set_schema(&mut self, k: &str, cols: Vec<String>) { self.schema.insert(k.to_string(), cols); }
    pub fn schema_or_empty(&self, k: &str) -> Vec<String> { self.schema.get(k).cloned().unwrap_or_default() }
    // reads/2, copy_cols/2, controls/3 (and the bare assertz of a col_lineage)
    pub fn reads(&mut self, out: &str, inp: &str) {
        self.facts.insert(format!("{}.", Term::compound("ds_lineage", vec![atom(out), atom(inp)])));
    }
    pub fn col(&mut self, out: &str, oc: &str, inp: &str, ic: &str) {
        self.facts.insert(format!("{}.", Term::compound("col_lineage", vec![atom(out), atom(oc), atom(inp), atom(ic)])));
    }
    pub fn copy_cols(&mut self, out: &str, inp: &str) {
        for c in self.schema_or_empty(inp) { self.col(out, &c, inp, &c); }
    }
    pub fn controls(&mut self, out: &str, inp: &str, cols: &[String]) {
        for c in cols { self.facts.insert(format!("{}.", Term::compound("ctl_lineage", vec![atom(out), atom(inp), atom(c)]))); }
    }
    /// write_facts/1: schema facts join the rest, everything sorted by text
    pub fn text(&self) -> String {
        let mut all: BTreeSet<String> = self.facts.clone();
        for (k, cols) in &self.schema {
            let t = Term::compound("schema", vec![atom(k), Term::List(cols.iter().map(|c| atom(c)).collect())]);
            all.insert(format!("{}.", t));
        }
        let mut s = String::new();
        for a in all { s.push_str(&a); s.push('\n'); }
        s
    }
}

/// lineage_common.pl: blocks/1 + block_terms/2 over the folded statements
pub fn blocks<'t>(nodes: &[(String, &'t Term)]) -> Vec<Vec<&'t Term>> {
    let mut out: Vec<(String, Vec<&Term>)> = Vec::new();
    for (b, t) in nodes {
        match out.iter_mut().find(|(k, _)| k == b) { Some((_, v)) => v.push(t), None => out.push((b.clone(), vec![t])) }
    }
    out.into_iter().map(|(_, v)| v).collect()
}

fn dedup(v: Vec<String>) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    for x in v { if !out.contains(&x) { out.push(x); } }
    out
}
fn find<'t>(ts: &[&'t Term], f: &str, ar: usize) -> Option<&'t Term> { ts.iter().find(|t| t.functor() == (f, ar)).copied() }
fn sub_terms<'t>(t: &'t Term, out: &mut Vec<&'t Term>) {
    out.push(t);
    match t { Term::Compound(_, a) => for x in a { sub_terms(x, out) }, Term::List(a) => for x in a { sub_terms(x, out) }, _ => {} }
}

// ================================================================ SAS side
pub mod sas {
    use super::*;

    /// sas_lineage.pl: main — every block through step/1
    pub fn run(nodes: &[(String, &Term)]) -> Facts {
        let mut f = Facts::default();
        for ts in blocks(nodes) { step(&mut f, &ts); }
        f
    }

    fn var_name(v: &Term) -> String { lower(v.args()[0].atom_text()) }

    fn step(f: &mut Facts, ts: &[&Term]) {
        match ts[0].functor() {
            ("data", 1) => {
                let k = ds_key(&ts[0].args()[0]);
                let body = &ts[1..];
                // DATA out; INPUT vars; DATALINES -> a source: schema only
                if let (Some(input), Some(_)) = (find(body, "input", 1), find(body, "datalines", 1)) {
                    f.set_schema(&k, input.args()[0].list().iter().map(var_name).collect());
                    return;
                }
                // DATA out; IF _N_ = 1 THEN SET look; SET main
                if let (Some(its), Some(set)) = (find(body, "if_then_set", 3), find(body, "set", 1)) {
                    if its.args()[1] == Term::compound("lit", vec![Term::Int(1)]) {
                        let (ki, kl) = (ds_key(&set.args()[0]), ds_key(&its.args()[2]));
                        f.reads(&k, &ki); f.reads(&k, &kl); f.copy_cols(&k, &ki); f.copy_cols(&k, &kl);
                        let mut cols = f.schema_or_empty(&ki); cols.extend(f.schema_or_empty(&kl));
                        f.set_schema(&k, dedup(cols));
                        return;
                    }
                }
                // DATA out; SET in; IF cond ...
                if let Some(set) = find(body, "set", 1) {
                    let ki = ds_key(&set.args()[0]);
                    f.reads(&k, &ki); f.copy_cols(&k, &ki);
                    for t in body { if t.functor() == ("subset_if", 1) { let cs = expr_cols(&t.args()[0]); f.controls(&k, &ki, &cs); } }
                    let cols = f.schema_or_empty(&ki); f.set_schema(&k, cols);
                    return;
                }
                // DATA out; MERGE a b; BY keys
                if let Some(merge) = find(body, "merge", 1) {
                    let keys: Vec<String> = find(body, "by", 1).map(|b| b.args()[0].list().iter().map(|k| lower(k.atom_text())).collect()).unwrap_or_default();
                    let mut cols = Vec::new();
                    for src in merge.args()[0].list() {
                        let kd = ds_key(&src.args()[0]);
                        f.reads(&k, &kd); f.copy_cols(&k, &kd); f.controls(&k, &kd, &keys);
                        cols.extend(f.schema_or_empty(&kd));
                    }
                    f.set_schema(&k, dedup(cols));
                }
            }
            ("proc_sql", 0) => {
                for t in &ts[1..] {
                    if t.functor() == ("create_table_as", 2) {
                        let k = ds_key(&t.args()[0]);
                        let core = &t.args()[1].args()[0].list()[0];
                        select_lineage(f, &k, core);
                    }
                }
            }
            _ => {}   // LIBNAME, PROC PRINT, TITLE, RUN: no lineage
        }
    }

    fn from_ds(from: &Term) -> String {
        match from.functor() {
            ("table", 2) => ds_key(&from.args()[0]),
            ("subquery", 2) => from_ds(&from.args()[0].args()[1]),
            _ => panic!("from_ds {}", from),
        }
    }

    /// select_lineage/2
    // task 5c: `joins` is a Prolog LIST now (zero or more left_join(Src,On) /
    // inner_join(Src,On) terms, source order) — was `join: some(J)|none`, at
    // most one, before this task. Every join is read the same way regardless
    // of that functor name (args()[0]/args()[1] as (Src, On)), matching the
    // Prolog mirror (codegen/sas_lineage.pl's select_lineage/2, same task).
    fn select_lineage(f: &mut Facts, k: &str, core: &Term) {
        let a = core.args();
        let (projs, from, joins, wh, group, having) = (a[0].list(), &a[1], a[2].list(), &a[3], &a[4], &a[5]);
        let ki = from_ds(from); f.reads(k, &ki);
        for j in joins {
            let kj = from_ds(&j.args()[0]); f.reads(k, &kj);
            let cs = expr_cols(&j.args()[1]); f.controls(k, &ki, &cs); f.controls(k, &kj, &cs);
        }
        let mut cols = Vec::new();
        for p in projs { cols.extend(proj_lineage(f, k, &ki, &p.args()[0], &p.args()[1])); }
        f.set_schema(k, cols);
        if wh.functor() == ("some", 1) { cond_lineage(f, k, &ki, &wh.args()[0]); }
        if group.functor() == ("some", 1) {
            for g in group.args()[0].list() { let cs = expr_cols(g); f.controls(k, &ki, &cs); }
        }
        if having.functor() == ("some", 1) { cond_lineage(f, k, &ki, &having.args()[0]); }
    }

    /// proj_lineage/5
    fn proj_lineage(f: &mut Facts, k: &str, ki: &str, e: &Term, alias: &Term) -> Vec<String> {
        if e.functor() == ("star", 0) && alias.functor() == ("none", 0) {
            f.copy_cols(k, ki);
            return f.schema_or_empty(ki);
        }
        let col = if alias.functor() == ("some", 1) { lower(alias.args()[0].atom_text()) }
                  else if e.functor() == ("col", 1) { lower(e.args()[0].atom_text()) }
                  else { "_auto".to_string() };
        for c in expr_cols(e) { f.col(k, &col, ki, &c); }
        vec![col]
    }

    /// cond_lineage/3
    fn cond_lineage(f: &mut Facts, k: &str, ki: &str, w: &Term) {
        let cs = expr_cols(w); f.controls(k, ki, &cs);
        let mut subs = Vec::new(); sub_terms(w, &mut subs);
        for s in subs {
            if s.functor() == ("subquery_expr", 1) {
                let core = &s.args()[0];
                let ks = from_ds(&core.args()[1]); f.reads(k, &ks);
                let mut scs = Vec::new();
                for p in core.args()[0].list() { scs.extend(expr_cols(&p.args()[0])); }
                f.controls(k, &ks, &scs);
            }
        }
    }

    /// expr_cols/2
    pub fn expr_cols(e: &Term) -> Vec<String> {
        match e.functor() {
            ("col", 1) => vec![lower(e.args()[0].atom_text())],
            ("col", 2) => vec![lower(e.args()[1].atom_text())],
            ("lit", _) | ("star", 0) | ("subquery_expr", 1) => vec![],
            _ => match e {
                Term::Compound(_, args) => dedup(args.iter().flat_map(expr_cols).collect()),
                Term::List(items) => dedup(items.iter().flat_map(expr_cols).collect()),
                _ => vec![],
            },
        }
    }
}

// ============================================================ PySpark side
pub mod pyspark {
    use super::*;

    enum State { Pass(Vec<String>), Proj(Vec<String>), Grouped(Vec<String>) }
    fn state_cols(s: &State) -> Vec<String> { match s { State::Pass(c) | State::Proj(c) | State::Grouped(c) => c.clone() } }

    /// pyspark_lineage.pl: main — every block, bound/2 reset per block, every statement through stmt/1
    pub fn run(nodes: &[(String, &Term)]) -> Facts {
        let mut f = Facts::default();
        for ts in blocks(nodes) {
            let mut bound: HashMap<String, &Term> = HashMap::new();
            for t in ts { stmt(&mut f, &mut bound, t); }
        }
        f
    }

    fn stmt<'t>(f: &mut Facts, bound: &mut HashMap<String, &'t Term>, t: &'t Term) {
        match t.functor() {
            ("assign", 2) => { bound.insert(t.args()[0].atom_text().to_string(), &t.args()[1]); }
            ("put", 2) => {
                let out = lower(t.args()[0].args()[0].atom_text());
                let cols = df_lineage(f, bound, &out, &t.args()[1]);
                f.set_schema(&out, cols);
            }
            _ => {}
        }
    }

    fn kwarg<'t>(args: &'t [Term], name: &str) -> Option<&'t Term> {
        args.iter().find(|a| a.functor() == ("kwarg", 2) && a.args()[0].atom_text() == name).map(|a| &a.args()[1])
    }

    /// df_lineage/3
    fn df_lineage(f: &mut Facts, bound: &HashMap<String, &Term>, out: &str, df: &Term) -> Vec<String> {
        if df.functor() == ("call", 2) {
            let (name, args) = (df.args()[0].atom_text(), df.args()[1].list());
            match name {
                "sas_datalines" => {
                    let items = kwarg(args, "columns").expect("columns=").args()[0].list();
                    return items.iter().map(|t| lower(t.args()[0].args()[0].atom_text())).collect();
                }
                "sas_merge" => {
                    let srcs = args.iter().find(|a| a.functor() == ("list", 1)).expect("sources").args()[0].list();
                    let keys: Vec<String> = kwarg(args, "by").map(|l| l.args()[0].list().iter().map(|k| lower(k.args()[0].atom_text())).collect()).unwrap_or_default();
                    let mut cols = Vec::new();
                    for s in srcs {
                        let n = lower(s.args()[0].args()[0].atom_text());
                        f.reads(out, &n); f.copy_cols(out, &n); f.controls(out, &n, &keys);
                        cols.extend(f.schema_or_empty(&n));
                    }
                    return dedup(cols);
                }
                "sas_attach_first_row" => {
                    let (m, l) = (lower(args[0].args()[1].args()[0].atom_text()), lower(args[1].args()[1].args()[0].atom_text()));
                    f.reads(out, &m); f.reads(out, &l); f.copy_cols(out, &m); f.copy_cols(out, &l);
                    let mut cols = f.schema_or_empty(&m); cols.extend(f.schema_or_empty(&l));
                    return dedup(cols);
                }
                _ => {}
            }
        }
        // a method chain
        let (root, methods) = chain(df);
        let inp = root_ds(root);
        f.reads(out, &inp);
        let mut state = State::Pass(f.schema_or_empty(&inp));
        for m in methods { state = method(f, bound, out, &inp, m, state); }
        match state {
            State::Pass(cols) => { f.copy_cols(out, &inp); cols }
            State::Proj(cols) | State::Grouped(cols) => cols,
        }
    }

    /// chain/3: dot(dot(root, call1), call2) -> (root, [call1, call2])
    fn chain(t: &Term) -> (&Term, Vec<&Term>) {
        if t.functor() == ("dot", 2) && t.args()[1].functor() == ("call", 2) {
            let (root, mut ms) = chain(&t.args()[0]);
            ms.push(&t.args()[1]);
            (root, ms)
        } else { (t, vec![]) }
    }

    /// root_ds/2
    fn root_ds(root: &Term) -> String {
        match root.functor() {
            ("index", 2) => lower(root.args()[1].args()[0].atom_text()),
            ("paren", 1) => root_ds(chain(&root.args()[0]).0),
            _ => panic!("root_ds {}", root),
        }
    }

    /// method/5
    fn method(f: &mut Facts, bound: &HashMap<String, &Term>, out: &str, inp: &str, m: &Term, s: State) -> State {
        let (name, args) = (m.args()[0].atom_text(), m.args()[1].list());
        match name {
            "filter" | "where" => { cond_lineage(f, bound, out, inp, &args[0]); s }
            "select" if args.len() == 1 && args[0] == Term::compound("lit", vec![Term::atom("*")]) => {
                let cols = state_cols(&s);
                for c in &cols { f.col(out, c, inp, c); }
                State::Proj(cols)
            }
            "select" => State::Proj(args.iter().map(|e| proj_lineage(f, out, inp, e)).collect()),
            "agg" => {
                let acols: Vec<String> = args.iter().map(|e| proj_lineage(f, out, inp, e)).collect();
                match s { State::Grouped(mut keys) => { keys.extend(acols); State::Proj(keys) }, _ => State::Proj(acols) }
            }
            "groupBy" => {
                let cols: Vec<String> = args.iter().map(|e| proj_lineage(f, out, inp, e)).collect();
                for k in args { let kcs = expr_cols(k); f.controls(out, inp, &kcs); }
                State::Grouped(cols)
            }
            "alias" | "orderBy" | "limit" => s,
            other => { eprintln!("LINEAGEQ: no lineage rule for .{}()", other); s }
        }
    }

    /// proj_lineage/4
    fn proj_lineage(f: &mut Facts, out: &str, inp: &str, e: &Term) -> String {
        if e.functor() == ("dot", 2) && e.args()[1].functor() == ("call", 2) && e.args()[1].args()[0].atom_text() == "alias" {
            let col = lower(e.args()[1].args()[1].list()[0].args()[0].atom_text());
            for c in expr_cols(&e.args()[0]) { f.col(out, &col, inp, &c); }
            return col;
        }
        let col = pycol(e).unwrap_or_else(|| "_auto".to_string());
        for c in expr_cols(e) { f.col(out, &col, inp, &c); }
        col
    }

    /// cond_lineage/3
    fn cond_lineage(f: &mut Facts, bound: &HashMap<String, &Term>, out: &str, inp: &str, cond: &Term) {
        let cs = expr_cols(cond); f.controls(out, inp, &cs);
        let mut subs = Vec::new(); sub_terms(cond, &mut subs);
        for s in subs {
            if s.functor() != ("col", 1) { continue; }
            let Some(e) = bound.get(s.args()[0].atom_text()) else { continue };
            if e.functor() == ("call", 2) && e.args()[0].atom_text() == "scalar" {
                let (root, ms) = chain(&e.args()[1].list()[0]);
                let ks = root_ds(root); f.reads(out, &ks);
                let mut scs = Vec::new();
                for m in ms { if m.args()[0].atom_text() == "select" { for x in m.args()[1].list() { scs.extend(expr_cols(x)); } } }
                f.controls(out, &ks, &scs);
            }
        }
    }

    /// pycol/2: F.col("x") -> x
    fn pycol(e: &Term) -> Option<String> {
        if e.functor() == ("dot", 2) && e.args()[0] == Term::compound("col", vec![Term::atom("F")]) {
            let c = &e.args()[1];
            if c.functor() == ("call", 2) && c.args()[0].atom_text() == "col" {
                return Some(lower(c.args()[1].list()[0].args()[0].atom_text()));
            }
        }
        None
    }

    /// expr_cols/2
    pub fn expr_cols(e: &Term) -> Vec<String> {
        if let Some(n) = pycol(e) { return vec![n]; }
        match e {
            Term::Compound(f, args) if f == "lit" || f == "col" => vec![],
            Term::Compound(_, args) => dedup(args.iter().flat_map(expr_cols).collect()),
            Term::List(items) => dedup(items.iter().flat_map(expr_cols).collect()),
            _ => vec![],
        }
    }
}
