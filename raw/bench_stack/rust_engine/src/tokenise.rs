//! tokenise.rs — port of pipeline/tokeniser.py: leaves in order, first match
//! wins; a WORD in the keyword list becomes KEYWORD; anything unmatched is a
//! one-character SYMBOL; EOS after a statement_end symbol, after a token of an
//! eos_kind, and at EOF. Lossless by construction (every byte lands in a token).
use crate::spec::Spec;
use regex::Regex;

#[derive(Clone, Debug)]
pub struct Tok {
    pub kind: String,
    pub text: String,
    pub line: usize,
    pub col: usize,
    pub b0: usize,
    pub b1: usize,
}

pub const GRAMMAR_KINDS: [&str; 7] = ["keyword", "word", "number", "string", "symbol", "path", "datalines"];

pub fn tokenise(spec: &Spec, text: &str) -> Vec<Tok> {
    let leaves: Vec<(&str, Regex)> = spec.leaves.iter()
        .map(|lf| (lf.kind.as_str(), Regex::new(&format!("^(?:{})", lf.pattern)).expect("leaf regex")))
        .collect();
    let keywords: Vec<String> = spec.keywords.iter().map(|k| k.to_lowercase()).collect();
    let mut toks = Vec::new();
    let (mut pos, mut line, mut col) = (0usize, 1usize, 1usize);
    // exp_42 (2026-09-07): bracket_pairs — no statement ends while a bracket is
    // open (Python's implicit line joining). Mirrors pipeline/tokeniser.py.
    let opens: Vec<&str> = spec.bracket_pairs.iter().map(|p| p.0.as_str()).collect();
    let closes: Vec<&str> = spec.bracket_pairs.iter().map(|p| p.1.as_str()).collect();
    let mut depth: usize = 0;
    let n = text.len();
    let emit = |toks: &mut Vec<Tok>, kind: &str, s: &str, pos: usize, line: &mut usize, col: &mut usize| {
        toks.push(Tok { kind: kind.to_string(), text: s.to_string(), line: *line, col: *col, b0: pos, b1: pos + s.len() });
        for ch in s.chars() {
            if ch == '\n' { *line += 1; *col = 1; } else { *col += 1; }
        }
    };
    while pos < n {
        let rest = &text[pos..];
        let mut hit: Option<(&str, &str)> = None;
        for (kind, re) in &leaves {
            if let Some(m) = re.find(rest) {
                if m.end() > 0 { hit = Some((kind, &rest[..m.end()])); break; }
            }
        }
        let (kind, s) = match hit {
            Some((kind, s)) => {
                if kind == "word" && keywords.contains(&s.to_lowercase()) { ("keyword", s) } else { (kind, s) }
            }
            None => {
                let ch = rest.chars().next().unwrap();
                ("symbol", &rest[..ch.len_utf8()])
            }
        };
        emit(&mut toks, kind, s, pos, &mut line, &mut col);
        pos += s.len();
        if kind == "symbol" && opens.contains(&s) { depth += 1; }
        else if kind == "symbol" && closes.contains(&s) && depth > 0 { depth -= 1; }
        if (spec.statement_end.iter().any(|e| e == s) || spec.eos_kinds.iter().any(|k| k == kind)) && depth == 0 {
            toks.push(Tok { kind: "eos".into(), text: String::new(), line, col, b0: pos, b1: pos });
        }
    }
    toks.push(Tok { kind: "eos".into(), text: String::new(), line, col, b0: pos, b1: pos });
    let joined: String = toks.iter().map(|t| t.text.as_str()).collect();
    assert_eq!(joined, text, "LOSSLESS LAW violated");
    toks
}

/// One statement: the grammar tokens between two EOS markers (comments and
/// whitespace dropped; an all-comment segment is no statement at all).
pub struct StmtToks { pub seq: usize, pub toks: Vec<Tok>, pub l0: usize, pub l1: usize, pub b0: usize, pub b1: usize }

pub fn split_statements(toks: &[Tok]) -> Vec<StmtToks> {
    let mut out = Vec::new();
    let mut seg: Vec<Tok> = Vec::new();
    for t in toks {
        if t.kind == "eos" {
            let g: Vec<Tok> = seg.iter().filter(|x| GRAMMAR_KINDS.contains(&x.kind.as_str())).cloned().collect();
            if !g.is_empty() {
                let seq = out.len() + 1;
                out.push(StmtToks { seq, l0: g[0].line, l1: g[g.len() - 1].line, b0: g[0].b0, b1: g[g.len() - 1].b1, toks: g });
            }
            seg.clear();
        } else {
            seg.push(t.clone());
        }
    }
    out
}
