//! interp.rs — the executable node/4 in Rust, the mirror of codegen/sas_interp.pl
//! (exp_42, 2026-09-07). Same dataset model, same SAS semantics (missing compares
//! low, arithmetic with missing is missing, aggregates skip missing), same CSV
//! bytes. Every function names the Prolog clause it copies.
use crate::lineage::{blocks, ds_key};
use crate::term::Term;
use std::collections::HashMap;
use std::path::Path;

/// a value: a number (dates are days since 1960-01-01), text, or missing
#[derive(Clone, Debug, PartialEq)]
pub enum Value { Missing, Num(f64), Str(String) }

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Ty { Num, Char, Date }

#[derive(Clone, Debug)]
pub struct Col { pub name: String, pub ty: Ty }

#[derive(Clone, Debug)]
pub struct Dataset { pub cols: Vec<Col>, pub rows: Vec<Vec<Value>> }

#[derive(Default)]
pub struct Interp {
    pub datasets: HashMap<String, Dataset>,
    pub order: Vec<String>,          // order/1
    pub formats: HashMap<String, String>,   // fmt/2
    pub log: Vec<String>,            // what SAS would print to the log (the MERGE error)
}

fn lower(s: &str) -> String { s.to_lowercase() }
fn find<'t>(ts: &[&'t Term], f: &str, ar: usize) -> Option<&'t Term> { ts.iter().find(|t| t.functor() == (f, ar)).copied() }
fn is_some(t: &Term) -> Option<&Term> { if t.functor() == ("some", 1) { Some(&t.args()[0]) } else { None } }

impl Interp {
    /// main: file mode (every block) or block mode (one block after load_inputs)
    pub fn run(&mut self, nodes: &[(String, &Term)], only: Option<&str>) {
        let ids: Vec<String> = { let mut v = Vec::new(); for (b, _) in nodes { if !v.contains(b) { v.push(b.clone()); } } v };
        for (b, ts) in ids.iter().zip(blocks(nodes)) {
            if only.map_or(true, |o| o == b) { self.step(&ts); }
        }
    }

    // put/3, get/3
    fn put(&mut self, k: &str, ds: Dataset) {
        self.datasets.insert(k.to_string(), ds);
        if !self.order.iter().any(|x| x == k) { self.order.push(k.to_string()); }
    }
    fn get(&self, k: &str) -> Dataset {
        self.datasets.get(k).cloned().unwrap_or_else(|| { eprintln!("ERROR: dataset {} does not exist", k); Dataset { cols: vec![], rows: vec![] } })
    }
    // remember_formats/1
    fn remember_formats(&mut self, body: &[&Term]) {
        for t in body { if t.functor() == ("format", 2) {
            self.formats.insert(lower(t.args()[0].atom_text()), t.args()[1].args()[0].atom_text().to_string());
        } }
    }

    /// step/1 — one clause per SAS step shape
    fn step(&mut self, ts: &[&Term]) {
        match ts[0].functor() {
            ("data", 1) => {
                let k = ds_key(&ts[0].args()[0]);
                let body = &ts[1..];
                self.remember_formats(body);
                // DATA out; INPUT vars; DATALINES
                if let (Some(input), Some(dl)) = (find(body, "input", 1), find(body, "datalines", 1)) {
                    let vars = input.args()[0].list();
                    let cols: Vec<Col> = vars.iter().map(input_col).collect();
                    let mut rows = Vec::new();
                    for line in dl.args()[0].atom_text().split('\n') {
                        let toks: Vec<&str> = line.trim_matches('\r').split(|c| c == ' ' || c == '\t').filter(|t| !t.is_empty()).collect();
                        if toks.is_empty() { continue; }
                        rows.push(read_row(vars, &toks));
                    }
                    self.put(&k, Dataset { cols, rows });
                    return;
                }
                // DATA out; IF _N_ = 1 THEN SET look; SET main
                if let (Some(its), Some(set)) = (find(body, "if_then_set", 3), find(body, "set", 1)) {
                    if its.args()[1] == Term::compound("lit", vec![Term::Int(1)]) {
                        let (d1, d2) = (self.get(&ds_key(&set.args()[0])), self.get(&ds_key(&its.args()[2])));
                        let first: Vec<Value> = d2.rows.first().cloned().unwrap_or_else(|| vec![Value::Missing; d2.cols.len()]);
                        let mut cols = d1.cols.clone(); cols.extend(d2.cols.clone());
                        let rows = d1.rows.iter().map(|r| { let mut x = r.clone(); x.extend(first.clone()); x }).collect();
                        self.put(&k, Dataset { cols, rows });
                        return;
                    }
                }
                // DATA out; SET in; IF cond ...
                if let Some(set) = find(body, "set", 1) {
                    let d = self.get(&ds_key(&set.args()[0]));
                    let conds: Vec<&Term> = body.iter().filter(|t| t.functor() == ("subset_if", 1)).map(|t| &t.args()[0]).collect();
                    let rows = d.rows.iter().filter(|r| self.row_passes(&d.cols, &conds, r)).cloned().collect();
                    self.put(&k, Dataset { cols: d.cols.clone(), rows });
                    return;
                }
                // DATA out; MERGE a b; BY keys
                if let Some(merge) = find(body, "merge", 1) {
                    let keys: Vec<String> = find(body, "by", 1).map(|b| b.args()[0].list().iter().map(|x| lower(x.atom_text())).collect()).unwrap_or_default();
                    let sources: Vec<(String, Dataset)> = merge.args()[0].list().iter().map(|s| { let kd = ds_key(&s.args()[0]); (kd.clone(), self.get(&kd)) }).collect();
                    let cols = col_union(sources.iter().flat_map(|(_, d)| d.cols.clone()).collect());
                    let mut missing = Vec::new();
                    for (kd, d) in &sources { for key in &keys { if !d.cols.iter().any(|c| &c.name == key) { missing.push((kd.clone(), key.clone())); } } }
                    if !missing.is_empty() {
                        for (kd, key) in &missing { self.log.push(format!("ERROR: BY variable {} is not on input data set {}.", key.to_uppercase(), kd.to_uppercase())); }
                        self.log.push("NOTE: The SAS System stopped processing this step because of errors. The data set is created with 0 observations.".into());
                        self.put(&k, Dataset { cols, rows: vec![] });
                    } else {
                        let rows = merge_rows(&sources, &keys, &cols);
                        self.put(&k, Dataset { cols, rows });
                    }
                }
            }
            ("proc_sql", 0) => {
                for t in &ts[1..] {
                    if t.functor() == ("create_table_as", 2) {
                        let k = ds_key(&t.args()[0]);
                        let ds = self.select_stmt(&t.args()[1]);
                        self.put(&k, ds);
                    }
                }
            }
            _ => {}
        }
    }

    // row_passes/3
    fn row_passes(&self, cols: &[Col], conds: &[&Term], row: &[Value]) -> bool {
        conds.iter().all(|c| truthy(&self.eval(c, cols, row)))
    }

    // ---------------------------------------------------------------- SQL
    /// select_stmt/3
    fn select_stmt(&self, sel: &Term) -> Dataset {
        let a = sel.args();
        let core = &a[0].list()[0];
        let mut ds = self.select_core(core);
        if let Some(keys) = is_some(&a[1]) { ds.rows = self.order_rows(keys.list(), &ds.cols, &ds.rows); }
        ds
    }

    /// select_core/3
    fn select_core(&self, core: &Term) -> Dataset {
        let a = core.args();
        let (projs, from, join, wh, group, having) = (a[0].list(), &a[1], &a[2], &a[3], &a[4], &a[5]);
        let d0 = self.from_rows(from);
        let din = match is_some(join) {
            Some(j) => { let d1 = self.from_rows(&j.args()[0]); self.inner_join(&d0, &d1, &j.args()[1]) }
            None => d0,
        };
        let rw: Vec<Vec<Value>> = match is_some(wh) {
            Some(w) => din.rows.iter().filter(|r| self.row_passes(&din.cols, &[w], r)).cloned().collect(),
            None => din.rows.clone(),
        };
        let groups: Option<Vec<Vec<Vec<Value>>>> = match is_some(group) {
            Some(keys) => Some(self.group_rows(keys.list(), &din.cols, &rw)),
            None => if has_agg(projs) { Some(vec![rw.clone()]) } else { None },
        };
        let rows0: Vec<Vec<Value>> = match groups {
            None => rw.iter().map(|r| self.project(projs, &din.cols, std::slice::from_ref(r))).collect(),
            Some(gs) => gs.iter().map(|g| self.project(projs, &din.cols, g)).collect(),
        };
        let cols = out_cols(projs, &din.cols);
        let rows = match is_some(having) {
            Some(h) => rows0.into_iter().filter(|r| self.row_passes(&cols, &[h], r)).collect(),
            None => rows0,
        };
        Dataset { cols, rows }
    }

    fn from_rows(&self, from: &Term) -> Dataset {
        match from.functor() {
            ("table", 2) => self.get(&ds_key(&from.args()[0])),
            ("subquery", 2) => self.select_core(&from.args()[0]),
            _ => panic!("from_rows {}", from),
        }
    }

    fn inner_join(&self, d0: &Dataset, d1: &Dataset, on: &Term) -> Dataset {
        let mut cols = d0.cols.clone(); cols.extend(d1.cols.clone());
        let mut rows = Vec::new();
        for a in &d0.rows { for b in &d1.rows {
            let mut row = a.clone(); row.extend(b.clone());
            if truthy(&self.eval(on, &cols, &row)) { rows.push(row); }
        } }
        Dataset { cols, rows }
    }

    /// group_rows/4: groups in first-seen key order
    fn group_rows(&self, keys: &[Term], cols: &[Col], rows: &[Vec<Value>]) -> Vec<Vec<Vec<Value>>> {
        let mut kvs: Vec<Vec<Value>> = Vec::new();
        let mut groups: Vec<Vec<Vec<Value>>> = Vec::new();
        for r in rows {
            let kv: Vec<Value> = keys.iter().map(|k| self.eval(k, cols, r)).collect();
            match kvs.iter().position(|x| *x == kv) {
                Some(i) => groups[i].push(r.clone()),
                None => { kvs.push(kv); groups.push(vec![r.clone()]); }
            }
        }
        groups
    }

    /// project/4 + proj_values/4
    fn project(&self, projs: &[Term], cols: &[Col], group: &[Vec<Value>]) -> Vec<Value> {
        let mut row = Vec::new();
        for p in projs {
            let e = &p.args()[0];
            if e.functor() == ("star", 0) { row.extend(group[0].clone()); }
            else if is_agg(e) {
                let name = lower(e.args()[0].atom_text());
                let arg = &e.args()[1].list()[0];
                let xs: Vec<Value> = group.iter().map(|r| self.eval(arg, cols, r)).collect();
                row.push(aggregate(&name, &xs));
            } else { row.push(self.eval(e, cols, &group[0])); }
        }
        row
    }

    /// order_rows/4: stable sort by the key values in SAS order
    fn order_rows(&self, keys: &[Term], cols: &[Col], rows: &[Vec<Value>]) -> Vec<Vec<Value>> {
        let mut triples: Vec<(Vec<Value>, usize, Vec<Value>)> = rows.iter().enumerate()
            .map(|(i, r)| (keys.iter().map(|k| self.eval(k, cols, r)).collect(), i, r.clone())).collect();
        triples.sort_by(|a, b| cmp_list(&a.0, &b.0).then(a.1.cmp(&b.1)));
        triples.into_iter().map(|t| t.2).collect()
    }

    // ---------------------------------------------------------- expressions
    /// eval/4
    pub fn eval(&self, e: &Term, cols: &[Col], row: &[Value]) -> Value {
        match e.functor() {
            ("col", 1) => value_of(&lower(e.args()[0].atom_text()), cols, row),
            ("col", 2) => value_of(&lower(e.args()[1].atom_text()), cols, row),
            ("lit", 1) => match &e.args()[0] { Term::Int(i) => Value::Num(*i as f64), Term::Float(f) => Value::Num(*f), Term::Atom(a) => Value::Str(a.clone()), t => panic!("lit {}", t) },
            ("paren", 1) => self.eval(&e.args()[0], cols, row),
            ("neg", 1) => match self.eval(&e.args()[0], cols, row) { Value::Num(x) => Value::Num(-x), _ => Value::Missing },
            ("not", 1) => bool_v(!truthy(&self.eval(&e.args()[0], cols, row))),
            ("and", 2) => bool_v(truthy(&self.eval(&e.args()[0], cols, row)) && truthy(&self.eval(&e.args()[1], cols, row))),
            ("or", 2) => bool_v(truthy(&self.eval(&e.args()[0], cols, row)) || truthy(&self.eval(&e.args()[1], cols, row))),
            ("subquery_expr", 1) => { let d = self.select_core(&e.args()[0]); d.rows.first().and_then(|r| r.first().cloned()).unwrap_or(Value::Missing) }
            ("in", 2) => { let x = self.eval(&e.args()[0], cols, row); bool_v(e.args()[1].list().iter().any(|i| self.eval(i, cols, row) == x)) }
            ("call", 2) => {
                let xs: Vec<Value> = e.args()[1].list().iter().map(|a| self.eval(a, cols, row)).collect();
                sas_fn(&lower(e.args()[0].atom_text()), &xs)
            }
            (op, 2) => { let x = self.eval(&e.args()[0], cols, row); let y = self.eval(&e.args()[1], cols, row); binop(op, &x, &y) }
            _ => panic!("eval {}", e),
        }
    }
}

// input_col/2, read_row/3, read_value/3
fn input_col(v: &Term) -> Col {
    let name = lower(v.args()[0].atom_text());
    match v.functor() {
        ("cvar", 1) => Col { name, ty: Ty::Char },
        ("nvar", 2) => Col { name, ty: if is_some(&v.args()[1]).is_some() { Ty::Date } else { Ty::Num } },
        _ => panic!("input var {}", v),
    }
}
fn read_row(vars: &[Term], toks: &[&str]) -> Vec<Value> {
    vars.iter().enumerate().map(|(i, v)| match toks.get(i) {
        None => Value::Missing,
        Some(t) => match v.functor() {
            ("cvar", 1) => Value::Str(t.to_string()),
            ("nvar", 2) => match is_some(&v.args()[1]) {
                Some(inf) => informat_date(inf.args()[0].atom_text(), t),
                None => if *t == "." { Value::Missing } else { Value::Num(t.parse().expect("number")) },
            },
            _ => panic!("input var {}", v),
        },
    }).collect()
}
fn informat_date(informat: &str, t: &str) -> Value {
    let f = informat.to_lowercase();
    let (y, m, d) = if f.starts_with("mmddyy") { let p: Vec<&str> = t.split('/').collect(); (p[2], p[0], p[1]) }
        else if f.starts_with("ddmmyy") { let p: Vec<&str> = t.split('/').collect(); (p[2], p[1], p[0]) }
        else if f.starts_with("yymmdd") { let p: Vec<&str> = t.split('-').collect(); (p[0], p[1], p[2]) }
        else { panic!("informat not supported: {}", informat) };
    Value::Num(sas_days(y.parse().unwrap(), m.parse().unwrap(), d.parse().unwrap()) as f64)
}

fn truthy(v: &Value) -> bool { matches!(v, Value::Num(x) if *x != 0.0) }
fn bool_v(b: bool) -> Value { Value::Num(if b { 1.0 } else { 0.0 }) }
fn value_of(name: &str, cols: &[Col], row: &[Value]) -> Value {
    cols.iter().position(|c| c.name == name).map(|i| row[i].clone()).unwrap_or(Value::Missing)
}

// ------------------------------------------------------------------ merge
fn key_of(keys: &[String], cols: &[Col], r: &[Value]) -> Vec<Value> { keys.iter().map(|k| value_of(k, cols, r)).collect() }

/// merge_rows/4 + merge_group/5 + nth_or_last/3
fn merge_rows(sources: &[(String, Dataset)], keys: &[String], cols: &[Col]) -> Vec<Vec<Value>> {
    let mut kvs: Vec<Vec<Value>> = Vec::new();
    for (_, d) in sources { for r in &d.rows { let kv = key_of(keys, &d.cols, r); if !kvs.contains(&kv) { kvs.push(kv); } } }
    kvs.sort_by(|a, b| cmp_list(a, b));
    let mut rows = Vec::new();
    for kv in &kvs {
        let groups: Vec<(&Dataset, Vec<&Vec<Value>>)> = sources.iter().map(|(_, d)| (d, d.rows.iter().filter(|r| key_of(keys, &d.cols, r) == *kv).collect())).collect();
        let max = groups.iter().map(|(_, g)| g.len()).max().unwrap_or(0);
        for i in 1..=max {
            let row: Vec<Value> = cols.iter().map(|c| {
                for (d, g) in &groups {
                    if g.is_empty() || !d.cols.iter().any(|x| x.name == c.name) { continue; }
                    let r = if i <= g.len() { g[i - 1] } else { g[g.len() - 1] };
                    return value_of(&c.name, &d.cols, r);
                }
                Value::Missing
            }).collect();
            rows.push(row);
        }
    }
    rows
}

/// col_union/2
fn col_union(cols: Vec<Col>) -> Vec<Col> {
    let mut out: Vec<Col> = Vec::new();
    for c in cols { if !out.iter().any(|x| x.name == c.name) { out.push(c); } }
    out
}

// -------------------------------------------------------------------- SQL
fn has_agg(projs: &[Term]) -> bool { projs.iter().any(|p| is_agg(&p.args()[0])) }
fn is_agg(e: &Term) -> bool {
    e.functor() == ("call", 2) && matches!(lower(e.args()[0].atom_text()).as_str(), "sum" | "avg" | "mean" | "max" | "min" | "count")
}

/// out_cols/3 + out_col/4 + expr_type/3
fn out_cols(projs: &[Term], cols: &[Col]) -> Vec<Col> {
    let mut out = Vec::new();
    for p in projs {
        let (e, a) = (&p.args()[0], &p.args()[1]);
        if e.functor() == ("star", 0) && a.functor() == ("none", 0) { out.extend(cols.iter().cloned()); }
        else if let Some(alias) = is_some(a) { out.push(Col { name: lower(alias.atom_text()), ty: expr_type(e, cols) }); }
        else if e.functor() == ("col", 1) {
            let name = lower(e.args()[0].atom_text());
            let ty = cols.iter().find(|c| c.name == name).map(|c| c.ty).unwrap_or(Ty::Num);
            out.push(Col { name, ty });
        } else { out.push(Col { name: "_auto".into(), ty: expr_type(e, cols) }); }
    }
    out
}
fn expr_type(e: &Term, cols: &[Col]) -> Ty {
    match e.functor() {
        ("col", 1) => cols.iter().find(|c| c.name == lower(e.args()[0].atom_text())).map(|c| c.ty).unwrap_or(Ty::Num),
        ("call", 2) if matches!(lower(e.args()[0].atom_text()).as_str(), "max" | "min") => expr_type(&e.args()[1].list()[0], cols),
        ("lit", 1) => if e.args()[0].is_number() { Ty::Num } else { Ty::Char },
        _ => Ty::Num,
    }
}

/// aggregate/3: missing skipped; an empty set gives missing (count gives 0)
fn aggregate(name: &str, xs: &[Value]) -> Value {
    let ys: Vec<f64> = xs.iter().filter_map(|v| match v { Value::Num(x) => Some(*x), _ => None }).collect();
    if name == "count" { return Value::Num(ys.len() as f64); }
    if ys.is_empty() { return Value::Missing; }
    match name {
        "sum" => Value::Num(ys.iter().fold(0.0, |a, x| a + x)),
        "avg" | "mean" => Value::Num(ys.iter().fold(0.0, |a, x| a + x) / ys.len() as f64),
        "max" => Value::Num(ys.iter().cloned().fold(f64::NEG_INFINITY, f64::max)),
        "min" => Value::Num(ys.iter().cloned().fold(f64::INFINITY, f64::min)),
        _ => panic!("aggregate {}", name),
    }
}

// ------------------------------------------------------------ expressions
/// binop/4
fn binop(op: &str, x: &Value, y: &Value) -> Value {
    if matches!(op, "eq" | "ne" | "lt" | "le" | "gt" | "ge") {
        let c = compare_sas(x, y);
        use std::cmp::Ordering::*;
        return bool_v(match op { "eq" => c == Equal, "ne" => c != Equal, "lt" => c == Less, "le" => c != Greater, "gt" => c == Greater, _ => c != Less });
    }
    if op == "cat" {
        return match (x, y) { (Value::Missing, _) | (_, Value::Missing) => Value::Missing, _ => Value::Str(format!("{}{}", show(x), show(y))) };
    }
    let (Value::Num(a), Value::Num(b)) = (x, y) else { return Value::Missing };
    match op {
        "add" => Value::Num(a + b), "sub" => Value::Num(a - b), "mul" => Value::Num(a * b),
        "div" => if *b == 0.0 { Value::Missing } else { Value::Num(a / b) },
        "pow" => Value::Num(a.powf(*b)),
        _ => panic!("binop {}", op),
    }
}
fn show(v: &Value) -> String { match v { Value::Str(s) => s.clone(), Value::Num(x) => fmt_number(*x), Value::Missing => ".".into() } }

/// compare_sas/3: missing < any number; numbers by value; text by bytes
pub fn compare_sas(x: &Value, y: &Value) -> std::cmp::Ordering {
    use std::cmp::Ordering::*;
    match (x, y) {
        (Value::Missing, Value::Missing) => Equal,
        (Value::Missing, _) => Less,
        (_, Value::Missing) => Greater,
        (Value::Num(a), Value::Num(b)) => a.partial_cmp(b).unwrap_or(Equal),
        (Value::Num(_), Value::Str(_)) => Less,
        (Value::Str(_), Value::Num(_)) => Greater,
        (Value::Str(a), Value::Str(b)) => a.cmp(b),
    }
}
fn cmp_list(a: &[Value], b: &[Value]) -> std::cmp::Ordering {
    for (x, y) in a.iter().zip(b) { let c = compare_sas(x, y); if c != std::cmp::Ordering::Equal { return c; } }
    a.len().cmp(&b.len())
}

/// sas_fn/3
fn sas_fn(name: &str, xs: &[Value]) -> Value {
    if xs.iter().any(|v| *v == Value::Missing) { return Value::Missing; }
    let num = |i: usize| match &xs[i] { Value::Num(x) => *x, v => panic!("number expected, got {:?}", v) };
    match name {
        "month" => Value::Num(civil(num(0) as i64).1 as f64),
        "year" => Value::Num(civil(num(0) as i64).0 as f64),
        "day" => Value::Num(civil(num(0) as i64).2 as f64),
        "abs" => Value::Num(num(0).abs()),
        "round" => Value::Num(num(0).round()),
        "upcase" => Value::Str(show(&xs[0]).to_uppercase()),
        "lowcase" => Value::Str(show(&xs[0]).to_lowercase()),
        other => panic!("LINEAGEQ: function {} not executable", other),
    }
}

// ------------------------------------------------------------------ dates
/// sas_days/4, days_from_civil/4, civil/4 — Howard Hinnant's algorithms
fn days_from_civil(y0: i64, m: i64, d: i64) -> i64 {
    let y = if m <= 2 { y0 - 1 } else { y0 };
    let era = y.div_euclid(400);
    let yoe = y - era * 400;
    let mp = if m > 2 { m - 3 } else { m + 9 };
    let doy = (153 * mp + 2) / 5 + d - 1;
    let doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    era * 146097 + doe - 719468
}
pub fn sas_days(y: i64, m: i64, d: i64) -> i64 { days_from_civil(y, m, d) - days_from_civil(1960, 1, 1) }
pub fn civil(days: i64) -> (i64, i64, i64) {
    let z = days + days_from_civil(1960, 1, 1) + 719468;
    let era = z.div_euclid(146097);
    let doe = z - era * 146097;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let d = doy - (153 * mp + 2) / 5 + 1;
    let m = if mp < 10 { mp + 3 } else { mp - 9 };
    let y = yoe + era * 400 + if m <= 2 { 1 } else { 0 };
    (y, m, d)
}

// ----------------------------------------------------------------- CSV out
/// fmt_number/2: integers bare, otherwise C's %.12g
pub fn fmt_number(v: f64) -> String {
    if v == v.trunc() && v.abs() < 1e15 { return format!("{}", v as i64); }
    // %.12g: 12 significant digits, trailing zeros dropped, exponent form outside [1e-4, 1e12)
    let sci = format!("{:.11e}", v);
    let (mant, exp) = sci.split_once('e').unwrap();
    let exp: i32 = exp.parse().unwrap();
    if exp < -4 || exp >= 12 {
        let m = mant.trim_end_matches('0').trim_end_matches('.');
        format!("{}e{}{:02}", m, if exp < 0 { "-" } else { "+" }, exp.abs())
    } else {
        let decimals = (11 - exp).max(0) as usize;
        let s = format!("{:.*}", decimals, v);
        if s.contains('.') { s.trim_end_matches('0').trim_end_matches('.').to_string() } else { s }
    }
}

impl Interp {
    /// fmt_cell/3
    fn fmt_cell(&self, c: &Col, v: &Value) -> String {
        match v {
            Value::Missing => ".".into(),
            Value::Num(x) if c.ty == Ty::Date => {
                match self.formats.get(&c.name) {
                    Some(f) if f.to_lowercase().starts_with("mmddyy") => { let (y, m, d) = civil(*x as i64); format!("{:02}/{:02}/{}", m, d, y) }
                    _ => fmt_number(*x),
                }
            }
            Value::Num(x) => fmt_number(*x),
            Value::Str(s) => s.clone(),
        }
    }
    /// write_csv/2: the sas_print convention, CRLF like csv.writer
    pub fn write_all(&self, out_dir: &Path) {
        std::fs::create_dir_all(out_dir).unwrap();
        for k in &self.order {
            let d = &self.datasets[k];
            let mut s = String::new();
            s.push_str(&d.cols.iter().map(|c| c.name.as_str()).collect::<Vec<_>>().join(",")); s.push_str("\r\n");
            for r in &d.rows {
                s.push_str(&d.cols.iter().zip(r).map(|(c, v)| self.fmt_cell(c, v)).collect::<Vec<_>>().join(",")); s.push_str("\r\n");
            }
            std::fs::write(out_dir.join(format!("{}.csv", k)), s).unwrap();
        }
    }
    /// load_inputs/1 + load_csv/2 + read_cell/3 (block mode)
    pub fn load_inputs(&mut self, data_dir: &Path) {
        let Ok(rd) = std::fs::read_dir(data_dir) else { return };
        let mut names: Vec<String> = rd.filter_map(|e| e.ok()).map(|e| e.file_name().to_string_lossy().to_string())
            .filter(|n| n.ends_with(".csv")).map(|n| n.trim_end_matches(".csv").to_string()).collect();
        names.sort();
        for k in names {
            let schema: serde_json::Value = serde_json::from_str(&std::fs::read_to_string(data_dir.join(format!("{}.schema.json", k))).unwrap()).unwrap();
            let mut cols = Vec::new();
            for c in schema["columns"].as_array().unwrap() {
                let name = c["name"].as_str().unwrap().to_string();
                let ty = match c["type"].as_str().unwrap() { "num" => Ty::Num, "char" => Ty::Char, "date" => Ty::Date, t => panic!("type {}", t) };
                if let Some(f) = c["format"].as_str() { self.formats.insert(name.clone(), f.to_string()); }
                cols.push(Col { name, ty });
            }
            let text = std::fs::read_to_string(data_dir.join(format!("{}.csv", k))).unwrap();
            let rows: Vec<Vec<Value>> = text.split('\n').skip(1).map(|l| l.trim_end_matches('\r')).filter(|l| !l.is_empty())
                .map(|l| l.split(',').zip(&cols).map(|(cell, c)| read_cell(c, cell)).collect()).collect();
            self.datasets.insert(k, Dataset { cols, rows });
        }
    }
}
fn read_cell(c: &Col, s: &str) -> Value {
    if s == "." { return Value::Missing; }
    match c.ty {
        Ty::Num => Value::Num(s.parse().expect("number cell")),
        Ty::Date => if s.contains('/') { informat_date("mmddyy10", s) } else { Value::Num(s.parse().expect("day count")) },
        Ty::Char => Value::Str(s.to_string()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    /// pinned to Python's "%.12g" (see loops/run_loops.sh, which prints the same values)
    #[test]
    fn fmt_number_matches_c_g12() {
        let cases = [(0.1 + 0.2, "0.3"), (111.22111111111111, "111.221111111"), (1.0 / 3.0, "0.333333333333"),
                     (1e16, "1e+16"), (12345.678901234, "12345.6789012"), (0.00001234, "1.234e-05"),
                     (150.01, "150.01"), (734.01, "734.01"), (270.01, "270.01"), (150.0, "150"), (-5.0, "-5")];
        for (v, want) in cases { assert_eq!(fmt_number(v), want, "value {}", v); }
    }
    #[test]
    fn dates_round_trip() {
        assert_eq!(sas_days(1960, 1, 1), 0);
        assert_eq!(civil(sas_days(2023, 3, 31)), (2023, 3, 31));
        assert_eq!(civil(sas_days(2024, 2, 29)), (2024, 2, 29));
    }
}
