//! spec.rs — the SAS pyDSL as data (out/spec/sas.json), deserialised. The
//! Rust engine interprets this; pipeline/gen_prolog.py compiles the same data
//! to a DCG. One spec, two engines (exp_42, 2026-09-05).
use serde::Deserialize;
use std::collections::HashMap;

#[derive(Deserialize, Debug)]
pub struct Spec {
    pub name: String,
    pub keywords: Vec<String>,
    pub statement_end: Vec<String>,
    #[serde(default)]
    pub eos_kinds: Vec<String>,
    #[serde(default)]
    pub bracket_pairs: Vec<(String, String)>,   // exp_42 2026-09-07: see tokenise.rs
    pub leaves: Vec<Leaf>,
    pub ladder: Vec<Level>,
    pub forms: Vec<Form>,
    pub expr_leaves: Vec<ExprLeaf>,
    pub statements: Vec<Stmt>,
    #[serde(default)]
    pub rules: HashMap<String, Vec<RuleAlt>>,
    pub blocks: Option<Blocks>,
}

#[derive(Deserialize, Debug)]
pub struct Leaf { pub name: String, pub pattern: String, pub kind: String }

#[derive(Deserialize, Debug)]
pub struct Level { pub name: String, pub assoc: String, pub ops: Vec<Op> }

#[derive(Deserialize, Debug)]
pub struct Op { pub spelling: String, pub functor: String, pub kind: String }

#[derive(Deserialize, Debug)]
#[serde(tag = "t")]
pub enum Form {
    #[serde(rename = "shape")] Shape { name: String, shape: String },
    #[serde(rename = "parts")] Parts { name: String, parts: Vec<Piece> },
    #[serde(rename = "rule")] Rule { name: String, rule: String },
}

#[derive(Deserialize, Debug)]
pub struct ExprLeaf { pub name: String, pub term: String, pub double_delim: bool, pub backslash_escape: bool }

#[derive(Deserialize, Debug)]
pub struct Stmt { pub name: String, pub assign: bool, pub parts: Vec<Piece> }

#[derive(Deserialize, Debug)]
pub struct RuleAlt { pub functor: String, pub parts: Vec<Piece> }

#[derive(Deserialize, Debug)]
pub struct Blocks {
    #[serde(default)] pub open: Vec<String>,
    #[serde(default)] pub close: Vec<String>,
    #[serde(default)] pub single: Vec<String>,
}

#[derive(Deserialize, Debug)]
#[serde(tag = "t")]
pub enum Piece {
    #[serde(rename = "kw")] Kw { text: String },
    #[serde(rename = "sym")] Sym { text: String },
    #[serde(rename = "cap")] Cap { field: String, kind: String },
    #[serde(rename = "group")] Group { functor: String, parts: Vec<Piece> },
    #[serde(rename = "list")] List { field: String, parts: Vec<Piece>, min: usize, sep: Vec<Piece> },
    #[serde(rename = "choice")] Choice { field: String, options: Vec<(String, String)>, default: Option<String> },
    #[serde(rename = "opt")] Opt { parts: Vec<Piece> },
    #[serde(rename = "rule")] Rule { field: String, name: String },
}

impl Piece {
    pub fn is_raw(&self) -> bool {
        matches!(self, Piece::Cap { kind, .. } if kind.starts_with("raw:"))
    }
}

impl Stmt {
    pub fn is_raw(&self) -> bool { self.parts.iter().any(|p| p.is_raw()) }
}
