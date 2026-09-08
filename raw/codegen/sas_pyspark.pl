% codegen/sas_pyspark.pl — SAS node/4 -> PySpark, in Prolog (exp_42, 2026-09-05).
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
    memberchk(if_then_set(_, lit(1), Look), Body), memberchk(set(In), Body), !,
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
sql_lines(Out, select_stmt([Core], OrderOpt, _Limit), Lines) :-
    ds_key(Out, K),
    core_chain(Core, Chain, [], Pre),
    order_txt(OrderOpt, OrdTxt),
    format(atom(L), "put(\"~w\", ~w~w)", [K, Chain, OrdTxt]),
    core_out_cols(Core, Cols), set_schema(K, Cols),
    append(Pre, [L], Lines).

order_txt(none, "").
order_txt(some(Keys), T) :- maplist(px0, Keys, Ps), atomic_list_concat(Ps, ", ", PT), format(atom(T), ".orderBy(~w)", [PT]).

% core_chain(+Core, -ChainTxt, +Pre0, -Pre): Pre collects the lines that must
% run before the chain (scalar subqueries), in order.
core_chain(select_core(Cols, From, JoinOpt, WhereOpt, GroupOpt, HavingOpt), Chain, Pre0, Pre) :-
    from_txt(From, FromTxt, Pre0, Pre1),
    join_txt(JoinOpt, JoinTxt, Pre1, Pre2),
    where_txt(WhereOpt, WhereTxt, Pre2, Pre3),
    select_txt(Cols, GroupOpt, SelTxt, Pre3, Pre4),
    having_txt(HavingOpt, HavTxt, Pre4, Pre),
    atomic_list_concat([FromTxt, JoinTxt, WhereTxt, SelTxt, HavTxt], Chain).

from_txt(table(D, none), T, P, P) :- ds_key(D, K), format(atom(T), "ds[\"~w\"]", [K]).
from_txt(table(D, some(A)), T, P, P) :- ds_key(D, K), lower(A, LA), format(atom(T), "ds[\"~w\"].alias(\"~w\")", [K, LA]).
from_txt(subquery(Core, none), T, P0, P) :- core_chain(Core, C, P0, P), format(atom(T), "(~w)", [C]).
from_txt(subquery(Core, some(A)), T, P0, P) :- core_chain(Core, C, P0, P), lower(A, LA), format(atom(T), "(~w).alias(\"~w\")", [C, LA]).

join_txt(none, "", P, P).
join_txt(some(join(Src, On)), T, P0, P) :- from_txt(Src, S, P0, P1), px(On, O, P1, P), format(atom(T), ".join(~w, ~w, \"inner\")", [S, O]).

where_txt(none, "", P, P).
where_txt(some(C), T, P0, P) :- px(C, X, P0, P), format(atom(T), ".filter(~w)", [X]).

having_txt(none, "", P, P).
having_txt(some(C), T, P0, P) :- px(C, X, P0, P), format(atom(T), ".filter(~w)", [X]).

% SELECT list -> .select / .agg / .groupBy(...).agg
select_txt([proj(star, none)], none, ".select(\"*\")", P, P) :- !.
select_txt(Cols, none, T, P0, P) :-
    ( member(proj(E, _), Cols), is_agg(E) ) ->
        ( maplist_pre(proj_txt, Cols, Ts, P0, P), atomic_list_concat(Ts, ", ", TT), format(atom(T), ".agg(~w)", [TT]) )
    ;   ( maplist_pre(proj_txt, Cols, Ts, P0, P), atomic_list_concat(Ts, ", ", TT), format(atom(T), ".select(~w)", [TT]) ).
select_txt(Cols, some(Keys), T, P0, P) :-
    % group keys take the alias of the projection that spells the same expression
    findall(KT, ( member(Key, Keys), key_txt(Key, Cols, KT) ), KTs), atomic_list_concat(KTs, ", ", KeysTxt),
    include(agg_proj, Cols, Aggs), maplist_pre(proj_txt, Aggs, ATs, P0, P), atomic_list_concat(ATs, ", ", AggTxt),
    format(atom(T), ".groupBy(~w).agg(~w)", [KeysTxt, AggTxt]).

agg_proj(proj(E, _)) :- is_agg(E).
key_txt(Key, Cols, T) :- ( member(proj(E, some(A)), Cols), same_expr(E, Key) -> px0(Key, KP), lower(A, LA), format(atom(T), "~w.alias(\"~w\")", [KP, LA]) ; px0(Key, T) ).
same_expr(A, B) :- lower_term(A, LA), lower_term(B, LB), LA == LB.

proj_txt(proj(star, none), "F.col(\"*\")", P, P).
proj_txt(proj(E, none), T, P0, P) :- px(E, T, P0, P).
proj_txt(proj(E, some(A)), T, P0, P) :- px(E, X, P0, P), lower(A, LA), format(atom(T), "~w.alias(\"~w\")", [X, LA]).

maplist_pre(_, [], [], P, P).
maplist_pre(G, [X|Xs], [Y|Ys], P0, P) :- call(G, X, Y, P0, P1), maplist_pre(G, Xs, Ys, P1, P).

is_agg(call(N, _)) :- lower(N, L), memberchk(L, [sum, avg, mean, max, min, count, std, var, nmiss]).

% output columns of a core — for the schema table
core_out_cols(select_core(Cols, From, _, _, _, _), Out) :-
    findall(C, ( member(proj(E, A), Cols), proj_col(E, A, From, C) ), Cs), flatten(Cs, Out).
proj_col(_, some(A), _, L) :- !, lower(A, L).
proj_col(col(N), none, _, L) :- !, lower(N, L).
proj_col(star, none, table(D, _), Cols) :- ds_key(D, K), schema(K, Cols), !.
proj_col(_, none, _, '_auto').

% ------------------------------------------------------------ expressions
% px(+Term, -PythonText, +Pre0, -Pre): Pre gathers scalar-subquery lines.
px0(T, P) :- px(T, P, [], _).

px(col(N), T, P, P) :- lower(N, L), format(atom(T), "F.col(\"~w\")", [L]).
px(col(A, N), T, P, P) :- lower(A, LA), lower(N, L), format(atom(T), "F.col(\"~w.~w\")", [LA, L]).
px(lit(V), T, P, P) :- number(V), !, format(atom(T), "F.lit(~w)", [V]).
px(lit(V), T, P, P) :- py_str(V, S), format(atom(T), "F.lit(~w)", [S]).
px(star, "F.col(\"*\")", P, P).
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
