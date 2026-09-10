//! emit_pretty.rs — SAS node/4 -> PySpark a person would write. The same rules
//! as codegen/sas_pyspark_pretty.pl (named DataFrames, the SAS of each step as
//! a comment sliced from the source, one clause per line, SAS-flavoured
//! helpers). Its output is diffed byte for byte against the Prolog printer's.
use crate::emit::Node;
use crate::term::Term;
use std::collections::{HashMap, HashSet};

const PY_KEYWORDS: [&str; 34] = ["class", "def", "if", "in", "is", "for", "from", "import", "and", "or", "not", "return", "pass", "with", "as", "lambda", "while", "try", "except", "global", "del", "yield", "raise", "break", "continue", "elif", "else", "finally", "assert", "nonlocal", "async", "await", "None", "True"];

pub struct Pretty<'a> {
    source: &'a str,
    nodes: &'a [Node],
    schema: HashMap<String, Vec<String>>,
    scalar_names: HashSet<String>,
    shared_names: HashSet<String>,   // dataset names that occur under more than one libref
}

fn lower(s: &str) -> String { s.to_lowercase() }

fn py_str(a: &str) -> String {
    let mut s = String::from("\"");
    for c in a.chars() { match c { '\\' => s.push_str("\\\\"), '"' => s.push_str("\\\""), '\n' => s.push_str("\\n"), c => s.push(c) } }
    s.push('"'); s
}

fn py_path(a: &str) -> String {
    if !a.contains('"') && !a.ends_with('\\') { format!("r\"{}\"", a) } else { py_str(a) }
}

fn py_lit(t: &Term) -> String {
    if t.is_number() { format!("{}", t) } else { py_str(t.atom_text()) }
}

fn ds_key(d: &Term) -> String {
    match d.functor() {
        ("ds", 2) => format!("{}.{}", lower(d.args()[0].atom_text()), lower(d.args()[1].atom_text())),
        ("ds", 1) => format!("work.{}", lower(d.args()[0].atom_text())),
        _ => panic!("not a dataset ref: {}", d),
    }
}

fn is_agg(e: &Term) -> bool {
    e.functor().0 == "call" && matches!(lower(e.args()[0].atom_text()).as_str(), "sum" | "avg" | "mean" | "max" | "min" | "count" | "std" | "var" | "nmiss")
}

fn is_binop(e: &Term) -> bool {
    let (f, ar) = e.functor();
    ar == 2 && matches!(f, "mul" | "div" | "add" | "sub" | "eq" | "ne" | "lt" | "le" | "gt" | "ge" | "and" | "or")
}

fn sas_fn(name: &str) -> &'static str {
    match name {
        "month" => "month", "year" => "year", "day" => "dayofmonth",
        "sum" => "sum", "avg" => "avg", "mean" => "avg", "max" => "max", "min" => "min", "count" => "count",
        "upcase" => "upper", "lowcase" => "lower", "abs" => "abs", "round" => "round", "substr" => "substring",
        other => panic!("LINEAGEQ: no PySpark mapping for SAS function {}", other),
    }
}

fn some_arg(t: &Term) -> Option<&Term> { match t.functor() { ("some", 1) => Some(&t.args()[0]), _ => None } }

/// task 5d: the alias of one from_source (table(Ds,AliasOpt) or
/// subquery(Core,AliasOpt), both alias in arg position 1) — used to resolve a
/// qualified star (`a.*`), same helper as emit.rs's/lineage.rs's/interp.rs's
/// own from_alias.
fn from_source_alias(from: &Term) -> Option<String> {
    match from.functor() {
        ("table", 2) | ("subquery", 2) => some_arg(&from.args()[1]).map(|a| a.atom_text().to_lowercase()),
        _ => None,
    }
}

fn rule_line(label: &str) -> String {
    let head = format!("# ---- {} ", label);
    let pad = std::cmp::max(4, 78usize.saturating_sub(head.chars().count()));
    format!("{}{}", head, "-".repeat(pad))
}

fn collect_ds(t: &Term, out: &mut Vec<(String, String)>) {
    match t {
        Term::Compound(f, args) => {
            if f == "ds" && args.len() == 2 { out.push((lower(args[0].atom_text()), lower(args[1].atom_text()))); }
            else if f == "ds" && args.len() == 1 { out.push(("work".into(), lower(args[0].atom_text()))); }
            else { for a in args { collect_ds(a, out); } }
        }
        Term::List(items) => for a in items { collect_ds(a, out); },
        _ => {}
    }
}

/// a statement spread over several source lines: joined with one space, then
/// broken before FROM / WHERE / GROUP BY / HAVING / ORDER BY
fn reflow(lines: Vec<String>) -> Vec<String> {
    if lines.len() <= 1 { return lines; }
    let mut parts = vec![lines.join(" ")];
    for kw in ["FROM", "WHERE", "GROUP BY", "HAVING", "ORDER BY"] {
        let needle = format!(" {} ", kw);
        let mut next = Vec::new();
        for p in parts {
            let mut rest = p;
            loop {
                let upper = rest.to_uppercase();
                match upper.find(&needle) {
                    Some(i) => { next.push(rest[..i].to_string()); rest = rest[i + 1..].to_string(); }
                    None => { next.push(rest); break; }
                }
            }
        }
        parts = next;
    }
    parts.into_iter().map(|p| p.split_whitespace().collect::<Vec<_>>().join(" ")).filter(|p| !p.is_empty()).collect()
}

impl<'a> Pretty<'a> {
    pub fn new(source: &'a str, nodes: &'a [Node]) -> Self {
        let mut all = Vec::new();
        for n in nodes { collect_ds(&n.term, &mut all); }
        let mut libs_by_name: HashMap<String, HashSet<String>> = HashMap::new();
        for (l, n) in all { libs_by_name.entry(n).or_default().insert(l); }
        let shared_names = libs_by_name.into_iter().filter(|(_, ls)| ls.len() > 1).map(|(n, _)| n).collect();
        Pretty { source, nodes, schema: HashMap::new(), scalar_names: HashSet::new(), shared_names }
    }

    fn pyvar(&self, d: &Term) -> String {
        let (lib, name) = match d.functor() {
            ("ds", 2) => (lower(d.args()[0].atom_text()), lower(d.args()[1].atom_text())),
            _ => ("work".to_string(), lower(d.args()[0].atom_text())),
        };
        let v0 = if self.shared_names.contains(&name) { format!("{}_{}", lib, name) } else { name };
        let mut v: String = v0.chars().map(|c| if c.is_ascii_alphanumeric() || c == '_' { c } else { '_' }).collect();
        if v.chars().next().map_or(false, |c| c.is_ascii_digit()) { v.insert(0, '_'); }
        if PY_KEYWORDS.contains(&v.as_str()) || v == "False" { v.push('_'); }
        v
    }

    pub fn program(&mut self, preamble: &str) -> String {
        let mut blocks: Vec<String> = Vec::new();
        for n in self.nodes { if !blocks.contains(&n.block) { blocks.push(n.block.clone()); } }
        let mut lines: Vec<String> = vec!["spark = make_spark()".into(), "".into()];
        let mut shows: Vec<(String, String)> = Vec::new();
        for b in &blocks {
            let ns: Vec<&Node> = self.nodes.iter().filter(|n| &n.block == b).collect();
            let terms: Vec<&Term> = ns.iter().map(|n| &n.term).collect();
            let l0 = ns.iter().map(|n| n.l0).min().unwrap();
            let l1 = ns.iter().map(|n| n.l1).max().unwrap();
            let (label, kind) = self.step_label(&terms);
            lines.push(rule_line(&format!("{}  ({}, SAS lines {}-{})", label, kind, l0, l1)));
            for n in &ns { lines.extend(self.source_comment(&n.term, n.b0, n.b1)); }
            match self.step_lines(&terms) {
                Some(body) => lines.extend(body),
                None => lines.push(format!("# no rule for this step yet: {}", Term::List(terms.iter().map(|t| (*t).clone()).collect()))),
            }
            lines.push("".into());
            if let Some(d) = Self::out_ds(&terms) {
                let k = ds_key(d);
                if !shows.iter().any(|(kk, _)| kk == &k) { shows.push((k, self.pyvar(d))); }
            }
        }
        lines.push(rule_line("every dataset the program created, in SAS log order"));
        for (k, v) in shows { lines.push(format!("show(\"{}\", {})", k, v)); }
        lines.push("spark.stop()".into());
        format!("{}\n{}\n", preamble, lines.join("\n"))
    }

    fn out_ds<'t>(ts: &[&'t Term]) -> Option<&'t Term> {
        match ts[0].functor() {
            ("data", 1) => Some(&ts[0].args()[0]),
            ("proc_sql", 0) => ts[1..].iter().find(|t| t.functor() == ("create_table_as", 2)).map(|t| &t.args()[0]),
            _ => None,
        }
    }

    fn step_label(&self, ts: &[&Term]) -> (String, &'static str) {
        match ts[0].functor() {
            ("libname", 2) => (format!("libref {}", ts[0].args()[0].atom_text()), "LIBNAME"),
            ("data", 1) => (ds_key(&ts[0].args()[0]), "DATA step"),
            ("proc_sql", 0) => match Self::out_ds(ts) { Some(d) => (ds_key(d), "PROC SQL"), None => ("proc sql".into(), "PROC SQL") },
            ("proc_print", 1) => (format!("print {}", ds_key(&ts[0].args()[0])), "PROC PRINT"),
            _ => ("step".into(), "step"),
        }
    }

    fn source_comment(&self, t: &Term, b0: usize, b1: usize) -> Vec<String> {
        match t.functor() {
            ("empty", 0) => return vec![],
            ("datalines", 1) => {
                let n = t.args()[0].atom_text().lines().filter(|l| !l.trim().is_empty()).count();
                return vec![format!("#   datalines;  ... {} rows ...", n)];
            }
            _ => {}
        }
        if b1 > self.source.len() { return vec![]; }
        let slice = &self.source[b0..b1];
        let lines: Vec<String> = slice.lines().map(|l| l.trim().to_string()).filter(|l| !l.is_empty()).collect();
        reflow(lines).into_iter().map(|l| format!("#   {}", l)).collect()
    }

    fn find<'t>(ts: &[&'t Term], f: &str, ar: usize) -> Option<&'t Term> { ts.iter().find(|t| t.functor() == (f, ar)).copied() }

    fn format_lines(body: &[&Term]) -> Vec<String> {
        body.iter().filter(|t| t.functor() == ("format", 2))
            .map(|t| format!("display_format(\"{}\", \"{}.\")", lower(t.args()[0].atom_text()), t.args()[1].args()[0].atom_text())).collect()
    }

    fn chain_lines(v: &str, src: &str, steps: &[String]) -> Vec<String> {
        if steps.is_empty() || (steps.len() == 1 && !steps[0].contains('\n')) {
            return vec![format!("{} = {}{}", v, src, steps.join(""))];
        }
        let mut lines = vec![format!("{} = (", v), format!("    {}", src)];
        for s in steps { for part in s.split('\n') { lines.push(format!("    {}", part)); } }
        lines.push(")".into());
        lines
    }

    fn step_lines(&mut self, ts: &[&Term]) -> Option<Vec<String>> {
        match ts[0].functor() {
            ("libname", 2) => Some(vec![format!("libref(\"{}\", {})", ts[0].args()[0].atom_text(), py_path(ts[0].args()[1].args()[0].atom_text()))]),
            ("proc_print", 1) => Some(vec!["# (shown by show() at the end of the program)".into()]),
            ("proc_sql", 0) => {
                let mut lines = Vec::new();
                for t in &ts[1..] { if t.functor() == ("create_table_as", 2) { lines.extend(self.sql_lines(&t.args()[0], &t.args()[1])); } }
                Some(lines)
            }
            ("data", 1) => {
                let out = &ts[0].args()[0];
                let (k, v) = (ds_key(out), self.pyvar(out));
                let body = &ts[1..];
                let fmt_lines = Self::format_lines(body);
                if let (Some(input), Some(dl)) = (Self::find(body, "input", 1), Self::find(body, "datalines", 1)) {
                    let vars = input.args()[0].list();
                    let cols: Vec<String> = vars.iter().map(|x| match x.functor() {
                        ("cvar", 1) => format!("char(\"{}\")", lower(x.args()[0].atom_text())),
                        ("nvar", 2) => match some_arg(&x.args()[1]) {
                            Some(inf) => format!("date(\"{}\", informat=\"{}.\")", lower(x.args()[0].atom_text()), inf.args()[0].atom_text()),
                            None => format!("num(\"{}\")", lower(x.args()[0].atom_text())),
                        },
                        _ => panic!("input var {}", x),
                    }).collect();
                    self.schema.insert(k, vars.iter().map(|x| lower(x.args()[0].atom_text())).collect());
                    let mut lines = vec![format!("{} = read_datalines(", v), "    spark,".into(), format!("    schema=[{}],", cols.join(", ")), "    rows=\"\"\"".into()];
                    for r in dl.args()[0].atom_text().lines().map(|l| l.trim()).filter(|l| !l.is_empty()) { lines.push(format!("        {}", r)); }
                    lines.push("    \"\"\",".into()); lines.push(")".into());
                    lines.extend(fmt_lines);
                    return Some(lines);
                }
                if let (Some(its), Some(set)) = (body.iter().find(|t| t.functor() == ("if_then_set", 3) && crate::term::lit_num(&t.args()[1]) == Some(1.0)).copied(), Self::find(body, "set", 1)) {
                    let (ki, kl) = (ds_key(&set.args()[0]), ds_key(&its.args()[2]));
                    let mut cols: Vec<String> = Vec::new();
                    for dk in [&ki, &kl] { if let Some(cs) = self.schema.get(dk) { for c in cs { if !cols.contains(c) { cols.push(c.clone()); } } } }
                    self.schema.insert(k, cols);
                    let mut lines = vec![format!("{} = attach_first_row({}, {})", v, self.pyvar(&set.args()[0]), self.pyvar(&its.args()[2]))];
                    lines.extend(fmt_lines);
                    return Some(lines);
                }
                if let Some(set) = Self::find(body, "set", 1) {
                    let (ki, vi) = (ds_key(&set.args()[0]), self.pyvar(&set.args()[0]));
                    let mut steps = Vec::new();
                    for t in body.iter().filter(|t| t.functor() == ("subset_if", 1)) {
                        let mut pre = Vec::new();
                        let x = self.pe(&t.args()[0], Ctx::Top, &mut pre);
                        steps.push(format!(".filter({})", x));
                    }
                    if let Some(cols) = self.schema.get(&ki).cloned() { self.schema.insert(k, cols); }
                    let mut lines = Self::chain_lines(&v, &vi, &steps);
                    lines.extend(fmt_lines);
                    return Some(lines);
                }
                if let Some(merge) = Self::find(body, "merge", 1) {
                    let srcs = merge.args()[0].list();
                    let keys: Vec<String> = Self::find(body, "by", 1).map(|by| by.list_keys()).unwrap_or_default();
                    let src_txts: Vec<String> = srcs.iter().map(|s| format!("(\"{}\", {})", ds_key(&s.args()[0]), self.pyvar(&s.args()[0]))).collect();
                    let key_qs: Vec<String> = keys.iter().map(|kk| format!("\"{}\"", kk)).collect();
                    let mut lines = Vec::new();
                    let mut all_cols: Vec<String> = Vec::new();
                    for s in srcs {
                        let dk = ds_key(&s.args()[0]);
                        if let Some(cols) = self.schema.get(&dk) {
                            for key in &keys {
                                if !cols.contains(key) {
                                    lines.push(format!("# WARNING  BY variable {} is not on {} (columns: {}).", key, dk, cols.join(", ")));
                                    lines.push(format!("#          SAS logs an ERROR and leaves {} with 0 observations; merge_by does the same.", k));
                                }
                            }
                            for c in cols { if !all_cols.contains(c) { all_cols.push(c.clone()); } }
                        }
                    }
                    lines.push(format!("{} = merge_by(", v));
                    lines.push(format!("    [{}],", src_txts.join(", ")));
                    lines.push(format!("    by=[{}],", key_qs.join(", ")));
                    lines.push(")".into());
                    self.schema.insert(k, all_cols);
                    return Some(lines);
                }
                None
            }
            _ => None,
        }
    }

    // ------------------------------------------------------------ PROC SQL
    fn sql_lines(&mut self, out: &Term, sel: &Term) -> Vec<String> {
        let (k, v) = (ds_key(out), self.pyvar(out));
    // M3a defect 2 (2026-09-10): UNION ALL. `select_stmt(Cores, Order, Limit)` has
    // held a LIST of select_cores since task 5b; this took `cores[0]` and emitted the
    // first branch only, so 18_dashboard_mart.sas and 25_final_pack.sas silently lost
    // three of their four source tables. (Prolog's own sql_lines/3 matched `[Core]`
    // and so emitted nothing at all for those statements — both are fixed, Prolog
    // first, in the previous commit.)
    //
    // `.union` and not `.unionByName`: SQL UNION ALL is POSITIONAL — column by
    // column, which is exactly `DataFrame.union`. Only the first branch of
    // 18_dashboard_mart names its columns, so by-name matching would raise rather
    // than stack rows. The FIRST branch sets the output schema, the rule
    // lineage.rs's select_lineage already follows (task 5d's set_schema flag).
        let cores = sel.args()[0].list();
        let core = &cores[0];
        let mut pre = Vec::new();
        let (src, mut steps) = self.core_parts(core, &mut pre);
        // one ".union(<branch>)" step per extra branch, each branch flattened to a
        // single expression the way from_txt's subquery arm already flattens a core
        for c in &cores[1..] {
            let (s2, st2) = self.core_parts(c, &mut pre);
            steps.push(format!(".union({}{})", s2, st2.join("")));
        }
        if let Some(keys) = some_arg(&sel.args()[1]) {
            let kts: Vec<String> = keys.list().iter().map(|kk| self.key_txt0(kk)).collect();
            steps.push(format!(".orderBy({})", kts.join(", ")));
        }
        let cols = self.core_out_cols(core);
        self.schema.insert(k, cols);
        pre.extend(Self::chain_lines(&v, &src, &steps));
        pre
    }

    // task 5c: a[2] (`joins`) is a Prolog LIST now (was `some(J)|none`) — one
    // ".join(...)" step per item, source order; still hardcoded "inner" (this
    // pre-existing simplification is unchanged by this task). task 5d: a
    // join whose own arity is 1 (cross_join(Src): no ON) renders
    // ".crossJoin(src)" instead — arity decides this, not the functor name.
    fn core_parts(&mut self, core: &Term, pre: &mut Vec<String>) -> (String, Vec<String>) {
        let a = core.args();
        let src = self.from_txt(&a[1], pre);
        let mut steps = Vec::new();
        for j in a[2].list() {
            let jt = self.from_txt(&j.args()[0], pre);
            if j.args().len() > 1 {
                let on = self.pe(&j.args()[1], Ctx::Top, pre);
                steps.push(format!(".join({}, {}, \"inner\")", jt, on));
            } else {
                steps.push(format!(".crossJoin({})", jt));
            }
        }
        if let Some(w) = some_arg(&a[3]) { let x = self.pe(w, Ctx::Top, pre); steps.push(format!(".filter({})", x)); }
        steps.extend(self.select_steps(a[0].list(), &a[4], pre));
        if let Some(h) = some_arg(&a[5]) { let x = self.pe(h, Ctx::Top, pre); steps.push(format!(".filter({})", x)); }
        (src, steps)
    }

    fn from_txt(&mut self, from: &Term, pre: &mut Vec<String>) -> String {
        match from.functor() {
            ("table", 2) => {
                let v = self.pyvar(&from.args()[0]);
                match some_arg(&from.args()[1]) { Some(al) => format!("{}.alias(\"{}\")", v, lower(al.atom_text())), None => v }
            }
            ("subquery", 2) => {
                let (s, steps) = self.core_parts(&from.args()[0], pre);
                match some_arg(&from.args()[1]) {
                    Some(al) => format!("({}{}).alias(\"{}\")", s, steps.join(""), lower(al.atom_text())),
                    None => format!("({}{})", s, steps.join("")),
                }
            }
            _ => panic!("from {}", from),
        }
    }

    fn call_lines(name: &str, items: &[String]) -> String {
        if items.len() == 1 { return format!(".{}({})", name, items[0]); }
        let body: Vec<String> = items.iter().map(|i| format!("    {},", i)).collect();
        format!(".{}(\n{}\n)", name, body.join("\n"))
    }

    fn select_steps(&mut self, cols: &[Term], group: &Term, pre: &mut Vec<String>) -> Vec<String> {
        match some_arg(group) {
            None => {
                // task 5d: NOT widened to star/1 (a qualified `a.*`) — unlike the
                // bare star/0 fast path (implicit "pass every column through" is
                // sound when there is no join, or the whole joined row equals the
                // whole source anyway), skipping .select() entirely for a lone
                // `a.*` would pass through every JOINed column, not just `a`'s —
                // wrong the moment a join is present. No file in this corpus hits
                // this (a lone single-item `a.*` projection list), so left as the
                // general `sel_item` path below, which renders it correctly via
                // `"alias.*"` regardless.
                if cols.len() == 1 && cols[0].args()[0].functor() == ("star", 0) && cols[0].args()[1].functor() == ("none", 0) { return vec![]; }
                if cols.iter().any(|p| is_agg(&p.args()[0])) {
                    let items: Vec<String> = cols.iter().map(|p| self.sel_item(p, pre)).collect();
                    return vec![Self::call_lines("agg", &items)];
                }
                let all_plain = cols.iter().all(|p| p.args()[0].functor() == ("col", 1) && p.args()[1].functor() == ("none", 0));
                let items: Vec<String> = cols.iter().map(|p| self.sel_item(p, pre)).collect();
                if all_plain { vec![format!(".select({})", items.join(", "))] } else { vec![Self::call_lines("select", &items)] }
            }
            Some(keys) => {
                let mut kts = Vec::new();
                for key in keys.list() {
                    let alias = cols.iter().find(|p| some_arg(&p.args()[1]).is_some() && p.args()[0].lower_term() == key.lower_term())
                        .map(|p| lower(some_arg(&p.args()[1]).unwrap().atom_text()));
                    kts.push(match alias {
                        Some(a) => { let mut d = Vec::new(); format!("{}.alias(\"{}\")", self.pe(key, Ctx::Sub, &mut d), a) }
                        None => self.key_txt0(key),
                    });
                }
                let items: Vec<String> = cols.iter().filter(|p| is_agg(&p.args()[0])).map(|p| self.sel_item(p, pre)).collect();
                vec![format!(".groupBy({})", kts.join(", ")), Self::call_lines("agg", &items)]
            }
        }
    }

    fn key_txt0(&mut self, key: &Term) -> String {
        if key.functor() == ("col", 1) { return format!("\"{}\"", lower(key.args()[0].atom_text())); }
        let mut d = Vec::new();
        self.pe(key, Ctx::Sub, &mut d)
    }

    fn sel_item(&mut self, p: &Term, pre: &mut Vec<String>) -> String {
        let (e, alias) = (&p.args()[0], &p.args()[1]);
        match some_arg(alias) {
            None => match e.functor() {
                ("col", 1) => format!("\"{}\"", lower(e.args()[0].atom_text())),
                ("star", 0) => "\"*\"".into(),
                // task 5d: a qualified star (`a.*`) — the string form Spark's
                // own .select()/.agg() accepts to expand every column of an
                // aliased source, same idea as the bare "*" arm just above.
                ("star", 1) => format!("\"{}.*\"", lower(e.args()[0].atom_text())),
                _ => self.pe(e, Ctx::Sub, pre),
            },
            Some(a) => { let x = self.pe(e, Ctx::Sub, pre); format!("{}.alias(\"{}\")", x, lower(a.atom_text())) }
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

    // ------------------------------------------------------------ expressions
    fn wrap(&mut self, e: &Term, pre: &mut Vec<String>) -> String {
        let x = self.pe(e, Ctx::Sub, pre);
        if is_binop(e) { format!("({})", x) } else { x }
    }

    fn scalar_name(&mut self, core: &Term) -> String {
        let cols = core.args()[0].list();
        let base = match cols.first() {
            Some(p) if some_arg(&p.args()[1]).is_some() => format!("{}_value", lower(some_arg(&p.args()[1]).unwrap().atom_text())),
            Some(p) if p.args()[0].functor() == ("col", 1) => format!("{}_value", lower(p.args()[0].args()[0].atom_text())),
            _ => "subquery_value".into(),
        };
        let mut name = base.clone();
        let mut i = 2;
        while self.scalar_names.contains(&name) { name = format!("{}_{}", base, i); i += 1; }
        self.scalar_names.insert(name.clone());
        name
    }

    pub fn pe(&mut self, t: &Term, ctx: Ctx, pre: &mut Vec<String>) -> String {
        let (f, ar) = t.functor();
        let a = t.args();
        match (f, ar) {
            ("col", 1) => if ctx == Ctx::Arg { format!("\"{}\"", lower(a[0].atom_text())) } else { format!("F.col(\"{}\")", lower(a[0].atom_text())) },
            ("col", 2) => format!("F.col(\"{}.{}\")", lower(a[0].atom_text()), lower(a[1].atom_text())),
            ("lit", 1) | ("lit", 2) => if ctx == Ctx::Top { format!("F.lit({})", py_lit(&a[0])) } else { py_lit(&a[0]) },
            ("star", 0) => "\"*\"".into(),
            ("star", 1) => format!("\"{}.*\"", lower(a[0].atom_text())),
            ("paren", 1) => format!("({})", self.pe(&a[0], Ctx::Sub, pre)),
            ("neg", 1) => format!("-{}", self.wrap(&a[0], pre)),
            ("not", 1) => format!("~{}", self.wrap(&a[0], pre)),
            ("cat", 2) => { let x = self.pe(&a[0], Ctx::Arg, pre); let y = self.pe(&a[1], Ctx::Arg, pre); format!("F.concat({}, {})", x, y) }
            ("in", 2) => {
                let x = self.wrap(&a[0], pre);
                let items: Vec<String> = a[1].list().iter().map(|l| py_lit(&l.args()[0])).collect();
                format!("{}.isin([{}])", x, items.join(", "))
            }
            ("subquery_expr", 1) => {
                let core = &a[0];
                let name = self.scalar_name(core);
                let ca = core.args();
                // task 5c: index 2 (`joins`) is a LIST now — "no join" is an empty
                // list, not the atom `none`; indices 3/4/5 (WHERE/GROUP BY/HAVING)
                // are unaffected and still check against `none`. Missing this would
                // not panic — ca[2].functor() on a List returns ("", 0), which never
                // equals ("none", 0), so this fast path would just silently stop
                // firing for every 0-join scalar subquery (see codegen/
                // sas_pyspark_pretty.pl's own version of this same guard).
                let simple = ca[0].list().len() == 1 && ca[0].list()[0].args()[0].functor() == ("col", 1)
                    && ca[1].functor() == ("table", 2) && ca[1].args()[1].functor() == ("none", 0)
                    && ca[2].list().is_empty()
                    && [3, 4, 5].iter().all(|i| ca[*i].functor() == ("none", 0));
                if simple {
                    let dv = self.pyvar(&ca[1].args()[0]);
                    let c = lower(ca[0].list()[0].args()[0].args()[0].atom_text());
                    pre.push(format!("{} = scalar({}, \"{}\")", name, dv, c));
                } else {
                    let (s, steps) = self.core_parts(core, pre);
                    pre.push(format!("{} = scalar({}{})", name, s, steps.join("")));
                }
                name
            }
            // task 5c: COUNT(DISTINCT x) -> F.countDistinct(x) — ahead of the
            // generic ("call", 2) arm below, mirrors emit.rs's px() and
            // codegen/sas_pyspark_pretty.pl's pe/5.
            ("call", 2) if lower(a[0].atom_text()) == "count" && a[1].list().len() == 1 && a[1].list()[0].functor() == ("distinct", 1) => {
                let inner = &a[1].list()[0].args()[0];
                format!("F.countDistinct({})", self.pe(inner, Ctx::Arg, pre))
            }
            ("call", 2) => {
                let py = sas_fn(&lower(a[0].atom_text()));
                let xs: Vec<String> = a[1].list().iter().map(|x| self.pe(x, Ctx::Arg, pre)).collect();
                format!("F.{}({})", py, xs.join(", "))
            }
            (op, 2) if is_binop(t) => {
                let sym = match op { "mul" => "*", "div" => "/", "add" => "+", "sub" => "-", "eq" => "==", "ne" => "!=", "lt" => "<", "le" => "<=", "gt" => ">", "ge" => ">=", "and" => "&", _ => "|" };
                let x = self.wrap(&a[0], pre); let y = self.wrap(&a[1], pre);
                format!("{} {} {}", x, sym, y)
            }
            _ => panic!("no pretty rule for expression {}", t),
        }
    }
}

#[derive(Clone, Copy, PartialEq)]
pub enum Ctx { Top, Sub, Arg }

trait ListKeys { fn list_keys(&self) -> Vec<String>; }
impl ListKeys for Term {
    fn list_keys(&self) -> Vec<String> { self.args()[0].list().iter().map(|k| k.atom_text().to_string()).collect() }
}
