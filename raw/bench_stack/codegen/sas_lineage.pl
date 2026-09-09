% codegen/sas_lineage.pl — SAS node/4 -> column lineage facts (exp_42, 2026-09-07).
%
% Fix round 1 (2026-09-09): every proj(...) pattern in this file was arity-2
% (proj(Expr,AliasOpt)) while pipeline/specs/sas.py's PROJ has built arity-3
% (proj(Expr,AliasOpt,LengthOpt)) since task 5b's LENGTH support — this file was
% never touched or tested in 5b, so every proj/2 clause here silently matched
% nothing. run_all.sh step 4's Prolog-vs-Rust byte-diff caught it: this file was
% dropping the entire body of every CREATE TABLE AS SELECT. Fixed by widening
% every proj/2 to proj/3 (the third arg unused here, matched with `_`).
%
% Why: loop 2. One clause per SAS step shape says which output column comes
% from which input column, and which input columns decide the rows. The input
% is ONLY the node/4 fact file; the SAS text is never read. rust_engine/src/
% lineage.rs is the same rule set in Rust; the two fact files are diffed.
%
%   swipl -q -s codegen/sas_lineage.pl -g main -- out/ir/sas/<stem>.node4.pl out/loops/lineage/<stem>.sas.prolog.pl
:- consult('lineage_common.pl').

main :-
    current_prolog_flag(argv, [Node4, Out]),
    style_check(-discontiguous), consult(Node4),
    blocks(Bs), forall(member(B, Bs), (block_terms(B, Ts), once(step(Ts)))),
    write_facts(Out), halt(0).
main :- format(user_error, "usage: swipl -q -s codegen/sas_lineage.pl -g main -- node4.pl out.pl~n", []), halt(1).

% ----------------------------------------------------------------- steps
% DATA out; INPUT vars; DATALINES  ->  a source: schema only
step([data(Out)|Body]) :-
    memberchk(input(Vars), Body), memberchk(datalines(_), Body), !,
    ds_key(Out, K), maplist(var_name, Vars, Names), set_schema(K, Names).

% DATA out; IF _N_ = 1 THEN SET look; SET main  ->  every column of both rides along
step([data(Out)|Body]) :-
    memberchk(if_then_set(_, lit(1), Look), Body), memberchk(set(In), Body), !,
    ds_key(Out, K), ds_key(In, KI), ds_key(Look, KL),
    reads(K, KI), reads(K, KL), copy_cols(K, KI), copy_cols(K, KL),
    schema_or_empty(KI, C1), schema_or_empty(KL, C2), append(C1, C2, C0), list_to_set(C0, Cols), set_schema(K, Cols).

% DATA out; SET in; IF cond ...  ->  columns copied; the IF's columns control the rows
step([data(Out)|Body]) :-
    memberchk(set(In), Body), !,
    ds_key(Out, K), ds_key(In, KI),
    reads(K, KI), copy_cols(K, KI),
    forall(member(subset_if(C), Body), (expr_cols(C, Cs), controls(K, KI, Cs))),
    schema_or_empty(KI, Cols), set_schema(K, Cols).

% DATA out; MERGE a b; BY keys  ->  union of columns; the BY keys control the match on every source
step([data(Out)|Body]) :-
    memberchk(merge(Srcs), Body), !,
    ds_key(Out, K), ( memberchk(by(Keys0), Body) -> maplist(lower, Keys0, Keys) ; Keys = [] ),
    forall(member(src(D, _), Srcs), (ds_key(D, KD), reads(K, KD), copy_cols(K, KD), controls(K, KD, Keys))),
    findall(C, ( member(src(D, _), Srcs), ds_key(D, KD), schema_or_empty(KD, Cs), member(C, Cs) ), C0),
    list_to_set(C0, Cols), set_schema(K, Cols).

% PROC SQL; CREATE TABLE out AS SELECT ...  (one per statement in the step)
% task 5d (root cause U): Cores is every select_core in a `select_core (UNION
% ALL select_core)*` chain — was matched as `[Core|_]`, the FIRST branch only,
% silently dropping every other branch's reads (18_dashboard_mart.sas,
% 25_final_pack.sas: 4 branches, 1 recorded). select_lineage_all/2 walks every
% branch for its reads/controls/col-lineage; only the FIRST branch's own
% projection list decides Out's output schema — real SQL UNION ALL takes its
% output column names from the first SELECT, later branches line up
% positionally, not by name.
step([proc_sql|Body]) :- !,
    forall(member(create_table_as(Out, select_stmt(Cores, _, _)), Body), (ds_key(Out, K), select_lineage_all(K, Cores))).

step(_).   % LIBNAME, PROC PRINT, TITLE, RUN: no lineage

select_lineage_all(K, [First|Rest]) :-
    select_lineage(K, First, true),
    forall(member(C, Rest), select_lineage(K, C, false)).

var_name(cvar(N), L) :- lower(N, L).
var_name(nvar(N, _), L) :- lower(N, L).

% ---------------------------------------------------------------- SELECT
% task 5c: Joins is a LIST (zero or more left_join(Src,On)/inner_join(Src,On)
% terms, source order) — was `JoinOpt = none | some(join(Src,On))` (at most one,
% and under the stale functor name "join" that this file's own grammar never
% actually produced — left_join/inner_join, see pipeline/specs/sas.py).
% task 5d: two more widenings, both required for the join list to hold a
% `cross_join(Src)` term (arity 1, no ON) alongside left_join/inner_join
% (arity 2):
%   1. J's own arity (not its functor name) decides whether an ON exists —
%      `functor(J, _, Arity)` — matching the Rust mirror (lineage.rs's
%      select_lineage, same task) and the spec comment's own reasoning at
%      join_clause's RULES entry.
%   2. select_lineage/3: SetSchema is `true` only for the first branch of a
%      `select_stmt (UNION ALL select_core)*` chain (root cause U, see
%      select_lineage_all/2 above) — every branch still records its own
%      reads/controls/col-lineage.
%   AliasMap (an assoc-free plain list of Alias-Key pairs, built from From and
%   every Join's own Src) resolves a qualified star `a.*` to the ds_key `a`
%   actually names — see proj_lineage/5 below.
select_lineage(K, select_core(Projs, From, Joins, WhereOpt, GroupOpt, HavingOpt), SetSchema) :-
    from_ds(From, KI), reads(K, KI),
    from_alias_pair(From, KI, A0),
    foldl(join_step(K, KI), Joins, A0, AliasMap),
    findall(C, ( member(proj(E, A, _), Projs), proj_lineage(K, KI, AliasMap, E, A, C) ), Cs0), flatten(Cs0, Cols),
    ( SetSchema == true -> set_schema(K, Cols) ; true ),
    ( WhereOpt = some(W) -> cond_lineage(K, KI, W) ; true ),
    ( GroupOpt = some(Keys) -> forall(member(G, Keys), (expr_cols(G, GCs), controls(K, KI, GCs))) ; true ),
    ( HavingOpt = some(H) -> cond_lineage(K, KI, H) ; true ).

% one JOIN item folded into the running (Src alias -> ds_key) list
join_step(K, KI, J, AccIn, AccOut) :-
    functor(J, _, Arity), J =.. [_, Src|Rest],
    from_ds(Src, KJ), reads(K, KJ),
    from_alias_pair(Src, KJ, P),
    ( Arity =:= 2 -> [On] = Rest, expr_cols(On, OnCs), controls(K, KI, OnCs), controls(K, KJ, OnCs)
    ; true ),   % cross_join(Src): no ON clause, so no controlling columns on either side
    append(P, AccIn, AccOut).

from_alias_pair(table(_, some(A0)), K, [A-K]) :- !, lower(A0, A).
from_alias_pair(subquery(_, some(A0)), K, [A-K]) :- !, lower(A0, A).
from_alias_pair(_, _, []).

from_ds(table(D, _), K) :- ds_key(D, K).
from_ds(subquery(select_core(_, From, _, _, _, _), _), K) :- from_ds(From, K).   % lineage passes through the inner FROM

% one projection: its output column, and the input columns it depends on
proj_lineage(K, KI, _AliasMap, star, none, Cols) :- !, schema_or_empty(KI, Cols), copy_cols(K, KI).
% task 5d: a qualified star `a.*` copies the columns of whatever source `a`
% names (the FROM table or any JOIN source's own alias), not always KI —
% AliasMap (built by select_lineage/3, above) is exactly that lookup. Falls
% back to KI if the alias is unresolved (defensive, mirrors the Rust side;
% should not happen — every alias here was just read off From/Joins itself).
proj_lineage(K, KI, AliasMap, star(A0), none, Cols) :- !,
    lower(A0, A), ( memberchk(A-Src, AliasMap) -> true ; Src = KI ),
    schema_or_empty(Src, Cols), copy_cols(K, Src).
proj_lineage(K, KI, _AliasMap, E, Alias, Col) :-
    ( Alias = some(A) -> lower(A, Col) ; E = col(N) -> lower(N, Col) ; Col = '_auto' ),
    expr_cols(E, Cs), forall(member(C, Cs), assertz(col_lineage(K, Col, KI, C))).

% a WHERE / HAVING: its columns control the rows; a scalar subquery inside it is read too
cond_lineage(K, KI, W) :-
    expr_cols(W, Cs), controls(K, KI, Cs),
    forall(sub_term_of(subquery_expr(select_core(Projs, From, _, _, _, _)), W),
           ( from_ds(From, KS), reads(K, KS),
             findall(C, ( member(proj(E, _, _), Projs), expr_cols(E, ECs), member(C, ECs) ), SCs), controls(K, KS, SCs) )).

sub_term_of(X, T) :- X = T.
sub_term_of(X, T) :- compound(T), T =.. [_|As], member(A, As), sub_term_of(X, A).

% ----------------------------------------------------------- expressions
% expr_cols(+Expr, -Cols): the column names an expression reads (not inside a subquery)
expr_cols(col(N), [L]) :- !, lower(N, L).
expr_cols(col(_, N), [L]) :- !, lower(N, L).
expr_cols(lit(_), []) :- !.
expr_cols(star, []) :- !.
expr_cols(star(_), []) :- !.   % task 5d: a qualified star `a.*` — proj_lineage/6, not expr_cols, resolves it
expr_cols(subquery_expr(_), []) :- !.
expr_cols(call(_, Args), Cs) :- !, maplist(expr_cols, Args, Css), append(Css, Cs0), list_to_set(Cs0, Cs).
expr_cols(in(A, Items), Cs) :- !, expr_cols(A, C1), maplist(expr_cols, Items, Css), append([C1|Css], Cs0), list_to_set(Cs0, Cs).
expr_cols(T, Cs) :- compound(T), !, T =.. [_|As], maplist(expr_cols, As, Css), append(Css, Cs0), list_to_set(Cs0, Cs).
expr_cols(_, []).
