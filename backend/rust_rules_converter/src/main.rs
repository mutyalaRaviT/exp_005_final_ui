//! lineageq_sas — exp_42's Rust engine. One binary, the whole loop:
//!   SAS text -> tokens -> node/4 (fold) -> SAS text again (unfold, same rules)
//!            -> PySpark (emit)
//! driven by out/spec/sas.json, the SAME pyDSL the Prolog DCG was generated from.
//!
//!   lineageq_sas <spec.json> <file.sas> <out_dir> [preamble.py] [pretty_preamble.py]
//! writes <out_dir>/<stem>.node4.pl, <stem>.printed.sas, <stem>_ravi_rust.py
//! Source: `raw/bench_stack/rust_engine/src/main.rs` at exp_42 commit 30afba6.
//! The modules and five helpers moved to `lib.rs` in phase 1 so the store can call them
//! in-process; this file is now only the command-line front end.

use rules_converter::{
    emit, emit_pretty, lineage, interp, parser, spec, term, tokenise,
    quote_atom, block_ids, raw_body, rebuild_source, fold_file,
};
use std::fs;
use std::path::Path;

/// lineageq_sas lineage <spec.json> <file> <out.pl>
/// SAS or PySpark (by the spec's name) -> node/4 -> lineage facts, the mirror of
/// codegen/sas_lineage.pl and codegen/pyspark_lineage.pl.
fn cmd_lineage(args: &[String]) {
    let spec: spec::Spec = serde_json::from_str(&fs::read_to_string(&args[0]).expect("spec")).expect("spec json");
    let text = fs::read_to_string(&args[1]).expect("source");
    let t0 = std::time::Instant::now();
    let (_stmts, terms, ids) = fold_file(&spec, &text);
    let nodes: Vec<(String, &term::Term)> = terms.iter().enumerate().filter_map(|(i, t)| t.as_ref().map(|t| (ids[i].clone(), t))).collect();
    let facts = if spec.name == "pyspark" { lineage::pyspark::run(&nodes) } else { lineage::sas::run(&nodes) };
    let out = facts.text();
    fs::write(&args[2], &out).unwrap();
    println!("wrote {} ({} facts)  ({} us fold+lineage)", args[2], out.lines().count(), t0.elapsed().as_micros());
}

/// lineageq_sas interp <spec.json> <file.sas> <data_dir> <out_dir> [block]
/// the executable node/4 — the mirror of codegen/sas_interp.pl
fn cmd_interp(args: &[String]) {
    let spec: spec::Spec = serde_json::from_str(&fs::read_to_string(&args[0]).expect("spec")).expect("spec json");
    let text = fs::read_to_string(&args[1]).expect("source");
    let t0 = std::time::Instant::now();
    let (_stmts, terms, ids) = fold_file(&spec, &text);
    let nodes: Vec<(String, &term::Term)> = terms.iter().enumerate().filter_map(|(i, t)| t.as_ref().map(|t| (ids[i].clone(), t))).collect();
    let mut it = interp::Interp::default();
    let only = args.get(4).map(|s| s.as_str());
    if only.is_some() { it.load_inputs(Path::new(&args[2])); }
    it.run(&nodes, only);
    it.write_all(Path::new(&args[3]));
    for l in &it.log { println!("{}", l); }
    println!("interp: {} datasets written to {}  ({} us fold+run)", it.order.len(), args[3], t0.elapsed().as_micros());
}

/// lineageq_sas block-programs <pyspark spec.json> <job.py> <preamble.py> <blocks_dir>
/// the mirror of codegen/pyspark_block.pl: one runnable program per PySpark block
fn cmd_block_programs(args: &[String]) {
    let spec: spec::Spec = serde_json::from_str(&fs::read_to_string(&args[0]).expect("spec")).expect("spec json");
    let text = fs::read_to_string(&args[1]).expect("source");
    let pre = fs::read_to_string(&args[2]).expect("preamble");
    let blocks_dir = &args[3];
    let manifest: serde_json::Value = serde_json::from_str(&fs::read_to_string(format!("{}/manifest.json", blocks_dir)).expect("manifest")).unwrap();
    let (_stmts, terms, ids) = fold_file(&spec, &text);
    let printer = parser::Printer { spec: &spec };
    let nodes: Vec<(String, &term::Term)> = terms.iter().enumerate().filter_map(|(i, t)| t.as_ref().map(|t| (ids[i].clone(), t))).collect();
    for ts in lineage::blocks(&nodes) {
        let Some(put) = ts.iter().find(|t| t.functor() == ("put", 2)) else { continue };
        let k = put.args()[0].args()[0].atom_text().to_lowercase();
        let Some(e) = manifest.as_array().unwrap().iter().find(|e| e["creates"].as_array().unwrap().iter().any(|c| c.as_str() == Some(&k))) else {
            println!("  (no manifest block creates {} — skipped)", k); continue };
        let sas_block = e["block"].as_str().unwrap();
        let dir = format!("{}/{}", blocks_dir, sas_block);
        let mut lines = vec![pre.clone(), "".into(), "spark = make_spark()".into(), "".into(),
            format!("# ---- block {} creates {}: inputs loaded from {}/in, statements printed back from node/4", sas_block, k, dir)];
        for i in e["inputs"].as_array().unwrap() {
            let i = i.as_str().unwrap();
            lines.push(format!("ds[\"{}\"] = sas_load_csv(spark, \"{}/in/{}.csv\", \"{}/in/{}.schema.json\")", i, dir, i, dir, i));
        }
        for t in &ts { if let Some(texts) = printer.print_stmt(t) { lines.push(texts.join(" ")); } }
        lines.extend(["".to_string(), "for _name in ORDER:".into(), "    sas_print(_name)".into(), "spark.stop()".into()]);
        let f = format!("{}/block_{}_rust.py", dir, k);
        fs::write(&f, lines.join("\n") + "\n").unwrap();
        println!("wrote {}", f);
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() > 1 {
        match args[1].as_str() {
            "block-programs" => { cmd_block_programs(&args[2..]); return; }
            "lineage" => { cmd_lineage(&args[2..]); return; }
            "interp" => { cmd_interp(&args[2..]); return; }
            _ => {}
        }
    }
    if args.len() < 4 {
        eprintln!("usage: lineageq_sas <spec.json> <file.sas> <out_dir> [preamble.py] [pretty_preamble.py]");
        std::process::exit(2);
    }
    let spec: spec::Spec = serde_json::from_str(&fs::read_to_string(&args[1]).expect("spec")).expect("spec json");
    let src_path = Path::new(&args[2]);
    let text = fs::read_to_string(src_path).expect("source");
    let out_dir = Path::new(&args[3]);
    fs::create_dir_all(out_dir).unwrap();
    let stem = src_path.file_stem().unwrap().to_string_lossy().to_string();
    let t0 = std::time::Instant::now();

    // 1. tokenise + split
    let toks = tokenise::tokenise(&spec, &text);
    let stmts = tokenise::split_statements(&toks);

    // 2. fold every statement
    let mut terms: Vec<Option<term::Term>> = Vec::new();
    for st in &stmts {
        let p = parser::Parser::new(&spec, &st.toks);
        let t = p.fold();
        if t.is_none() {
            let txt: Vec<&str> = st.toks.iter().map(|t| t.text.as_str()).collect();
            eprintln!("seq {}: fold failed: {}", st.seq, txt.join(" "));
        }
        terms.push(t);
    }
    let folded = terms.iter().filter(|t| t.is_some()).count();

    // 3. unfold (print) with the same rules, retokenise, refold, compare
    let printer = parser::Printer { spec: &spec };
    let mut roundtrip = 0;
    let mut printed_sas = String::new();
    let mut printed_texts: Vec<Option<Vec<String>>> = vec![None; terms.len()];
    for (i, t) in terms.iter().enumerate() {
        let Some(t) = t else { continue };
        match printer.print_stmt(t) {
            None => eprintln!("seq {}: print failed for {}", i + 1, t),
            Some(texts) => {
                printed_texts[i] = Some(texts.clone());
                let snippet = texts.join(" ");
                printed_sas.push_str(&snippet);
                printed_sas.push('\n');
                let toks2 = tokenise::tokenise(&spec, &snippet);
                let st2 = tokenise::split_statements(&toks2);
                let again = st2.first().and_then(|s| parser::Parser::new(&spec, &s.toks).fold());
                match again {
                    Some(t2) if t2.to_string() == t.to_string() => roundtrip += 1,
                    Some(t2) => eprintln!("seq {}: round-trip mismatch\n  {}\n  {}", i + 1, t, t2),
                    None => eprintln!("seq {}: refold failed on {:?}", i + 1, snippet),
                }
            }
        }
    }
    fs::write(out_dir.join(format!("{}.printed.sas", stem)), &printed_sas).unwrap();

    // 3b. SOURCE-REBUILD LAW (exp_011's R3 oracle): put the printed tokens back
    // into the original stream — whitespace, comments, keyword casing kept —
    // and the result must equal the source byte for byte.
    let (rebuilt, mismatches) = rebuild_source(&toks, &printed_texts);
    let source_match = rebuilt == text;
    fs::write(out_dir.join(format!("{}.rebuilt.sas", stem)), &rebuilt).unwrap();
    for m in &mismatches { eprintln!("rebuild mismatch: source {:?} printed {:?}", m.0, m.1); }

    // 4. node/4
    let ids = block_ids(&spec, &terms);
    let rel = src_path.to_string_lossy().to_string();
    let mut node4 = String::new();
    let mut nodes = Vec::new();
    for (i, st) in stmts.iter().enumerate() {
        let Some(t) = &terms[i] else { continue };
        node4.push_str(&format!("node({}, {}, {}, trace({},{},{},{},{})).\n",
            quote_atom(&ids[i]), st.seq, t, quote_atom(&rel), st.l0, st.l1, st.b0, st.b1));
        nodes.push(emit::Node { block: ids[i].clone(), seq: st.seq, term: t.clone(), l0: st.l0, l1: st.l1, b0: st.b0, b1: st.b1 });
    }
    fs::write(out_dir.join(format!("{}.node4.pl", stem)), &node4).unwrap();

    // 5. emit PySpark
    if args.len() > 4 {
        let preamble = fs::read_to_string(&args[4]).expect("preamble");
        let py = emit::Emitter::new().program(&nodes, &preamble);
        fs::write(out_dir.join(format!("{}_ravi_rust.py", stem)), py).unwrap();
    }
    // 5b. the readable version, from the same node/4
    if args.len() > 5 {
        let preamble = fs::read_to_string(&args[5]).expect("pretty preamble");
        let py = emit_pretty::Pretty::new(&text, &nodes).program(&preamble);
        fs::write(out_dir.join(format!("{}_pretty_rust.py", stem)), py).unwrap();
    }
    let us = t0.elapsed().as_micros();
    println!("{}: statements {}  folded {}  roundtrip {}  source==rebuilt {}  blocks {}  ({} us total)",
             stem, stmts.len(), folded, roundtrip, if source_match { "yes" } else { "NO" },
             ids.iter().collect::<std::collections::BTreeSet<_>>().len(), us);
    if folded != stmts.len() || roundtrip != stmts.len() || !source_match { std::process::exit(1); }
}
