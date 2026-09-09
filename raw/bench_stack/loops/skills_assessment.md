# Skills assessment — would bench-card skills pay off for exp_42's engine?

Written 2026-09-07 (read-only pass over the engine and the existing skills).
Why this file exists: the owner asked whether four Claude Code skills (tokeniser,
pyDSL generator, Prolog codegen, Rust mirror) would cut tokens per task and wrong
turns. Inputs: `/Users/mutyala/.claude/skills/`, the repo's `.claude/skills/`, the
exp_42 engine files. Output: one verdict per part, the rules each skill must hold,
and an order of writing.

## 1. Existing skills and their overlap with exp_42

| Skill | Written for | Still applies to exp_42? | Overlap |
|---|---|---|---|
| `fixing-tokeniser-gaps` (60 lines) | exp_008, `engine/src/specs/*_tokens.json`, `node engine/run/tokenise_lang.ts` | No. Different spec grammar (piece/one_of/between), different commands, UNKNOWN tokens exist there and not here. | Loop shape only (probe first, diff-minimal edit). |
| `hardening-a-tokeniser` (151 lines) | exp_008 invariants (`beauty.ts`) | Principle only: "lossless is not correct". | The one sentence exp_42's tokeniser docstring already carries. |
| `resolving-unknown-tokens` (115 lines) | any lexer with UNKNOWN tokens | No. exp_42 never emits UNKNOWN; a stray char is a 1-char `symbol`. | None. |
| `pydsl_step_grammar` (57 lines) | exp_007 nine-step pyDSL, `builders.py`, `lineageq` binary | No. Different vocabulary (`statement_anatomies`, `anatomy_keyword`), different binary. | The word "pyDSL" only. |
| `scryer_dcg_both_ways_ts` (58 lines) | exp_011 Scryer + TypeScript | Partly. Rules 5, 6, 9 (dumb printer, literals as text, prove by string equality) are exp_42's design. Tabling / machine-death rules do not apply (SWI, no left recursion by construction). | Design principles, not mechanics. |
| `tokeniser_parse_folder_knowledge_graph_skill` (100 lines) | wiki rule dictionary, REST logging | No. Doctrine, not code. | None. |
| `exp008_default_knowhow` (132 lines) | exp_008 TS rewrite | Rule 3 ("diff every port against the reference") is exp_42's whole method. | One rule. |

Conclusion: nothing existing tells a fresh session how exp_42's engine works.
The commands, file paths, and vocabulary in every existing skill point at other
tracks. A session that loads them gets the right attitude and the wrong bench.

## 2. What a fresh session must read today, per part

| Part | Files a safe change needs | Lines | Bench-card target |
|---|---|---|---|
| 1 Tokeniser | `pipeline/tokeniser.py`, `rust_engine/src/tokenise.rs`, `spec.rs`, `export_spec.py`, the LEAVES block of `specs/sas.py` + `specs/pyspark.py`, `run_fold.py` GRAMMAR_KINDS | ~450 | ~90 |
| 2 pyDSL generator | `pydsl_lib.py`, `gen_prolog.py`, `export_spec.py`, `specs/sas.py`, `spec.rs`, `parser.rs` (to know what Rust accepts) | ~2,060 | ~140 |
| 3 Prolog codegen | `sas_pyspark.pl`, `sas_pyspark_pretty.pl`, both runtime preambles, term vocabulary in `sas.py` docstring, `emit.rs` (must mirror) | ~1,000 | ~110 |
| 4 Rust mirror | `parser.rs`, `emit.rs`, `emit_pretty.rs`, `term.rs`, `main.rs`, `spec.rs`, plus the Prolog it mirrors | ~1,700 | ~120 |

Token argument (rough, 12 tokens per code line): part 2 costs ~25k tokens of
reading per session before the first edit; a 140-line card costs ~1.7k. Parts 3
and 4 cost ~12k and ~20k; cards ~1.4k. Part 1 costs ~5k; a card ~1k. The card
never replaces reading the one file being edited, so the saving is the OTHER
files: the cross-file rules a session otherwise rediscovers by grep.

## 3. Verdicts

| Part | Verdict | Reason |
|---|---|---|
| 1 Tokeniser | Fold into the generator skill (one section) | The engine is 90 lines in each language and its docstring already states the six laws. What is NOT in one file is the four-place rule for a new token kind and the eos/bracket rules. Ten lines cover it. |
| 2 pyDSL generator | Write now | Highest reading cost (~2,000 lines), most known limits, and every limit fails silently or with a `sys.exit` that names the symptom, not the rule. This is where wrong turns happen. |
| 3 Prolog codegen | Write now, short | 257 lines read fast, but the schema threading (`Pre0/Pre` accumulator, `schema/2` asserted in step order, `flag(scalar)`) and the "must mirror emit.rs" contract are not derivable from one clause. |
| 4 Rust mirror | Write now, as the second half of part 3's card | The mirror's value is the list of what it does NOT support (`assign` skipped, three shape strings only, `print_stmt` arity rule). A session that adds a form to `sas.py` without that list gets a panic at run time, after generating the Prolog. |

### 3.1 What goes into the pyDSL-generator card (part 2, with the tokeniser section)

1. A new Piece kind needs four places: `pydsl_lib.py` dataclass + constructor, `gen_prolog.py` `_piece_parse` AND `_piece_print`, `export_spec.py` `piece()`, `parser.rs` `Piece` enum + `piece()` + `print_piece()`. A new Form kind needs `gen_ladder` (both directions), `export_spec.form()`, `spec.rs Form`, `parser.rs prim()` + `expr_own()`.
2. One `Opt` per parts sequence; no Opt inside Opt; an Opt must carry exactly one value piece. `select_core` works only because each Opt is its own piece in the sequence.
3. A `comma_list`/`sep_list` item carries exactly one value (Cap, RuleRef, or Group). Wrap two captures in `group()`.
4. `kw()` vs `sym()` is decided by `is_word()` on the spelling, not by the constructor: a keyword must also be in `KEYWORDS`, or the tokeniser emits `word` and the DCG's `tok(keyword,_)` never matches. Symptom: fold fails, no message.
5. The word leaf always builds `col/1`; `ident()` builds a bare atom; `ref()` builds `rel/1`. There is no "word as literal" leaf. Strings always print single-quoted; a source `"..."` prints back `'...'` (source rebuild still passes because rebuild compares by value for datalines only, and by text otherwise, so a double-quoted SAS string breaks source==rebuilt).
6. Ladder is tightest-first; `assoc="none"` levels are one-shot (no `a ** b ** c`); there is no right-assoc and no postfix level. Left-assoc levels become accumulator loops (no left recursion).
7. Form shape strings are a closed set (`FORM_FUNCTOR_ARITY`); Rust supports only `( E )`, `ID ( ARGS )`, `ID . ID (canonical)`. `$ NUM`, `$ ID`, `ID :: ID`, `KW <word>` panic in Rust. Prefer `parts_form` for anything new.
8. `expr_leaves` names are the token kinds (`number`, `string`, `word`); Rust panics on any other leaf name. `dequote=True` only means something on `string`/`atom`.
9. `statement_end=[]` means "statement ends when all tokens are consumed" (PySpark); `eos_kinds` ends a statement on a token kind (`datalines`, `newline`); `bracket_pairs` suppresses EOS while depth > 0. A `raw()` statement has no trailing `;` on parse or print.
10. Print keeps source order inside `opt` (2026-09-05 fix); keyword print is lowercased `text`; `Choice` always prints the explicit keyword, never the default.
11. Statement order in `STATEMENTS` is try-order; Rust and Prolog both take the first full-consumption parse. `subset_if` before `if_then_set` would never fold the latter.
12. Regenerate both outputs after any spec edit: `python -m pipeline.gen_prolog sas && python -m pipeline.export_spec sas`, then `cargo build --release`, then `./run_all.sh`. `sas.json` is written by export_spec, not by the Rust build.
13. Tokeniser section: leaves are tried in order, first non-empty match wins; no UNKNOWN; a new token kind must be added to `GRAMMAR_KINDS` in BOTH `run_fold.py` and `tokenise.rs` or the fold silently drops it (exp_014 Pig `path` bug). A leaf with `(?s)` needs the same flag in the Rust regex string. The lossless and byte-offset laws are asserted at every call.

### 3.2 What goes into the codegen + mirror card (parts 3 and 4)

1. Prolog is the reference; every `emit.rs` function names its clause. Write the Prolog clause first, then the Rust arm, then `run_all.sh` step 4 must print `prolog == rust` three times per file.
2. `step_lines/2` is tried in clause order with `!` after the discriminating `memberchk`; the order INPUT+DATALINES → IF_THEN_SET → SET → MERGE is load-bearing. Rust's `if let` chain must keep the same order.
3. `px/4` threads `Pre0/Pre`: scalar subqueries append a `_scalarN = scalar(...)` line to Pre and return `F.lit(_scalarN)`. Rust passes `&mut Vec<String> pre`. `filter_txt` requires `Pre == []` (no scalar subquery inside a subsetting IF).
4. `schema/2` is asserted per step in block order and read by later steps (MERGE check, `*` expansion). Rust keeps `HashMap schema`. A new step shape must `set_schema` or downstream `*` becomes `_auto`.
5. `sas_fn/2` is the SAS→PySpark function table; Prolog `fail`s with a stderr line, Rust `panic!`s. Add to both or the outputs differ.
6. Numbers: Prolog `~w` and Rust `Display` must agree (`term.rs float_text`). Strings: `py_str` escapes `\`, `"`, newline — identical in both.
7. The pretty printer (`sas_pyspark_pretty.pl` / `emit_pretty.rs`) has its own rules: Python keyword suffix `_`, `lib_name` when a dataset name appears under two librefs, unique `_scalar` names. Plain and pretty must produce the same CSVs (step 5 of `run_all.sh`).
8. Rust `fold()` skips `assign=True` statements; `print_stmt` accepts an arity-0 term only if the parts are all KW/SYM. node/4 is printed like `writeq/2`; `term_parse.py` reads bare symbol atoms (`*`, `<=`) since 2026-09-07.
9. Block ids come from `LANG["blocks"]` (`open`/`close`/`single`) in both `blocks.py` and `main.rs block_ids`; a new opening statement must be listed or it joins the previous block.

## 4. Quality argument — how work went wrong before

Receipts found quickly (exp_014 `code_graph/gold/pig/coverage.md`, docs1 gold_draft exp_014, exp_42 README):

| Failure | Kind | Would a skill have caught it? |
|---|---|---|
| New `path` token kind silently dropped by `GRAMMAR_KINDS` (exp_014 Pig) | did not know the rule (a constant in another file) | Yes — rule 13 above. |
| Hive `\'` escape hid live SQL inside string tokens while staying lossless (exp_014 phase B) | the rule was wrong (regex) | No. Caught by review, not by a rule card. |
| `opt` print put keywords first: `( in = ) a` (exp_42, 2026-09-05) | the rule was wrong (generator bug) | No. A skill would have named the symptom faster only. |
| Rust panics on a form shape the Prolog side accepts | did not know the rule (closed set in `parser.rs`) | Yes — rule 7. |
| `bracket_pairs` had to be added in tokeniser.py, tokenise.rs, spec.rs, export_spec.py (2026-09-07) | did not know the four places (found by grep) | Yes — rule 1 / 13. |
| Vishnu MERGE with BY variable missing — caught by schema inference | not a failure; a rule that worked | n/a |

About half the recorded failures are "did not know the cross-file rule" and half
are "the rule was wrong". A skill fixes the first half and shortens the second
(it tells the session where the two engines must agree, so the diff shows the
wrong rule sooner). It never replaces `run_all.sh`.

## 5. Recommendation

Write ONE skill, `exp42_two_engine_pydsl`, with three sections in this order:

1. **Spec and generator** (rules 3.1.1–3.1.12) — write first; largest saving.
2. **Tokeniser** (rule 3.1.13, ten lines) — same card, since every tokeniser change is a spec change.
3. **Codegen and Rust mirror** (rules 3.2.1–3.2.9) — one section, because a codegen change is never done until Rust matches; splitting them invites a Prolog-only edit.

One skill, not four: the four parts share one loop (`run_all.sh`), one spec, and
one contract (byte equality), and a session working on any part needs the
"four places" rule from the others. Keep it under 150 lines; put commands at the
top (`gen_prolog`, `export_spec`, `cargo build --release`, `run_all.sh`, the
per-file `swipl` and `lineageq_sas` lines from `run_all.sh`). Add the
scryer-style receipt table (which rule, which date, which file) so it stays
bronze-tiered and improvable. Do not fold it into `exp008_default_knowhow` or
`fixing-tokeniser-gaps`; their commands are for another engine.
