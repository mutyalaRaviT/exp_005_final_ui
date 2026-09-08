# backend/prolog_rules_converter — Prolog rules converter

**Why this folder exists.** drives swipl over the same DCG for the proof; runs after an open, never on its path.

**Inputs → outputs.** node/4 from Rust, stmts from the tokeniser → proof state per file: pending / same / differs (+ first differing line).

**Status (2026-09-08).** Planned in `docs/plan/gold/gold_draft_exp_005_plan.md`; nothing here runs yet.
