//! emit.rs — SAS node/4 -> PySpark, in Rust. The same rules as
//! codegen/sas_pyspark.pl, clause for clause: one function per SAS step shape,
//! one match arm per expression functor. Output is diffed against the Prolog
//! generator's byte for byte.
use crate::term::Term;
use std::collections::HashMap;

#[derive(Clone)]
pub struct Node { pub block: String, pub seq: usize, pub term: Term, pub l0: usize, pub l1: usize, pub b0: usize, pub b1: usize }

pub struct Emitter { schema: HashMap<String, Vec<String>>, scalar_n: usize }

fn lower(s: &str) -> String { s.to_lowercase() }

pub fn py_str(a: &str) -> String {
    let mut s = String::from("\"");
    for c in a.chars() {
        match c { '\\' => s.push_str("\\\\"), '"' => s.push_str("\\\""), '\n' => s.push_str("\\n"), c => s.push(c) }
    }
    s.push('"'); s
}

fn ds_key(d: &Term) -> String {
    match d.functor() {
        ("ds", 2) => format!("{}.{}", lower(d.args()[0].atom_text()), lower(d.args()[1].atom_text())),
        ("ds", 1) => format!("work.{}", lower(d.args()[0].atom_text())),
        _ => panic!("not a dataset ref: {}", d),
    }
}

fn is_agg(e: &Term) -> bool {
    match e.functor() {
        ("call", 2) => matches!(lower(e.args()[0].atom_text()).as_str(), "sum" | "avg" | "mean" | "max" | "min" | "count" | "std" | "var" | "nmiss"),
        _ => false,
    }
}

fn sas_fn(name: &str) -> String {
    match name {
        "month" => "month", "year" => "year", "day" => "dayofmonth",
        "sum" => "sum", "avg" => "avg", "mean" => "avg", "max" => "max", "min" => "min", "count" => "count",
        "upcase" => "upper", "lowcase" => "lower", "abs" => "abs", "round" => "round", "substr" => "substring",
        other => panic!("LINEAGEQ: no PySpark mapping for SAS function {}", other),
    }.to_string()
}

fn some_arg(t: &Term) -> Option<&Term> {
    match t.functor() { ("some", 1) => Some(&t.args()[0]), _ => None }
}

/// task 5d: the alias of one from_source (table(Ds,AliasOpt) or
/// subquery(Core,AliasOpt), both alias in arg position 1) — used to resolve a
/// qualified star (`a.*`), same helper as lineage.rs's/interp.rs's own
/// from_alias.
fn from_source_alias(from: &Term) -> Option<String> {
    match from.functor() {
        ("table", 2) | ("subquery", 2) => some_arg(&from.args()[1]).map(|a| a.atom_text().to_lowercase()),
        _ => None,
    }
}

impl Emitter {
    pub fn new() -> Self { Emitter { schema: HashMap::new(), scalar_n: 0 } }

    pub fn program(&mut self, nodes: &[Node], preamble: &str) -> String {
        let mut blocks: Vec<String> = Vec::new();
        for n in nodes { if !blocks.contains(&n.block) { blocks.push(n.block.clone()); } }
        let mut lines: Vec<String> = vec!["".into(), "spark = make_spark()".into(), "".into()];
        for b in &blocks {
            let terms: Vec<&Term> = nodes.iter().filter(|n| &n.block == b).map(|n| &n.term).collect();
            let l0 = nodes.iter().filter(|n| &n.block == b).map(|n| n.l0).min().unwrap();
            let l1 = nodes.iter().filter(|n| &n.block == b).map(|n| n.l1).max().unwrap();
            lines.push(format!("# ---- {}  lines {}-{}  {}", b, l0, l1, self.step_title(&terms)));
            match self.step_lines(&terms) {
                Some(body) => lines.extend(body),
                None => lines.push(format!("# LINEAGEQ: no rule for this step: {}", Term::List(terms.iter().map(|t| (*t).clone()).collect()))),
            }
            lines.push("".into());
        }
        lines.extend(["".to_string(), "# ---- every dataset the program created, in SAS log order".into(),
                      "for _name in ORDER:".into(), "    sas_print(_name)".into(), "spark.stop()".into()]);
        format!("{}\n{}\n", preamble, lines.join("\n"))
    }

    fn step_title(&self, ts: &[&Term]) -> String {
        match ts[0].functor() {
            ("libname", 2) => format!("LIBNAME {} '{}'", ts[0].args()[0].atom_text(), ts[0].args()[1].args()[0].atom_text()),
            ("data", 1) => format!("DATA {}", ds_key(&ts[0].args()[0])),
            ("proc_sql", 0) => "PROC SQL".into(),
            ("proc_print", 1) => format!("PROC PRINT {}", ds_key(&ts[0].args()[0])),
            _ => "".into(),
        }
    }

    fn find<'t>(ts: &[&'t Term], f: &str, ar: usize) -> Option<&'t Term> {
        ts.iter().find(|t| t.functor() == (f, ar)).copied()
    }

    fn step_lines(&mut self, ts: &[&Term]) -> Option<Vec<String>> {
        match ts[0].functor() {
            ("libname", 2) => {
                let path = ts[0].args()[1].args()[0].atom_text();
                Some(vec![format!("LIBS[\"{}\"] = {}", ts[0].args()[0].atom_text(), py_str(path))])
            }
            ("proc_sql", 0) => {
                let mut lines = Vec::new();
                for t in &ts[1..] {
                    if t.functor() == ("create_table_as", 2) { lines.extend(self.sql_lines(&t.args()[0], &t.args()[1])); }
                }
                Some(lines)
            }
            ("proc_print", 1) => {
                let mut lines = vec![format!("# PROC PRINT {} -> listed by sas_print at the end of this program", ds_key(&ts[0].args()[0]))];
                for t in &ts[1..] {
                    if t.functor() == ("title", 1) { lines.push(format!("# TITLE '{}'", t.args()[0].args()[0].atom_text())); }
                }
                Some(lines)
            }
            ("data", 1) => {
                let out = ds_key(&ts[0].args()[0]);
                let body = &ts[1..];
                let fmt_lines: Vec<String> = body.iter().filter(|t| t.functor() == ("format", 2))
                    .map(|t| format!("FORMATS[\"{}\"] = \"{}.\"", lower(t.args()[0].atom_text()), t.args()[1].args()[0].atom_text())).collect();
                if let (Some(input), Some(dl)) = (Self::find(body, "input", 1), Self::find(body, "datalines", 1)) {
                    let vars = input.args()[0].list();
                    let cols: Vec<String> = vars.iter().map(|v| match v.functor() {
                        ("cvar", 1) => format!("(\"{}\", \"char\", None)", lower(v.args()[0].atom_text())),
                        ("nvar", 2) => match some_arg(&v.args()[1]) {
                            Some(inf) => format!("(\"{}\", \"num\", \"{}\")", lower(v.args()[0].atom_text()), inf.args()[0].atom_text()),
                            None => format!("(\"{}\", \"num\", None)", lower(v.args()[0].atom_text())),
                        },
                        _ => panic!("input var {}", v),
                    }).collect();
                    let names: Vec<String> = vars.iter().map(|v| lower(v.args()[0].atom_text())).collect();
                    self.schema.insert(out.clone(), names);
                    // exp_42 2026-09-07: FORMAT lines first, like sas_pyspark.pl
                    let mut lines = fmt_lines;
                    lines.extend([
                        format!("put(\"{}\", sas_datalines(spark,", out),
                        format!("    columns=[{}],", cols.join(", ")),
                        format!("    rows={}))", py_str(dl.args()[0].atom_text())),
                    ]);
                    return Some(lines);
                }
                if let (Some(its), Some(set)) = (body.iter().find(|t| t.functor() == ("if_then_set", 3) && t.args()[1] == Term::Compound("lit".into(), vec![Term::Int(1)])).copied(), Self::find(body, "set", 1)) {
                    let (ki, kl) = (ds_key(&set.args()[0]), ds_key(&its.args()[2]));
                    let mut cols: Vec<String> = Vec::new();
                    for dk in [&ki, &kl] { if let Some(cs) = self.schema.get(dk) { for c in cs { if !cols.contains(c) { cols.push(c.clone()); } } } }
                    self.schema.insert(out.clone(), cols);
                    let mut lines = fmt_lines;
                    lines.push(format!("put(\"{}\", sas_attach_first_row(ds[\"{}\"], ds[\"{}\"]))", out, ki, kl));
                    return Some(lines);
                }
                if let Some(set) = Self::find(body, "set", 1) {
                    let ki = ds_key(&set.args()[0]);
                    let mut chain = String::new();
                    for t in body.iter().filter(|t| t.functor() == ("subset_if", 1)) {
                        let mut pre = Vec::new();
                        let p = self.px(&t.args()[0], &mut pre);
                        chain.push_str(&format!(".filter({})", p));
                    }
                    if let Some(cols) = self.schema.get(&ki).cloned() { self.schema.insert(out.clone(), cols); }
                    let mut lines = fmt_lines;
                    lines.push(format!("put(\"{}\", ds[\"{}\"]{})", out, ki, chain));
                    return Some(lines);
                }
                if let Some(merge) = Self::find(body, "merge", 1) {
                    let srcs = merge.args()[0].list();
                    let keys: Vec<String> = match Self::find(body, "by", 1) {
                        Some(by) => by.args()[0].list().iter().map(|k| k.atom_text().to_string()).collect(),
                        None => vec![],
                    };
                    let src_txts: Vec<String> = srcs.iter().map(|s| { let k = ds_key(&s.args()[0]); format!("(\"{}\", ds[\"{}\"])", k, k) }).collect();
                    let key_pys: Vec<String> = keys.iter().map(|k| py_str(k)).collect();
                    let mut lines = Vec::new();
                    let mut all_cols: Vec<String> = Vec::new();
                    for s in srcs {
                        let dk = ds_key(&s.args()[0]);
                        if let Some(cols) = self.schema.get(&dk) {
                            for key in &keys {
                                if !cols.contains(key) {
                                    lines.push(format!("# LINEAGEQ CHECK: BY variable {} is not on {} (its columns: {}) -> SAS logs an ERROR, stops the step, and leaves 0 observations.", key, dk, cols.join(", ")));
                                }
                            }
                            for c in cols { if !all_cols.contains(c) { all_cols.push(c.clone()); } }
                        }
                    }
                    lines.push(format!("put(\"{}\", sas_merge(spark, [{}], by=[{}]))", out, src_txts.join(", "), key_pys.join(", ")));
                    self.schema.insert(out, all_cols);
                    return Some(lines);
                }
                None
            }
            _ => None,
        }
    }

    // ------------------------------------------------------------ PROC SQL
    fn sql_lines(&mut self, out: &Term, sel: &Term) -> Vec<String> {
        let k = ds_key(out);
        let cores = sel.args()[0].list();
        let core = &cores[0];
        let mut pre = Vec::new();
        let chain = self.core_chain(core, &mut pre);
        let ord = match some_arg(&sel.args()[1]) {
            Some(keys) => {
                let ps: Vec<String> = keys.list().iter().map(|kk| { let mut p = Vec::new(); self.px(kk, &mut p) }).collect();
                format!(".orderBy({})", ps.join(", "))
            }
            None => String::new(),
        };
        pre.push(format!("put(\"{}\", {}{})", k, chain, ord));
        let cols = self.core_out_cols(core);
        self.schema.insert(k, cols);
        pre
    }

    // task 5c: `joins` is a Prolog LIST now (was `join: some(J)|none`) — one
    // `.join(...)` per item, source order; still hardcoded "inner" (this
    // pre-existing simplification — never reading left_join vs inner_join's
    // own functor for the join TYPE — is unchanged by this task). task 5d:
    // a join whose own arity is 1 (cross_join(Src): no ON) renders
    // `.crossJoin(src)` instead — arity decides this, not the functor name.
    fn core_chain(&mut self, core: &Term, pre: &mut Vec<String>) -> String {
        let a = core.args();
        let (cols, from, joins, where_, group, having) = (&a[0], &a[1], a[2].list(), &a[3], &a[4], &a[5]);
        let mut s = self.from_txt(from, pre);
        for j in joins {
            let src = self.from_txt(&j.args()[0], pre);
            if j.args().len() > 1 {
                let on = self.px(&j.args()[1], pre);
                s.push_str(&format!(".join({}, {}, \"inner\")", src, on));
            } else {
                s.push_str(&format!(".crossJoin({})", src));
            }
        }
        if let Some(c) = some_arg(where_) { let x = self.px(c, pre); s.push_str(&format!(".filter({})", x)); }
        s.push_str(&self.select_txt(cols.list(), group, pre));
        if let Some(c) = some_arg(having) { let x = self.px(c, pre); s.push_str(&format!(".filter({})", x)); }
        s
    }

    fn from_txt(&mut self, from: &Term, pre: &mut Vec<String>) -> String {
        match from.functor() {
            ("table", 2) => {
                let k = ds_key(&from.args()[0]);
                match some_arg(&from.args()[1]) {
                    Some(al) => format!("ds[\"{}\"].alias(\"{}\")", k, lower(al.atom_text())),
                    None => format!("ds[\"{}\"]", k),
                }
            }
            ("subquery", 2) => {
                let c = self.core_chain(&from.args()[0], pre);
                match some_arg(&from.args()[1]) {
                    Some(al) => format!("({}).alias(\"{}\")", c, lower(al.atom_text())),
                    None => format!("({})", c),
                }
            }
            _ => panic!("from {}", from),
        }
    }

    fn proj_txt(&mut self, p: &Term, pre: &mut Vec<String>) -> String {
        let (e, alias) = (&p.args()[0], &p.args()[1]);
        if e.functor() == ("star", 0) && alias.functor() == ("none", 0) { return "F.col(\"*\")".into(); }
        // task 5d: a qualified star (`a.*`) — Spark's own `"alias.*"` column
        // string expands to every column of that aliased source, so this is
        // the direct analogue of the bare-star arm just above.
        if e.functor() == ("star", 1) && alias.functor() == ("none", 0) {
            return format!("F.col(\"{}.*\")", lower(e.args()[0].atom_text()));
        }
        let x = self.px(e, pre);
        match some_arg(alias) { Some(a) => format!("{}.alias(\"{}\")", x, lower(a.atom_text())), None => x }
    }

    fn select_txt(&mut self, cols: &[Term], group: &Term, pre: &mut Vec<String>) -> String {
        match some_arg(group) {
            None => {
                if cols.len() == 1 && cols[0].args()[1].functor() == ("none", 0) {
                    match cols[0].args()[0].functor() {
                        ("star", 0) => return ".select(\"*\")".into(),
                        ("star", 1) => return format!(".select(\"{}.*\")", lower(cols[0].args()[0].args()[0].atom_text())),
                        _ => {}
                    }
                }
                let any_agg = cols.iter().any(|p| is_agg(&p.args()[0]));
                let ts: Vec<String> = cols.iter().map(|p| self.proj_txt(p, pre)).collect();
                if any_agg { format!(".agg({})", ts.join(", ")) } else { format!(".select({})", ts.join(", ")) }
            }
            Some(keys) => {
                let mut kts = Vec::new();
                for key in keys.list() {
                    let kp = self.px(key, pre);
                    let alias = cols.iter().find(|p| some_arg(&p.args()[1]).is_some() && p.args()[0].lower_term() == key.lower_term())
                        .map(|p| lower(some_arg(&p.args()[1]).unwrap().atom_text()));
                    kts.push(match alias { Some(a) => format!("{}.alias(\"{}\")", kp, a), None => kp });
                }
                let aggs: Vec<String> = cols.iter().filter(|p| is_agg(&p.args()[0])).map(|p| self.proj_txt(p, pre)).collect();
                format!(".groupBy({}).agg({})", kts.join(", "), aggs.join(", "))
            }
        }
    }

    fn core_out_cols(&self, core: &Term) -> Vec<String> {
        let mut out = Vec::new();
        for p in core.args()[0].list() {
            let (e, alias) = (&p.args()[0], &p.args()[1]);
            if let Some(a) = some_arg(alias) { out.push(lower(a.atom_text())); continue; }
            match e.functor() {
                ("col", 1) => out.push(lower(e.args()[0].atom_text())),
                ("star", 0) => {
                    let from = &core.args()[1];
                    if from.functor() == ("table", 2) {
                        if let Some(cols) = self.schema.get(&ds_key(&from.args()[0])) { out.extend(cols.iter().cloned()); continue; }
                    }
                    out.push("_auto".into());
                }
                // task 5d: a qualified star (`a.*`) — same lookup as the bare
                // star above, but resolved against whichever of FROM/JOINs
                // carries alias `a`, not always FROM itself.
                ("star", 1) => {
                    let al = lower(e.args()[0].atom_text());
                    if let Some(cols) = self.alias_schema(core, &al) { out.extend(cols); continue; }
                    out.push("_auto".into());
                }
                _ => out.push("_auto".into()),
            }
        }
        out
    }

    /// task 5d: the schema of whichever from_source (FROM itself, or one of
    /// its JOINs) carries alias `al` — None if unresolved or not a plain
    /// table (a subquery's own columns are not tracked in self.schema here).
    fn alias_schema(&self, core: &Term, al: &str) -> Option<Vec<String>> {
        let from = &core.args()[1];
        if from_source_alias(from) == Some(al.to_string()) { return self.table_schema(from); }
        for j in core.args()[2].list() {
            if from_source_alias(&j.args()[0]) == Some(al.to_string()) { return self.table_schema(&j.args()[0]); }
        }
        None
    }
    fn table_schema(&self, from: &Term) -> Option<Vec<String>> {
        if from.functor() == ("table", 2) { self.schema.get(&ds_key(&from.args()[0])).cloned() } else { None }
    }

    // ----------------------------------------------------------- expressions
    pub fn px(&mut self, t: &Term, pre: &mut Vec<String>) -> String {
        let (f, ar) = t.functor();
        let a = t.args();
        match (f, ar) {
            ("col", 1) => format!("F.col(\"{}\")", lower(a[0].atom_text())),
            ("col", 2) => format!("F.col(\"{}.{}\")", lower(a[0].atom_text()), lower(a[1].atom_text())),
            ("lit", 1) => if a[0].is_number() { format!("F.lit({})", a[0]) } else { format!("F.lit({})", py_str(a[0].atom_text())) },
            ("star", 0) => "F.col(\"*\")".into(),
            ("star", 1) => format!("F.col(\"{}.*\")", lower(a[0].atom_text())),
            ("paren", 1) => format!("({})", self.px(&a[0], pre)),
            ("neg", 1) => format!("(-{})", self.px(&a[0], pre)),
            ("not", 1) => format!("(~{})", self.px(&a[0], pre)),
            ("cat", 2) => { let x = self.px(&a[0], pre); let y = self.px(&a[1], pre); format!("F.concat({}, {})", x, y) }
            ("in", 2) => {
                let x = self.px(&a[0], pre);
                let items: Vec<String> = a[1].list().iter().map(|l| if l.args()[0].is_number() { format!("{}", l.args()[0]) } else { py_str(l.args()[0].atom_text()) }).collect();
                format!("{}.isin([{}])", x, items.join(", "))
            }
            ("subquery_expr", 1) => {
                let chain = self.core_chain(&a[0], pre);
                self.scalar_n += 1;
                pre.push(format!("_scalar{} = scalar({})", self.scalar_n, chain));
                format!("F.lit(_scalar{})", self.scalar_n)
            }
            // task 5c: COUNT(DISTINCT x) -> F.countDistinct(x) — ahead of the
            // generic ("call", 2) arm below, so `distinct(...)` never has to
            // stand on its own as a general expression (it has no meaning
            // outside this one wrapper). Mirrors codegen/sas_pyspark.pl's px/4.
            ("call", 2) if lower(a[0].atom_text()) == "count" && a[1].list().len() == 1 && a[1].list()[0].functor() == ("distinct", 1) => {
                let inner = &a[1].list()[0].args()[0];
                format!("F.countDistinct({})", self.px(inner, pre))
            }
            ("call", 2) => {
                let py = sas_fn(&lower(a[0].atom_text()));
                let xs: Vec<String> = a[1].list().iter().map(|x| self.px(x, pre)).collect();
                format!("F.{}({})", py, xs.join(", "))
            }
            (op, 2) => {
                let sym = match op {
                    "mul" => "*", "div" => "/", "add" => "+", "sub" => "-",
                    "eq" => "==", "ne" => "!=", "lt" => "<", "le" => "<=", "gt" => ">", "ge" => ">=",
                    "and" => "&", "or" => "|",
                    other => panic!("no PySpark rule for expression functor {}", other),
                };
                let x = self.px(&a[0], pre); let y = self.px(&a[1], pre);
                format!("({} {} {})", x, sym, y)
            }
            _ => panic!("no PySpark rule for expression {}", t),
        }
    }
}
