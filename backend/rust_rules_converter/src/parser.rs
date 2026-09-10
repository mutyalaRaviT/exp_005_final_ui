//! parser.rs — the pyDSL interpreted as a backtracking grammar, both ways.
//!
//! FOLD:  tokens -> Term. Every piece returns ALL its alternatives, in the
//! same order gen_prolog.py's DCG clauses try them (present-before-absent for
//! opt, longest-first for lists, spec order for statements/rules/forms), and
//! the first alternative that consumes the whole statement wins — the same
//! answer Prolog's depth-first search gives.
//! UNFOLD: Term -> canonical token texts, walking the same parts.
use crate::spec::*;
use crate::term::{float_text, Term};
use crate::tokenise::Tok;

type Alts = Vec<(usize, Vec<Term>)>;

// exp_42 2026-09-07: memo — every (ladder level, position) is parsed once. The
// all-alternatives search is exponential on a PySpark method chain without it
// (6 s per file); with it, milliseconds. Prolog's DCG never pays this because
// it stops at the first solution.
pub struct Parser<'a> { pub spec: &'a Spec, toks: &'a [Tok],
    memo: std::cell::RefCell<std::collections::HashMap<(isize, usize), Vec<(usize, Term)>>> }

fn raw_body(text: &str) -> String {
    match text.find(';') { Some(i) => text[i + 1..].trim().to_string(), None => text.trim().to_string() }
}

fn unquote_plain(raw: &str) -> String {
    let delim = raw.chars().next().unwrap();
    let body: Vec<char> = raw.chars().skip(1).collect();
    let mut out = String::new();
    let mut i = 0;
    while i + 1 < body.len() {
        if body[i] == delim && body[i + 1] == delim { out.push(delim); i += 2; } else { out.push(body[i]); i += 1; }
    }
    out
}

fn unquote_escaped(raw: &str, double_delim: bool) -> String {
    let delim = raw.chars().next().unwrap();
    let body: Vec<char> = raw.chars().skip(1).collect();
    let mut out = String::new();
    let mut i = 0;
    while i + 1 < body.len() {
        if double_delim && body[i] == delim && body[i + 1] == delim { out.push(delim); i += 2; }
        else if body[i] == '\\' && i + 2 < body.len() + 1 { out.push(body[i + 1]); i += 2; }
        else { out.push(body[i]); i += 1; }
    }
    out
}

pub fn quote_plain(delim: char, v: &str) -> String {
    let mut s = String::new(); s.push(delim);
    for c in v.chars() { if c == delim { s.push(delim); } s.push(c); }
    s.push(delim); s
}

fn quote_escaped(delim: char, v: &str) -> String {
    let mut s = String::new(); s.push(delim);
    for c in v.chars() { if c == delim || c == '\\' { s.push('\\'); } s.push(c); }
    s.push(delim); s
}

fn is_word(s: &str) -> bool {
    let mut cs = s.chars();
    matches!(cs.next(), Some(c) if c.is_ascii_alphabetic() || c == '_') && cs.all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-')
}

impl<'a> Parser<'a> {
    pub fn new(spec: &'a Spec, toks: &'a [Tok]) -> Self { Parser { spec, toks, memo: Default::default() } }

    // ------------------------------------------------------------ fold
    pub fn fold(&self) -> Option<Term> {
        let n = self.toks.len();
        let end = &self.spec.statement_end;
        for st in &self.spec.statements {
            if st.assign { continue; } // not used by SAS
            for (pos, args) in self.parts(&st.parts, 0) {
                // exp_42 2026-09-07: an empty statement_end (PySpark: the newline is the
                // end, see eos_kinds) means the statement is done when every token is consumed —
                // the same rule gen_prolog.py applies when stmt_end is None.
                let done = if st.is_raw() || end.is_empty() { pos == n }
                           else { pos + 1 == n && self.toks[pos].kind == "symbol" && end.iter().any(|e| *e == self.toks[pos].text) };
                if done { return Some(Term::compound(&st.name, args)); }
            }
        }
        None
    }

    fn tok(&self, pos: usize) -> Option<&Tok> { self.toks.get(pos) }

    fn match_kw_or_sym(&self, spelling: &str, pos: usize) -> bool {
        match self.tok(pos) {
            None => false,
            Some(t) => if is_word(spelling) { t.kind == "keyword" && t.text.to_lowercase() == spelling.to_lowercase() }
                       else { t.kind == "symbol" && t.text == spelling },
        }
    }

    fn parts(&self, parts: &[Piece], pos: usize) -> Alts {
        let mut results: Alts = vec![(pos, vec![])];
        for p in parts {
            let mut next: Alts = Vec::new();
            for (p1, acc) in &results {
                for (p2, val) in self.piece(p, *p1) {
                    let mut acc2 = acc.clone();
                    if let Some(v) = val { acc2.push(v); }
                    next.push((p2, acc2));
                }
            }
            results = next;
            if results.is_empty() { break; }
        }
        results
    }

    fn piece(&self, p: &Piece, pos: usize) -> Vec<(usize, Option<Term>)> {
        match p {
            Piece::Kw { text } | Piece::Sym { text } =>
                if self.match_kw_or_sym(text, pos) { vec![(pos + 1, None)] } else { vec![] },
            Piece::Cap { kind, .. } => self.cap(kind, pos),
            Piece::Group { functor, parts } =>
                self.parts(parts, pos).into_iter().map(|(p2, args)| (p2, Some(Term::compound(functor, args)))).collect(),
            Piece::List { parts, min, sep, .. } => {
                let mut alts: Vec<(usize, Option<Term>)> = self.list_alts(parts, sep, pos).into_iter()
                    .map(|(p2, items)| (p2, Some(Term::List(items)))).collect();
                if *min == 0 { alts.push((pos, Some(Term::List(vec![])))); }
                alts
            }
            Piece::Choice { options, default, .. } => {
                let mut alts = Vec::new();
                for (src, val) in options {
                    if self.match_kw_or_sym(src, pos) { alts.push((pos + 1, Some(Term::atom(val)))); }
                }
                if let Some(d) = default { alts.push((pos, Some(Term::atom(d)))); }
                alts
            }
            Piece::Opt { parts } => {
                let mut alts: Vec<(usize, Option<Term>)> = self.parts(parts, pos).into_iter()
                    .map(|(p2, args)| { assert_eq!(args.len(), 1, "opt must carry one value"); (p2, Some(Term::compound("some", args))) })
                    .collect();
                alts.push((pos, Some(Term::atom("none"))));
                alts
            }
            Piece::Rule { name, .. } => self.rule(name, pos).into_iter().map(|(p2, t)| (p2, Some(t))).collect(),
        }
    }

    fn list_alts(&self, parts: &[Piece], sep: &[Piece], pos: usize) -> Alts {
        let mut out: Alts = Vec::new();
        for (p1, first) in self.parts(parts, pos) {
            assert_eq!(first.len(), 1, "a list item must carry one value");
            for (p2, rest) in self.list_rest(parts, sep, p1) {
                let mut items = first.clone(); items.extend(rest);
                out.push((p2, items));
            }
        }
        out
    }

    fn list_rest(&self, parts: &[Piece], sep: &[Piece], pos: usize) -> Alts {
        let mut out: Alts = Vec::new();
        for (p1, _) in self.parts(sep, pos) {
            for (p2, item) in self.parts(parts, p1) {
                for (p3, rest) in self.list_rest(parts, sep, p2) {
                    let mut items = item.clone(); items.extend(rest);
                    out.push((p3, items));
                }
            }
        }
        out.push((pos, vec![]));
        out
    }

    fn rule(&self, name: &str, pos: usize) -> Vec<(usize, Term)> {
        let alts = self.spec.rules.get(name).unwrap_or_else(|| panic!("no rule {}", name));
        let mut out = Vec::new();
        for ra in alts {
            for (p2, args) in self.parts(&ra.parts, pos) {
                out.push((p2, Term::compound(&ra.functor, args)));
            }
        }
        out
    }

    fn cap(&self, kind: &str, pos: usize) -> Vec<(usize, Option<Term>)> {
        let t = match self.tok(pos) { Some(t) => t, None => return vec![] };
        match kind {
            "ref" => if t.kind == "word" { vec![(pos + 1, Some(Term::compound("rel", vec![Term::atom(&t.text)])))] } else { vec![] },
            "ident" => if t.kind == "word" { vec![(pos + 1, Some(Term::atom(&t.text)))] } else { vec![] },
            "typename" => if t.kind == "word" || t.kind == "keyword" { vec![(pos + 1, Some(Term::atom(&t.text)))] } else { vec![] },
            "expr" => self.expr(pos).into_iter().map(|(p2, e)| (p2, Some(e))).collect(),
            k if k.starts_with("raw:") => {
                let tk = &k[4..];
                if t.kind == tk { vec![(pos + 1, Some(Term::atom(&raw_body(&t.text))))] } else { vec![] }
            }
            k => panic!("unknown cap kind {}", k),
        }
    }

    // ------------------------------------------------- expression ladder
    pub fn expr(&self, pos: usize) -> Vec<(usize, Term)> {
        let top = self.spec.ladder.len() as isize - 1;
        self.level(top, pos)
    }

    fn level(&self, i: isize, pos: usize) -> Vec<(usize, Term)> {
        if let Some(hit) = self.memo.borrow().get(&(i, pos)) { return hit.clone(); }
        let out = self.level_uncached(i, pos);
        self.memo.borrow_mut().insert((i, pos), out.clone());
        out
    }

    fn level_uncached(&self, i: isize, pos: usize) -> Vec<(usize, Term)> {
        if i < 0 { return self.prim(pos); }
        let lv = &self.spec.ladder[i as usize];
        let is_prefix = lv.ops.iter().all(|o| o.kind == "prefix");
        let mut out = Vec::new();
        if is_prefix {
            for op in &lv.ops {
                if self.match_kw_or_sym(&op.spelling, pos) {
                    for (p2, e) in self.level(i, pos + 1) { out.push((p2, Term::compound(&op.functor, vec![e]))); }
                }
            }
            out.extend(self.level(i - 1, pos));
        } else if lv.assoc == "left" {
            for (p1, l0) in self.level(i - 1, pos) {
                out.extend(self.level_rest(i, l0, p1));
            }
        } else {
            for op in &lv.ops {
                for (p1, a) in self.level(i - 1, pos) {
                    if !self.match_kw_or_sym(&op.spelling, p1) { continue; }
                    if op.kind == "list_rhs" {
                        if self.match_kw_or_sym("(", p1 + 1) {
                            for (p2, items) in self.args(p1 + 2) {
                                if self.match_kw_or_sym(")", p2) {
                                    out.push((p2 + 1, Term::compound(&op.functor, vec![a.clone(), Term::List(items)])));
                                }
                            }
                        }
                    } else {
                        for (p2, b) in self.level(i - 1, p1 + 1) {
                            out.push((p2, Term::compound(&op.functor, vec![a.clone(), b])));
                        }
                    }
                }
            }
            out.extend(self.level(i - 1, pos));
        }
        out
    }

    fn level_rest(&self, i: isize, acc: Term, pos: usize) -> Vec<(usize, Term)> {
        let lv = &self.spec.ladder[i as usize];
        let mut out = Vec::new();
        for op in &lv.ops {
            if self.match_kw_or_sym(&op.spelling, pos) {
                for (p2, r) in self.level(i - 1, pos + 1) {
                    out.extend(self.level_rest(i, Term::compound(&op.functor, vec![acc.clone(), r]), p2));
                }
            }
        }
        out.push((pos, acc));
        out
    }

    fn args(&self, pos: usize) -> Alts {
        let mut out: Alts = Vec::new();
        for (p1, a) in self.expr(pos) {
            for (p2, rest) in self.args_rest(p1) {
                let mut items = vec![a.clone()]; items.extend(rest);
                out.push((p2, items));
            }
        }
        out.push((pos, vec![]));
        out
    }

    fn args_rest(&self, pos: usize) -> Alts {
        let mut out: Alts = Vec::new();
        if self.match_kw_or_sym(",", pos) {
            for (p1, a) in self.expr(pos + 1) {
                for (p2, rest) in self.args_rest(p1) {
                    let mut items = vec![a.clone()]; items.extend(rest);
                    out.push((p2, items));
                }
            }
        }
        out.push((pos, vec![]));
        out
    }

    fn prim(&self, pos: usize) -> Vec<(usize, Term)> {
        let mut out = Vec::new();
        for f in &self.spec.forms {
            match f {
                Form::Parts { name, parts } => {
                    for (p2, args) in self.parts(parts, pos) { out.push((p2, Term::compound(name, args))); }
                }
                Form::Shape { name, shape } => match shape.as_str() {
                    "( E )" => if self.match_kw_or_sym("(", pos) {
                        for (p2, e) in self.expr(pos + 1) {
                            if self.match_kw_or_sym(")", p2) { out.push((p2 + 1, Term::compound(name, vec![e]))); }
                        }
                    },
                    "ID ( ARGS )" => if let Some(t) = self.tok(pos) {
                        if (t.kind == "word" || t.kind == "keyword") && self.match_kw_or_sym("(", pos + 1) {
                            for (p2, items) in self.args(pos + 2) {
                                if self.match_kw_or_sym(")", p2) {
                                    out.push((p2 + 1, Term::compound(name, vec![Term::atom(&t.text), Term::List(items)])));
                                }
                            }
                        }
                    },
                    "ID . ID (canonical)" | "ID . ID" => if let (Some(a), Some(b)) = (self.tok(pos), self.tok(pos + 2)) {
                        if a.kind == "word" && b.kind == "word" && self.match_kw_or_sym(".", pos + 1) {
                            out.push((pos + 3, Term::compound(name, vec![Term::atom(&a.text), Term::atom(&b.text)])));
                        }
                    },
                    other => panic!("form shape not supported by the Rust engine: {}", other),
                },
                Form::Rule { name, rule } => if self.match_kw_or_sym("(", pos) {
                    for (p2, t) in self.rule(rule, pos + 1) {
                        if self.match_kw_or_sym(")", p2) { out.push((p2 + 1, Term::compound(name, vec![t]))); }
                    }
                },
            }
        }
        if let Some(t) = self.tok(pos) {
            for lf in &self.spec.expr_leaves {
                match lf.name.as_str() {
                    // M3a defect 1: keep_lexeme -> lit(Value, Text), so print_expr can write the
                    // source spelling back (`0.40`, not the canonical `0.4`).
                    "number" => if t.kind == "number" {
                        let mut args = vec![Term::number(&t.text)];
                        if lf.keep_lexeme { args.push(Term::atom(&t.text)); }
                        out.push((pos + 1, Term::compound("lit", args)));
                    },
                    "string" => if t.kind == "string" {
                        let v = if lf.backslash_escape { unquote_escaped(&t.text, lf.double_delim) } else { unquote_plain(&t.text) };
                        out.push((pos + 1, Term::compound("lit", vec![Term::atom(&v)])));
                    },
                    "word" => if t.kind == "word" { out.push((pos + 1, Term::compound("col", vec![Term::atom(&t.text)]))); },
                    other => panic!("expr leaf not supported: {}", other),
                }
            }
        }
        out
    }
}

// ================================================================ unfold
pub struct Printer<'a> { pub spec: &'a Spec }

impl<'a> Printer<'a> {
    pub fn print_stmt(&self, t: &Term) -> Option<Vec<String>> {
        let (f, ar) = t.functor();
        for st in &self.spec.statements {
            if st.name != f { continue; }
            if let Some(mut texts) = self.print_parts(&st.parts, t.args()) {
                if ar == 0 && !st.parts.iter().any(|p| !matches!(p, Piece::Kw { .. } | Piece::Sym { .. })) || ar > 0 || st.parts.is_empty() {
                    // exp_42 2026-09-07: no trailing symbol when the spec has none (PySpark)
                    if !st.is_raw() && !self.spec.statement_end.is_empty() { texts.push(self.spec.statement_end[0].clone()); }
                    return Some(texts);
                }
            }
        }
        None
    }

    /// walk `parts`, consuming one term argument per value-carrying piece
    fn print_parts(&self, parts: &[Piece], args: &[Term]) -> Option<Vec<String>> {
        let mut out = Vec::new();
        let mut i = 0;
        for p in parts {
            match p {
                Piece::Kw { text } => out.push(text.to_lowercase()),
                Piece::Sym { text } => out.push(text.clone()),
                _ => {
                    let a = args.get(i)?; i += 1;
                    out.extend(self.print_piece(p, a)?);
                }
            }
        }
        if i != args.len() { return None; }
        Some(out)
    }

    fn print_piece(&self, p: &Piece, a: &Term) -> Option<Vec<String>> {
        match p {
            Piece::Cap { kind, .. } => match kind.as_str() {
                "ref" => Some(vec![a.args()[0].atom_text().to_string()]),
                "ident" | "typename" => Some(vec![a.atom_text().to_string()]),
                "expr" => Some(self.print_expr(a, 0)),
                k if k.starts_with("raw:") => Some(vec![format!("{};\n{}\n", &k[4..], a.atom_text())]),
                _ => None,
            },
            Piece::Group { functor, parts } => {
                let (f, _) = a.functor();
                if f != functor { return None; }
                self.print_parts(parts, a.args())
            }
            Piece::List { parts, sep, .. } => {
                let mut out = Vec::new();
                for (k, item) in a.list().iter().enumerate() {
                    if k > 0 { for s in sep { out.extend(self.print_parts(std::slice::from_ref(s), &[])?); } }
                    out.extend(self.print_parts(parts, std::slice::from_ref(item))?);
                }
                Some(out)
            }
            Piece::Choice { options, .. } => {
                let v = a.atom_text();
                options.iter().find(|(_, val)| val == v).map(|(src, _)| vec![src.to_lowercase()])
            }
            Piece::Opt { parts } => match a.functor() {
                ("some", 1) => self.print_parts(parts, a.args()),
                ("none", 0) => Some(vec![]),
                _ => None,
            },
            Piece::Rule { name, .. } => self.print_rule(name, a),
            Piece::Kw { .. } | Piece::Sym { .. } => unreachable!(),
        }
    }

    fn print_rule(&self, name: &str, a: &Term) -> Option<Vec<String>> {
        let (f, _) = a.functor();
        for ra in self.spec.rules.get(name)? {
            if ra.functor != f { continue; }
            if let Some(texts) = self.print_parts(&ra.parts, a.args()) { return Some(texts); }
        }
        None
    }

    pub fn print_expr(&self, t: &Term, min_prec: usize) -> Vec<String> {
        let (own, inner) = self.expr_own(t);
        if own >= min_prec { inner } else {
            let mut v = vec!["(".to_string()]; v.extend(inner); v.push(")".to_string()); v
        }
    }

    fn expr_own(&self, t: &Term) -> (usize, Vec<String>) {
        let n = self.spec.ladder.len();
        let (f, ar) = t.functor();
        // ladder operators, tightest level = highest precedence
        for (i, lv) in self.spec.ladder.iter().enumerate() {
            let p = (n - i) * 10;
            let is_prefix = lv.ops.iter().all(|o| o.kind == "prefix");
            for op in &lv.ops {
                if op.functor != f { continue; }
                let text = if is_word(&op.spelling) { op.spelling.to_lowercase() } else { op.spelling.clone() };
                if is_prefix && ar == 1 {
                    let mut v = vec![text]; v.extend(self.print_expr(&t.args()[0], p)); return (p, v);
                }
                if ar != 2 { continue; }
                let (a, b) = (&t.args()[0], &t.args()[1]);
                let mut v = Vec::new();
                match (lv.assoc.as_str(), op.kind.as_str()) {
                    ("left", _) => { v.extend(self.print_expr(a, p)); v.push(text); v.extend(self.print_expr(b, p + 1)); }
                    (_, "list_rhs") => {
                        v.extend(self.print_expr(a, p + 1)); v.push(text); v.push("(".into());
                        v.extend(self.print_args(b.list())); v.push(")".into());
                    }
                    _ => { v.extend(self.print_expr(a, p + 1)); v.push(text); v.extend(self.print_expr(b, p + 1)); }
                }
                return (p, v);
            }
        }
        // forms
        for form in &self.spec.forms {
            match form {
                Form::Parts { name, parts } if name == f => {
                    if let Some(v) = self.print_parts(parts, t.args()) { return (100, v); }
                }
                Form::Shape { name, shape } if name == f => match (shape.as_str(), ar) {
                    ("( E )", 1) => { let mut v = vec!["(".to_string()]; v.extend(self.print_expr(&t.args()[0], 0)); v.push(")".into()); return (100, v); }
                    ("ID ( ARGS )", 2) => {
                        let mut v = vec![t.args()[0].atom_text().to_string(), "(".into()];
                        v.extend(self.print_args(t.args()[1].list())); v.push(")".into()); return (100, v);
                    }
                    ("ID . ID (canonical)", 2) => return (100, vec![t.args()[0].atom_text().into(), ".".into(), t.args()[1].atom_text().into()]),
                    _ => {}
                },
                Form::Rule { name, rule } if name == f && ar == 1 => {
                    if let Some(inner) = self.print_rule(rule, &t.args()[0]) {
                        let mut v = vec!["(".to_string()]; v.extend(inner); v.push(")".into()); return (100, v);
                    }
                }
                _ => {}
            }
        }
        // leaves
        match (f, ar) {
            // M3a defect 1: lit/2 prints its stored lexeme verbatim — that IS the fix.
            ("lit", 2) if t.args()[0].is_number() => return (100, vec![t.args()[1].atom_text().to_string()]),
            ("lit", 1) => match &t.args()[0] {
                Term::Int(i) => return (100, vec![i.to_string()]),
                Term::Float(x) => return (100, vec![float_text(*x)]),
                Term::Atom(s) => {
                    let lf = self.spec.expr_leaves.iter().find(|l| l.name == "string").expect("string leaf");
                    return (100, vec![if lf.backslash_escape { quote_escaped('\'', s) } else { quote_plain('\'', s) }]);
                }
                _ => {}
            },
            ("col", 1) => return (100, vec![t.args()[0].atom_text().to_string()]),
            _ => {}
        }
        panic!("cannot print expression {}", t)
    }

    fn print_args(&self, items: &[Term]) -> Vec<String> {
        let mut v = Vec::new();
        for (i, a) in items.iter().enumerate() {
            if i > 0 { v.push(",".into()); }
            v.extend(self.print_expr(a, 0));
        }
        v
    }
}
