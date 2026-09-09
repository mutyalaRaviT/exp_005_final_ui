---
tags: [plan, gold, ui, verification, rules_engine]
---
# Three UIs and the verification loop

**Why this file exists.** The owner set the shape of exp_005 on 2026-09-08: there are
**three** UIs, not two, and the thing that proves the product works is a **four-leg
verification loop** driven by AI in the development area. `gold_draft_exp_005_plan.md`
was written before this and assumes two windows and a background Prolog proof. This page
is the authority where the two disagree.

**Inputs → outputs.** the owner's brief of 2026-09-08 (quoted verbatim below) + a
three-round interview on the same day → this page → the corrections listed in
§7, which must be applied to `gold_draft_exp_005_plan.md` and to `CLAUDE.md`.

**Status.** Gold, marked so by the owner ("mark this as golden document"). Written by an
agent from the owner's own words and answers; the owner's authorisation is what makes it
gold rather than `gold_draft_`.

---

## 1. The brief, verbatim

> our main verification loop is sas -> node4 -> sas , sas -> node4 -> testcases ->
> executable -> output_left , sas -> node4 -> testcases -> migrate -> execute ->
> ouptut_right, lineage_left -> lineage_right these all happens in a test/development
> using ai format, we need a seperate 3 ui for my eyes only for development in my local
> laptop, every one else will use ui1 and ui2 I will use ui3 with ai to test my rules and
> rules engine end to end, mark this as golden document

And, on Prolog:

> we use prolog only for development in my development area, ui testing and user testing
> donot need prolog and we will not mention it, we will just test them as testcases when
> something is failing or require prolog validation during compiler rules testing.

---

## 2. The three UIs

| UI | who uses it | what it shows | ships? |
|---|---|---|---|
| **UI1** | everyone | across files — which file feeds which, tables flowing between them | yes |
| **UI2** | everyone | inside one file — SAS cells beside PySpark cells, the table graph | yes |
| **UI3** | the owner, alone | the verification workbench: runs the loop of §3 over a corpus, with AI | **no** |

UI3 is a **third window in the same app** — same frontend, same tokens, same API — put
behind a **build flag that excludes it from the release binary**. Not a hidden route, not
a menu item nobody clicks: the release `.app` does not contain the code. Dev builds do.

Think of it as a compiler and its test suite. UI1 and UI2 are the compiler's output that
customers look at. UI3 is the bench the compiler author works at, and it never leaves the
workshop.

---

## 3. The verification loop — four legs

Everything below runs in the development area, never in front of a user.

| leg | the path | what it proves |
|---|---|---|
| **L1** | `sas → node4 → sas` | **round trip.** Parse the SAS into node/4 terms, print it back out. If what comes out differs from what went in, the parse lost something. |
| **L2** | `sas → node4 → testcases → executable → output_left` | **what the original means.** Generate test rows from the node/4 terms, then execute the *original* semantics over them. This is the left-hand answer. |
| **L3** | `sas → node4 → testcases → migrate → execute → output_right` | **what the migration does.** Same test rows, but now generate PySpark from node/4 and run it on Spark. This is the right-hand answer. |
| **L4** | `lineage_left → lineage_right` | **the lineage survives.** The table-to-table story the original tells must be the story the migration tells. |

**A run passes when all three hold:**

```
L1 round-trips exactly
output_left  ==  output_right     (the data matches)
lineage_left ==  lineage_right    (the lineage matches)
```

A migration that produces the right numbers but a different lineage has still failed.
That is the whole point of LineageQ.

### Who executes each side

- **`output_left` is computed by Prolog.** The Prolog driver runs the node/4 terms as the
  reference semantics.
- **`output_right` is computed by Spark**, running the PySpark that the **Rust** engine
  generated from the same node/4.

This split is deliberate — see §5.

---

## 4. What UI3 actually is

**Unit of work: the whole corpus.** You point UI3 at a folder and it sweeps every file
through all four legs, and hands back a table of pass and fail. UI3 exists to find bugs in
the **rules engine**, not to certify one customer's migration. Per-file correctness is how
you find the bug, not the goal.

**On failure, one screen shows three things at once:**

1. **the narrowest failing block** — the single SAS block where the divergence starts
2. **the data diff** — output_left beside output_right, at row level
3. **the rule that fired** — which grammar or codegen rule produced the bad node/4 or the
   bad PySpark

That combination *is* UI3. Any one of the three alone is already available elsewhere;
having them on one screen, tied to each other, is the reason the third window exists.

**AI drives the loop.** Concretely, all of:

- **writes the testcases** from the node/4 terms — the `testcases` step in L2 and L3,
  where `gen_testdata.py` and Z3 cannot reach
- **runs the legs** across the corpus
- **triages the failures** — reads block, diff and rule together and says *why*
- **proposes the rule fix**, then re-runs to see if it held

The owner supervises from UI3 rather than clicking through it.

---

## 5. Prolog: dev-only, and load-bearing

Prolog **does not appear in UI1 or UI2**. Stripped: the `prolog == rust` pill, the
Rust/Prolog engine toggle, and the receipt bar. Users never see the word.

But inside UI3, Prolog is not a fallback that runs "when something fails" — it is the
independent second engine, and here is why.

If Rust both computes `output_left` (by interpreting node/4) *and* generates the PySpark
that computes `output_right`, then a bug in Rust's understanding of a SAS construct
corrupts **both sides in the same way**. The diff comes back green. The loop reports
"pass" over wrong semantics. You would have built a machine that checks its own homework.

So: **Prolog computes `output_left`, Rust generates the code behind `output_right`.** Two
engines that were written separately, disagreeing when either is wrong. That is what makes
the equality in §3 mean something.

This is the owner rule from exp_42 — *Prolog is the reference, Rust mirrors it* — carried
into exp_005 in the only place it is still needed.

---

## 6. Analogy, for the two-minute version

Imagine translating a recipe from French to English.

- **L1** is reading the French, writing it back in French, and checking nothing was lost.
- **L2** is cooking the French recipe and photographing the dish.
- **L3** is cooking your English translation and photographing that dish.
- **L4** is checking both cooks bought the same ingredients from the same shops.

If the two photos differ, the translation is wrong. And you want the two dishes cooked by
**two different cooks** — otherwise one cook's misreading shows up identically in both,
and the photos match while the recipe is wrong. Prolog and Rust are the two cooks.

---

## 7. What this changes in the existing plan

`gold_draft_exp_005_plan.md` and `CLAUDE.md` were written before this brief. These points
must be reconciled; until they are, **this page wins**.

| # | where | says today | must become |
|---|---|---|---|
| C1 | plan §7, §8, CLAUDE.md opening | "two windows", "the two UIs" | three UIs, the third build-flagged out of release |
| C2 | plan §8 phase 4 | "proof in background… receipts table; bar turns green"; pass mark is a receipt bar going from pending to same | Prolog is not a background service and there is no bar. Phase 4 becomes: Prolog computes `output_left` inside UI3, and the L2/L3 comparison runs over a corpus |
| C3 | plan §8 phase 5 | `run()` + DataMatch strip inside the in-file window | that machinery is UI3's core, not a strip in UI2. `bench_receipt.py` and `datamatch.ts` seed UI3 |
| C4 | plan §8 phase 6 | "one `.app` opens both windows" | unchanged for the release build — and the build flag that keeps UI3 out of it is part of this phase's pass mark |
| C5 | plan §8 phase 0 | "folders, READMEs, this vault, `wiki_from_git.py` first run" | add: the source trees copied into `raw/`, untouched, with provenance |
| C6 | plan §6, the Bench port | the Bench keeps its Prolog surface | strip the pill, the toggle and the receipt line from the UI2 port |
| C7 | `raw_sources_to_copy.md` | ankitha_1 comes from `exp_003_lineageq_slides` | it is in `lineageQ_aug_experiments/exp_014b_vertical_slice_sas_lineage/corpus/ankitha_1/` |

### A conflict the owner must settle

The owner's own Bench screenshot — the agreed visual baseline for the UI2 port — **shows
the Prolog pill, the toggle and the `prolog = rust: true` receipt**. "Match the baseline"
and "no Prolog in UI2" cannot both hold. Resolved 2026-09-08: **strip them**, and the
port's screenshots will differ from the baseline in exactly those places, listed
explicitly when the port is delivered.

---

## Decisions

- **PROVEN ∎** — §1 is the owner's words, unedited. §2–§5 are the owner's answers to a
  three-round interview on 2026-09-08: UI3 is a third window in the same app; gated by a
  build flag excluded from release; unit of work is a corpus sweep; failure shows block +
  diff + rule on one screen; AI writes testcases, runs, triages and proposes fixes;
  `output_left` comes from an engine interpreting node/4, with Prolog as that engine.
- **ASSUMED** — that `output_right` runs on Spark rather than any other executor; taken
  from the plan's phase 5 and exp_42's existing `run()`, not restated by the owner.
- **ASSUMED** — that "corpus sweep" means ankitha_1 and the exp_42 SAS corpus to begin
  with. Not yet sized against `big_1000.sas`.
- **OPEN** — how a corpus sweep is scheduled. The owner rejected "whatever failed last
  night", so there is no nightly queue; whether a sweep is manual-only is unstated.
- **OPEN** — what `testcases` are as an artefact: rows only, or rows plus expected values.
  L2 executing them implies rows only, with the expectation computed. Confirm before
  phase 5.
- **OPEN** — whether UI3's build flag lives in Cargo, in Vite, or both. §2 fixes the
  requirement, not the mechanism.
