% codegen/sas_pyspark.pl — SAS node/4 -> PySpark, in Prolog (exp_42, 2026-09-05).
%
% Fix round 1 (2026-09-09): every proj(...) pattern in this file was arity-2
% (proj(Expr,AliasOpt)) while pipeline/specs/sas.py's PROJ has built arity-3
% (proj(Expr,AliasOpt,LengthOpt)) since task 5b's LENGTH support — this file was
% never touched or tested in 5b, so every proj/2 clause here silently matched
% nothing. run_all.sh step 4's Prolog-vs-Rust byte-diff caught it: this file was
% dropping the entire body of every CREATE TABLE AS SELECT. Fixed by widening
% every proj/2 to proj/3 (the third arg unused here, matched with `_`).
%
% Why: the conversion RULES live here as clauses a person can read one at a
% time: one clause per SAS statement shape, one clause per expression
% functor. The input is ONLY the node/4 fact file the fold harness wrote
% (out/ir/sas/<stem>.node4.pl) — never the SAS text. rust_engine/src/emit.rs
% is the same rule set in Rust; the two outputs are diffed byte for byte.
%
%   swipl -q -s codegen/sas_pyspark.pl -g main -- <node4.pl> <preamble.py> <out.py>
%
% Output shape: the runtime preamble, `spark = make_spark()`, then one
% commented section per block (one SAS step), then a PROC PRINT-like listing
% of every dataset in creation order.
:- dynamic node/4.
:- dynamic node_comment/5.
:- dynamic schema/2.        % schema(DsAtom, [ColAtom...]) — inferred as we go

main :-
    current_prolog_flag(argv, [Node4, Preamble, Out]),
    style_check(-discontiguous),
    consult(Node4),
    read_file_to_string(Preamble, Pre, []),
    flag(scalar, _, 0),
    program_lines(Lines),
    setup_call_cleanup(open(Out, write, S),
        ( write(S, Pre), nl(S), forall(member(L, Lines), (write(S, L), nl(S))) ),
        close(S)),
    length(Lines, N), format("wrote ~w (~w generated lines)~n", [Out, N]),
    halt(0).
main :- format(user_error, "usage: swipl -q -s codegen/sas_pyspark.pl -g main -- node4.pl preamble.py out.py~n", []), halt(1).

% ---------------------------------------------------------------- blocks
blocks(Bs) :- findall(B, node(B, _, _, _), Bs0), list_to_set(Bs0, Bs).
block_terms(B, Ts) :- findall(Seq-T, node(B, Seq, T, _), Ps), keysort(Ps, Sorted), pairs_values(Sorted, Ts).
block_span(B, L0, L1) :-
    findall(A-Z, node(B, _, _, trace(_, A, Z, _, _)), Ps),
    pairs_keys(Ps, As), pairs_values(Ps, Zs), min_list(As, L0), max_list(Zs, L1).

program_lines(Lines) :-
    blocks(Bs),
    findall(L, ( member(B, Bs), block_lines(B, BL), member(L, BL) ), Body),
    append(["", "spark = make_spark()", ""], Body, L1),
    append(L1, ["", "# ---- every dataset the program created, in SAS log order",
                "for _name in ORDER:", "    sas_print(_name)", "spark.stop()"], Lines).

block_lines(B, Lines) :-
    block_terms(B, Ts), block_span(B, L0, L1), once(step_title(Ts, Title)),
    format(atom(H), "# ---- ~w  lines ~w-~w  ~w", [B, L0, L1, Title]),
    ( once(step_lines(Ts, Body)) -> true
    ; format(atom(E), "# LINEAGEQ: no rule for this step: ~q", [Ts]), Body = [E] ),
    append([H|Body], [""], Lines).

step_title([libname(L, lit(P))|_], T) :- format(atom(T), "LIBNAME ~w '~w'", [L, P]).
step_title([data(D)|_], T) :- ds_key(D, K), format(atom(T), "DATA ~w", [K]).
step_title([proc_sql|_], "PROC SQL").
step_title([proc_print(D)|_], T) :- ds_key(D, K), format(atom(T), "PROC PRINT ~w", [K]).
step_title(_, "").

% ----------------------------------------------------------------- steps
% LIBNAME lib 'path'  ->  a documented mapping; datasets live in memory here.
step_lines([libname(Lib, lit(Path))], [L]) :-
    py_str(Path, P), format(atom(L), "LIBS[\"~w\"] = ~w", [Lib, P]).

% PROC SQL step: every CREATE TABLE inside it, in order.
step_lines([proc_sql|Body], Lines) :-
    findall(L, ( member(create_table_as(Out, Sel), Body), sql_lines(Out, Sel, Ls), member(L, Ls) ), Lines).

% PROC PRINT step: every dataset is listed at the end of the program anyway.
step_lines([proc_print(D)|Body], [L|Ts]) :-
    ds_key(D, K), format(atom(L), "# PROC PRINT ~w -> listed by sas_print at the end of this program", [K]),
    findall(T, ( member(title(lit(X)), Body), format(atom(T), "# TITLE '~w'", [X]) ), Ts).

% DATA step: INPUT + DATALINES  ->  sas_datalines(...)
step_lines([data(Out)|Body], Lines) :-
    memberchk(input(Vars), Body), memberchk(datalines(Rows), Body), !,
    ds_key(Out, K), maplist(input_col, Vars, Cols), atomic_list_concat(Cols, ", ", ColsTxt),
    py_str(Rows, RowsPy),
    format(atom(L1), "put(\"~w\", sas_datalines(spark,", [K]),
    format(atom(L2), "    columns=[~w],", [ColsTxt]),
    format(atom(L3), "    rows=~w))", [RowsPy]),
    format_lines(Body, FmtLines),
    maplist(var_name, Vars, Names), set_schema(K, Names),
    append(FmtLines, [L1, L2, L3], Lines).   % exp_42 2026-09-07: FORMAT lines first

% DATA step: IF _N_ = 1 THEN SET lookup; SET main  ->  every row of main carries the lookup's one row
step_lines([data(Out)|Body], Lines) :-
    memberchk(if_then_set(_, lit(1, _), Look), Body), memberchk(set(In), Body), !,
    ds_key(Out, K), ds_key(In, KI), ds_key(Look, KL),
    format(atom(L1), "put(\"~w\", sas_attach_first_row(ds[\"~w\"], ds[\"~w\"]))", [K, KI, KL]),
    format_lines(Body, FmtLines), append(FmtLines, [L1], Lines),
    findall(C, ( member(D, [In, Look]), ds_key(D, DK), schema(DK, Cs), member(C, Cs) ), Cols0), list_to_set(Cols0, Cols), set_schema(K, Cols).

% DATA step: SET + subsetting IF(s)  ->  filter chain
step_lines([data(Out)|Body], Lines) :-
    memberchk(set(In), Body), !,
    ds_key(Out, K), ds_key(In, KI),
    findall(C, member(subset_if(C), Body), Conds),
    foldl(filter_txt, Conds, "", Chain),
    format(atom(L1), "put(\"~w\", ds[\"~w\"]~w)", [K, KI, Chain]),
    format_lines(Body, FmtLines),
    ( schema(KI, Cols) -> set_schema(K, Cols) ; true ),
    append(FmtLines, [L1], Lines).

% DATA step: MERGE ... BY  ->  sas_merge(...), with a compile-time schema check
step_lines([data(Out)|Body], Lines) :-
    memberchk(merge(Srcs), Body), !,
    ds_key(Out, K),
    ( memberchk(by(Keys), Body) -> true ; Keys = [] ),
    maplist(merge_src, Srcs, SrcTxts), atomic_list_concat(SrcTxts, ", ", SrcsTxt),
    maplist(py_str, Keys, KeyPys), atomic_list_concat(KeyPys, ", ", KeysTxt),
    findall(W, ( member(src(D, _), Srcs), ds_key(D, DK), schema(DK, Cols), member(Key, Keys), \+ memberchk(Key, Cols),
                 atomic_list_concat(Cols, ", ", ColsTxt),
                 format(atom(W), "# LINEAGEQ CHECK: BY variable ~w is not on ~w (its columns: ~w) -> SAS logs an ERROR, stops the step, and leaves 0 observations.", [Key, DK, ColsTxt]) ), Warns),
    format(atom(L1), "put(\"~w\", sas_merge(spark, [~w], by=[~w]))", [K, SrcsTxt, KeysTxt]),
    findall(C, ( member(src(D, _), Srcs), ds_key(D, DK), schema(DK, Cs), member(C, Cs) ), AllCols0),
    list_to_set(AllCols0, AllCols), set_schema(K, AllCols),
    append(Warns, [L1], Lines).

merge_src(src(D, _Flag), Txt) :- ds_key(D, K), format(atom(Txt), "(\"~w\", ds[\"~w\"])", [K, K]).

filter_txt(C, Acc, Out) :- px(C, P, [], Pre), Pre == [], format(atom(Out), "~w.filter(~w)", [Acc, P]).

% FORMAT var fmt.  ->  the format travels with the variable
format_lines(Body, Lines) :-
    findall(L, ( member(format(V, fmt(Fm)), Body), lower(V, LV), format(atom(L), "FORMATS[\"~w\"] = \"~w.\"", [LV, Fm]) ), Lines).

input_col(cvar(N), T) :- lower(N, L), format(atom(T), "(\"~w\", \"char\", None)", [L]).
input_col(nvar(N, none), T) :- lower(N, L), format(atom(T), "(\"~w\", \"num\", None)", [L]).
input_col(nvar(N, some(informat(I))), T) :- lower(N, L), format(atom(T), "(\"~w\", \"num\", \"~w\")", [L, I]).
var_name(cvar(N), L) :- lower(N, L).
var_name(nvar(N, _), L) :- lower(N, L).

% -------------------------------------------------------------- PROC SQL
% CREATE TABLE out AS select  ->  put("out", <chain>)   (scalar subqueries first)
% M3a defect 2 (2026-09-10): UNION ALL. `select_stmt(Cores, Order, Limit)` has
% held a LIST of select_cores since task 5b, but this rule only ever matched a
% one-element list, so a UNION ALL statement matched NO clause at all and the
% whole PROC SQL step vanished from the generated program (18_dashboard_mart,
% 25_final_pack: 4 branches, 0 lines emitted). Every branch is rendered now and
% they are combined with `.union(...)`, left-associated.
%
% `.union` and not `.unionByName`: SQL UNION ALL is POSITIONAL — it matches
% branches column by column, not by name — and that is exactly `DataFrame.union`.
% `unionByName` would also be wrong in practice here: only the first branch of
% 18_dashboard_mart names its columns (`'BRANCH' as metric_type, ...`), the other
% three are bare projections whose Spark column names are `LARGETXN`, `l.acct_id`
% and so on, so matching by name would raise instead of stacking the rows.
%
% The first branch sets the output schema, which is the rule sas_lineage.pl's
% select_lineage/3 already follows (task 5d, the SetSchema flag).
sql_lines(Out, select_stmt([Core|Cores], OrderOpt, _Limit), Lines) :-
    ds_key(Out, K),
    core_chain(Core, Chain0, [], Pre0),
    union_chain(Cores, Chain0, Chain, Pre0, Pre),
    order_txt(OrderOpt, OrdTxt),
    format(atom(L), "put(\"~w\", ~w~w)", [K, Chain, OrdTxt]),
    core_out_cols(Core, Cols), set_schema(K, Cols),
    append(Pre, [L], Lines).

% union_chain(+RemainingCores, +Acc, -Chain, +Pre0, -Pre): left-associated
% `a.union(b).union(c)`; Pre keeps every branch's scalar-subquery lines in
% branch order, the same way core_chain threads them within one branch.
union_chain([], Chain, Chain, P, P).
union_chain([C|Cs], Acc, Chain, P0, P) :-
    core_chain(C, T, P0, P1),
    format(atom(Acc1), "~w.union(~w)", [Acc, T]),
    union_chain(Cs, Acc1, Chain, P1, P).

order_txt(none, "").
order_txt(some(Keys), T) :- maplist(px0, Keys, Ps), atomic_list_concat(Ps, ", ", PT), format(atom(T), ".orderBy(~w)", [PT]).

% core_chain(+Core, -ChainTxt, +Pre0, -Pre): Pre collects the lines that must
% run before the chain (scalar subqueries), in order.
% task 5c: Joins is a LIST now (was `JoinOpt = none | some(join(Src,On))`);
% joins_txt/4 concatenates one ".join(...)" per list item, source order,
% still hardcoded "inner" (this pre-existing simplification — never reading
% left_join vs inner_join's own functor for the join TYPE — is unchanged).
core_chain(select_core(Cols, From, Joins, WhereOpt, GroupOpt, HavingOpt), Chain, Pre0, Pre) :-
    from_txt(From, FromTxt, Pre0, Pre1),
    joins_txt(Joins, JoinTxt, Pre1, Pre2),
    where_txt(WhereOpt, WhereTxt, Pre2, Pre3),
    select_txt(Cols, GroupOpt, SelTxt, Pre3, Pre4),
    having_txt(HavingOpt, HavTxt, Pre4, Pre),
    atomic_list_concat([FromTxt, JoinTxt, WhereTxt, SelTxt, HavTxt], Chain).

from_txt(table(D, none), T, P, P) :- ds_key(D, K), format(atom(T), "ds[\"~w\"]", [K]).
from_txt(table(D, some(A)), T, P, P) :- ds_key(D, K), lower(A, LA), format(atom(T), "ds[\"~w\"].alias(\"~w\")", [K, LA]).
from_txt(subquery(Core, none), T, P0, P) :- core_chain(Core, C, P0, P), format(atom(T), "(~w)", [C]).
from_txt(subquery(Core, some(A)), T, P0, P) :- core_chain(Core, C, P0, P), lower(A, LA), format(atom(T), "(~w).alias(\"~w\")", [C, LA]).

% task 5d: a join whose own arity is 1 (cross_join(Src): no ON) renders
% ".crossJoin(src)" instead — arity decides this, not the functor name.
joins_txt([], "", P, P).
joins_txt([J|Js], T, P0, P) :-
    functor(J, _, Arity), J =.. [_, Src|Rest], from_txt(Src, S, P0, P1),
    ( Arity =:= 2 -> [On] = Rest, px(On, O, P1, P2), format(atom(JT), ".join(~w, ~w, \"inner\")", [S, O])
    ; P2 = P1, format(atom(JT), ".crossJoin(~w)", [S]) ),
    joins_txt(Js, RestT, P2, P),
    atomic_list_concat([JT, RestT], T).

where_txt(none, "", P, P).
where_txt(some(C), T, P0, P) :- px(C, X, P0, P), format(atom(T), ".filter(~w)", [X]).

having_txt(none, "", P, P).
having_txt(some(C), T, P0, P) :- px(C, X, P0, P), format(atom(T), ".filter(~w)", [X]).

% SELECT list -> .select / .agg / .groupBy(...).agg
select_txt([proj(star, none, _)], none, ".select(\"*\")", P, P) :- !.
% task 5d: a single-item qualified star (`a.*`) — Spark's own "alias.*"
% column string expands every column of that aliased source, so this is the
% direct analogue of the bare-star fast path just above.
select_txt([proj(star(A0), none, _)], none, T, P, P) :- !, lower(A0, A), format(atom(T), ".select(\"~w.*\")", [A]).
select_txt(Cols, none, T, P0, P) :-
    ( member(proj(E, _, _), Cols), is_agg(E) ) ->
        ( maplist_pre(proj_txt, Cols, Ts, P0, P), atomic_list_concat(Ts, ", ", TT), format(atom(T), ".agg(~w)", [TT]) )
    ;   ( maplist_pre(proj_txt, Cols, Ts, P0, P), atomic_list_concat(Ts, ", ", TT), format(atom(T), ".select(~w)", [TT]) ).
select_txt(Cols, some(Keys), T, P0, P) :-
    % group keys take the alias of the projection that spells the same expression
    findall(KT, ( member(Key, Keys), key_txt(Key, Cols, KT) ), KTs), atomic_list_concat(KTs, ", ", KeysTxt),
    include(agg_proj, Cols, Aggs), maplist_pre(proj_txt, Aggs, ATs, P0, P), atomic_list_concat(ATs, ", ", AggTxt),
    format(atom(T), ".groupBy(~w).agg(~w)", [KeysTxt, AggTxt]).

agg_proj(proj(E, _, _)) :- is_agg(E).
key_txt(Key, Cols, T) :- ( member(proj(E, some(A), _), Cols), same_expr(E, Key) -> px0(Key, KP), lower(A, LA), format(atom(T), "~w.alias(\"~w\")", [KP, LA]) ; px0(Key, T) ).
same_expr(A, B) :- lower_term(A, LA), lower_term(B, LB), LA == LB.

proj_txt(proj(star, none, _), "F.col(\"*\")", P, P).
% task 5d: a qualified star (`a.*`), same idea as the bare star arm above.
proj_txt(proj(star(A0), none, _), T, P, P) :- !, lower(A0, A), format(atom(T), "F.col(\"~w.*\")", [A]).
proj_txt(proj(E, none, _), T, P0, P) :- px(E, T, P0, P).
proj_txt(proj(E, some(A), _), T, P0, P) :- px(E, X, P0, P), lower(A, LA), format(atom(T), "~w.alias(\"~w\")", [X, LA]).

maplist_pre(_, [], [], P, P).
maplist_pre(G, [X|Xs], [Y|Ys], P0, P) :- call(G, X, Y, P0, P1), maplist_pre(G, Xs, Ys, P1, P).

is_agg(call(N, _)) :- lower(N, L), memberchk(L, [sum, avg, mean, max, min, count, std, var, nmiss]).

% output columns of a core — for the schema table
% task 5d: proj_col now also sees Joins, so a qualified star (`a.*`) can
% resolve against a JOIN source's own alias, not only FROM's.
core_out_cols(select_core(Cols, From, Joins, _, _, _), Out) :-
    findall(C, ( member(proj(E, A, _), Cols), proj_col(E, A, From, Joins, C) ), Cs), flatten(Cs, Out).
proj_col(_, some(A), _, _, L) :- !, lower(A, L).
proj_col(col(N), none, _, _, L) :- !, lower(N, L).
proj_col(star, none, table(D, _), _, Cols) :- ds_key(D, K), schema(K, Cols), !.
proj_col(star(A0), none, From, Joins, Cols) :- !,
    lower(A0, A), ( alias_schema(From, Joins, A, S) -> Cols = S ; Cols = ['_auto'] ).
proj_col(_, none, _, _, '_auto').

% task 5d: the schema of whichever from_source (FROM itself, or one of its
% JOINs) carries alias Al — used by proj_col's star(Alias) clause above; same
% helper name/shape as the Rust mirrors' own alias_schema.
alias_schema(From, _Joins, Al, Cols) :- from_source_alias(From, Al), !, table_schema(From, Cols).
alias_schema(_From, Joins, Al, Cols) :- member(J, Joins), arg(1, J, Src), from_source_alias(Src, Al), !, table_schema(Src, Cols).
from_source_alias(table(_, some(A0)), Al) :- !, lower(A0, Al).
from_source_alias(subquery(_, some(A0)), Al) :- !, lower(A0, Al).
table_schema(table(D, _), Cols) :- !, ds_key(D, K), schema(K, Cols).
table_schema(_, []).

% ------------------------------------------------------------ expressions
% px(+Term, -PythonText, +Pre0, -Pre): Pre gathers scalar-subquery lines.
px0(T, P) :- px(T, P, [], _).

px(col(N), T, P, P) :- lower(N, L), format(atom(T), "F.col(\"~w\")", [L]).
px(col(A, N), T, P, P) :- lower(A, LA), lower(N, L), format(atom(T), "F.col(\"~w.~w\")", [LA, L]).
% M3a defect 1: a NUMBER leaf now folds to lit(Value, Lexeme) (specs/sas.py
% keep_lexeme=True). Only the printer reads the lexeme; every consumer below
% reads Value and ignores it, so lit/2 is handled by one clause that defers to
% the existing lit/1 clause rather than by duplicating any rule.
px(lit(V, _), T, P, P) :- !, format(atom(T), "F.lit(~w)", [V]).
px(lit(V), T, P, P) :- number(V), !, format(atom(T), "F.lit(~w)", [V]).
px(lit(V), T, P, P) :- py_str(V, S), format(atom(T), "F.lit(~w)", [S]).
% M3a defect 3 (2026-09-10): CASE WHEN ... END and the lone `.` (missing).
% CASE_FORM has folded to case_expr([when(Cond,Then)...], none|some(Else)) since
% task 5b and MISSING_FORM to `missing` since task 5d, but neither had a rule in
% either PySpark emitter: 13_risk_flags.sas's risk_band and 25_final_pack.sas's
% third UNION ALL branch fell through to no clause at all here (and made the Rust
% mirror panic, which is how `lineageq_store convert` reported them as a warn and
% stored an EMPTY program for the block).
%
% CASE maps to the PySpark chain F.when(c1, v1).when(c2, v2).otherwise(vN), with
% no `.otherwise(...)` when the source has no ELSE — that is Spark's own default
% (null), so writing one would invent a value the SAS did not name.
% A lone `.` is SAS's numeric missing value, i.e. NULL: F.lit(None).
px(case_expr(Whens, ElseOpt), T, P0, P) :- !,
    when_chain(Whens, WT, P0, P1),
    (   ElseOpt = some(E)
    ->  px(E, ET, P1, P), format(atom(T), "~w.otherwise(~w)", [WT, ET])
    ;   P = P1, T = WT ).
px(missing, "F.lit(None)", P, P) :- !.
px(star, "F.col(\"*\")", P, P).
px(star(A0), T, P, P) :- lower(A0, A), format(atom(T), "F.col(\"~w.*\")", [A]).
px(paren(E), T, P0, P) :- px(E, X, P0, P), format(atom(T), "(~w)", [X]).
px(neg(E), T, P0, P) :- px(E, X, P0, P), format(atom(T), "(-~w)", [X]).
px(not(E), T, P0, P) :- px(E, X, P0, P), format(atom(T), "(~~~w)", [X]).
px(cat(A, B), T, P0, P) :- px(A, X, P0, P1), px(B, Y, P1, P), format(atom(T), "F.concat(~w, ~w)", [X, Y]).
px(in(A, Items), T, P0, P) :- px(A, X, P0, P), maplist(py_lit, Items, Ls), atomic_list_concat(Ls, ", ", LT), format(atom(T), "~w.isin([~w])", [X, LT]).
px(subquery_expr(Core), T, P0, P) :-
    core_chain(Core, Chain, P0, P1),
    flag(scalar, N, N + 1), N1 is N + 1,
    format(atom(Line), "_scalar~w = scalar(~w)", [N1, Chain]),
    append(P1, [Line], P),
    format(atom(T), "F.lit(_scalar~w)", [N1]).
% task 5c: COUNT(DISTINCT x) -> F.countDistinct(x) — a special case ahead of
% the generic call/2 clause below, so the DISTINCT marker never reaches px/4
% as a bare operand (it has no general PySpark rule of its own; it only
% means anything as this one wrapper).
px(call(Name, [distinct(Arg)]), T, P0, P) :-
    lower(Name, count), !, px(Arg, X, P0, P), format(atom(T), "F.countDistinct(~w)", [X]).
px(call(Name, Args), T, P0, P) :-
    lower(Name, L), once(sas_fn(L, Py)),
    maplist_pre(px, Args, Xs, P0, P), atomic_list_concat(Xs, ", ", XT),
    format(atom(T), "F.~w(~w)", [Py, XT]).
px(Term, T, P0, P) :-
    Term =.. [Op, A, B], binop(Op, Sym),
    px(A, X, P0, P1), px(B, Y, P1, P), format(atom(T), "(~w ~w ~w)", [X, Sym, Y]).

binop(mul, "*"). binop(div, "/"). binop(add, "+"). binop(sub, "-").
binop(eq, "=="). binop(ne, "!="). binop(lt, "<"). binop(le, "<="). binop(gt, ">"). binop(ge, ">=").
binop(and, "&"). binop(or, "|").

% SAS function -> pyspark.sql.functions name. One line per function.
sas_fn(month, month).  sas_fn(year, year).  sas_fn(day, dayofmonth).
sas_fn(sum, sum).  sas_fn(avg, avg).  sas_fn(mean, avg).  sas_fn(max, max).  sas_fn(min, min).  sas_fn(count, count).
sas_fn(upcase, upper).  sas_fn(lowcase, lower).  sas_fn(abs, abs).  sas_fn(round, round).  sas_fn(substr, substring).
sas_fn(F, _) :- \+ clause(sas_fn(F, _), true), format(user_error, "LINEAGEQ: no PySpark mapping for SAS function ~w~n", [F]), fail.

py_lit(lit(V, _), T) :- !, format(atom(T), "~w", [V]).
py_lit(lit(V), T) :- number(V), !, format(atom(T), "~w", [V]).
py_lit(lit(V), T) :- py_str(V, T).

% ----------------------------------------------------------------- helpers
ds_key(ds(L, N), K) :- lower(L, LL), lower(N, LN), format(atom(K), "~w.~w", [LL, LN]).
ds_key(ds(N), K) :- lower(N, LN), format(atom(K), "work.~w", [LN]).
set_schema(K, Cols) :- retractall(schema(K, _)), assertz(schema(K, Cols)).
lower(A, L) :- ( atom(A) -> downcase_atom(A, L) ; L = A ).
lower_term(T, L) :- ( atom(T) -> downcase_atom(T, L) ; compound(T) -> T =.. [F|As], maplist(lower_term, As, Ls), L =.. [F|Ls] ; L = T ).
% a Python double-quoted string literal: backslash and quote escaped, newline as \n
py_str(A, S) :-
    atom_codes(A, Cs), py_esc(Cs, Es), atom_codes(Body, Es), format(atom(S), "\"~w\"", [Body]).
py_esc([], []).
py_esc([0'\\|Cs], [0'\\, 0'\\|Es]) :- !, py_esc(Cs, Es).
py_esc([0'"|Cs], [0'\\, 0'"|Es]) :- !, py_esc(Cs, Es).
py_esc([0'\n|Cs], [0'\\, 0'n|Es]) :- !, py_esc(Cs, Es).
py_esc([C|Cs], [C|Es]) :- py_esc(Cs, Es).

% M3a defect 3: the CASE chain helpers, kept below every px clause so
% px's own clauses stay contiguous (SWI warns otherwise).
when_chain([when(C, V)|Ws], T, P0, P) :-
    px(C, CT, P0, P1), px(V, VT, P1, P2),
    format(atom(T0), "F.when(~w, ~w)", [CT, VT]),
    when_rest(Ws, T0, T, P2, P).
when_rest([], T, T, P, P).
when_rest([when(C, V)|Ws], Acc, T, P0, P) :-
    px(C, CT, P0, P1), px(V, VT, P1, P2),
    format(atom(Acc1), "~w.when(~w, ~w)", [Acc, CT, VT]),
    when_rest(Ws, Acc1, T, P2, P).
