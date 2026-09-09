//! term.rs — the node/4 Term, printed exactly like SWI-Prolog's writeq/2 so
//! the Rust and Prolog node/4 files diff byte for byte.
use std::fmt;

#[derive(Clone, Debug, PartialEq)]
pub enum Term {
    Atom(String),
    Int(i64),
    Float(f64),
    Compound(String, Vec<Term>),
    List(Vec<Term>),
}

impl Term {
    pub fn atom(s: &str) -> Term { Term::Atom(s.to_string()) }
    pub fn compound(f: &str, args: Vec<Term>) -> Term {
        if args.is_empty() { Term::Atom(f.to_string()) } else { Term::Compound(f.to_string(), args) }
    }
    pub fn number(text: &str) -> Term {
        if let Ok(i) = text.parse::<i64>() { return Term::Int(i); }
        Term::Float(text.parse::<f64>().expect("number token"))
    }
    /// (functor, arity) — an atom is functor/0
    pub fn functor(&self) -> (&str, usize) {
        match self {
            Term::Atom(a) => (a.as_str(), 0),
            Term::Compound(f, args) => (f.as_str(), args.len()),
            _ => ("", 0),
        }
    }
    pub fn args(&self) -> &[Term] {
        match self { Term::Compound(_, a) => a, _ => &[] }
    }
    pub fn atom_text(&self) -> &str {
        match self { Term::Atom(a) => a, _ => panic!("not an atom: {}", self) }
    }
    pub fn list(&self) -> &[Term] {
        match self { Term::List(items) => items, _ => panic!("not a list: {}", self) }
    }
    pub fn is_number(&self) -> bool { matches!(self, Term::Int(_) | Term::Float(_)) }
    /// lower every atom inside (functors kept) — SAS names are case-insensitive
    pub fn lower_term(&self) -> Term {
        match self {
            Term::Atom(a) => Term::Atom(a.to_lowercase()),
            Term::Compound(f, args) => Term::Compound(f.clone(), args.iter().map(|a| a.lower_term()).collect()),
            Term::List(items) => Term::List(items.iter().map(|a| a.lower_term()).collect()),
            other => other.clone(),
        }
    }
}

pub fn writeq_atom(a: &str) -> String {
    let bare = {
        let mut cs = a.chars();
        match cs.next() {
            Some(c) if c.is_ascii_lowercase() => cs.all(|c| c.is_ascii_alphanumeric() || c == '_'),
            _ => false,
        }
    } || a == "[]" || a == "!" || a == ";" || a == "{}" || a == ",";
    // a run of symbol characters is also bare in Prolog (e.g. '<=' prints as <=)
    let symbolic = !a.is_empty() && a.chars().all(|c| "+-*/\\^<>=~:.?@#&$".contains(c));
    if (bare && a != ",") || symbolic {
        return a.to_string();
    }
    let mut out = String::from("'");
    for c in a.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\'' => out.push_str("\\'"),
            '\n' => out.push_str("\\n"),
            '\t' => out.push_str("\\t"),
            '\r' => out.push_str("\\r"),
            c => out.push(c),
        }
    }
    out.push('\'');
    out
}

pub fn float_text(f: f64) -> String {
    let s = format!("{}", f);
    if s.contains('.') || s.contains('e') || s.contains("inf") || s.contains("NaN") { s } else { s + ".0" }
}

impl fmt::Display for Term {
    fn fmt(&self, w: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Term::Atom(a) => write!(w, "{}", writeq_atom(a)),
            Term::Int(i) => write!(w, "{}", i),
            Term::Float(f) => write!(w, "{}", float_text(*f)),
            Term::Compound(f, args) => {
                write!(w, "{}(", writeq_atom(f))?;
                for (i, a) in args.iter().enumerate() {
                    if i > 0 { write!(w, ",")?; }
                    write!(w, "{}", a)?;
                }
                write!(w, ")")
            }
            Term::List(items) => {
                write!(w, "[")?;
                for (i, a) in items.iter().enumerate() {
                    if i > 0 { write!(w, ",")?; }
                    write!(w, "{}", a)?;
                }
                write!(w, "]")
            }
        }
    }
}
