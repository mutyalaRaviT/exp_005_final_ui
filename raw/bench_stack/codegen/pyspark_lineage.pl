% codegen/pyspark_lineage.pl — PySpark node/4 -> column lineage facts (exp_42, 2026-09-07).
%
% Why: loop 2's other half. The PySpark job was parsed by its own pyDSL
% (pipeline/specs/pyspark.py); these clauses read that node/4 and write the
% same four facts sas_lineage.pl writes, so the two files can be diffed.
% One clause per DataFrame method, one per runtime helper (sas_datalines,
% sas_merge, sas_attach_first_row, scalar). rust_engine/src/py_lineage.rs is
% the mirror.
%
%   swipl -q -s codegen/pyspark_lineage.pl -g main -- out/ir/pyspark/<stem>.node4.pl out/loops/lineage/<stem>.py.prolog.pl
:- consult('lineage_common.pl').
:- dynamic bound/2.     % bound(Name, Expr): an assignment seen in the current block (scalar subqueries)

main :-
    current_prolog_flag(argv, [Node4, Out]),
    style_check(-discontiguous), consult(Node4),
    blocks(Bs), forall(member(B, Bs), (block_terms(B, Ts), retractall(bound(_, _)), forall(member(T, Ts), once(stmt(T))))),
    write_facts(Out), halt(0).
main :- format(user_error, "usage: swipl -q -s codegen/pyspark_lineage.pl -g main -- node4.pl out.pl~n", []), halt(1).

% ------------------------------------------------------------ statements
stmt(assign(Name, E)) :- assertz(bound(Name, E)).
stmt(put(lit(Out0), Df)) :- lower(Out0, Out), df_lineage(Out, Df, Cols), set_schema(Out, Cols).
stmt(_).                                   % set_item, for_in, expr_stmt, imports: no lineage

% ---------------------------------------------- df_lineage(+Out, +Expr, -Cols)
% sas_datalines(spark, columns=[(name, kind, informat), ...], rows=...)  ->  a source
df_lineage(_, call(sas_datalines, Args), Cols) :- !,
    memberchk(kwarg(columns, list(Items)), Args),
    findall(L, ( member(tuple(lit(N), _), Items), lower(N, L) ), Cols).

% sas_merge(spark, [("name", ds["name"]), ...], by=[...])
df_lineage(Out, call(sas_merge, Args), Cols) :- !,
    memberchk(list(Srcs), Args),
    ( memberchk(kwarg(by, list(Keys0)), Args) -> findall(L, (member(lit(K), Keys0), lower(K, L)), Keys) ; Keys = [] ),
    forall(member(tuple(lit(N0), _), Srcs), (lower(N0, N), reads(Out, N), copy_cols(Out, N), controls(Out, N, Keys))),
    findall(C, ( member(tuple(lit(N0), _), Srcs), lower(N0, N), schema_or_empty(N, Cs), member(C, Cs) ), C0), list_to_set(C0, Cols).

% sas_attach_first_row(ds["main"], ds["look"])
df_lineage(Out, call(sas_attach_first_row, [index(ds, lit(M0)), index(ds, lit(L0))]), Cols) :- !,
    lower(M0, M), lower(L0, L),
    reads(Out, M), reads(Out, L), copy_cols(Out, M), copy_cols(Out, L),
    schema_or_empty(M, C1), schema_or_empty(L, C2), append(C1, C2, C0), list_to_set(C0, Cols).

% a method chain: root, then each method in order, carrying the column state:
%   pass(Cols)     no projection yet — the input columns flow through unchanged
%   proj(Cols)     a select/agg named the output columns
%   grouped(Keys)  a groupBy named the key columns; the .agg that follows appends to them
% A chain that ends in pass(Cols) copies every column (DATA out; SET in; IF ...).
df_lineage(Out, Chain, Cols) :-
    chain(Chain, Root, Methods),
    root_ds(Root, In), reads(Out, In),
    schema_or_empty(In, Cols0),
    foldl(method(Out, In), Methods, pass(Cols0), State),
    ( State = pass(Cols) -> copy_cols(Out, In) ; State = proj(Cols) ; State = grouped(Cols) ).

chain(dot(Obj, call(M, Args)), Root, Ms) :- !, chain(Obj, Root, Ms0), append(Ms0, [call(M, Args)], Ms).
chain(Root, Root, []).

root_ds(index(ds, lit(N0)), N) :- lower(N0, N).
root_ds(paren(E), N) :- chain(E, R, _), root_ds(R, N).

% ---------------------------------------------------------------- methods
% .filter(cond): the columns the condition reads control the rows
method(Out, In, call(filter, [Cond]), S, S) :- !, cond_lineage(Out, In, Cond).
method(Out, In, call(where, [Cond]), S, S) :- !, cond_lineage(Out, In, Cond).
% .select("*"): every current column copied
method(Out, In, call(select, [lit(*)]), S, proj(Cols)) :- !, state_cols(S, Cols), forall(member(C, Cols), assertz(col_lineage(Out, C, In, C))).
% .select(e, ...): one output column per expression
method(Out, In, call(select, Es), _, proj(Cols)) :- !, maplist(proj_lineage(Out, In), Es, Cols).
% .agg(e, ...): one output column per expression, after the groupBy keys if there were any
method(Out, In, call(agg, Es), S, proj(Cols)) :- !,
    maplist(proj_lineage(Out, In), Es, ACols),
    ( S = grouped(Keys) -> append(Keys, ACols, Cols) ; Cols = ACols ).
% .groupBy(k, ...): keys become output columns and control the grouping
method(Out, In, call(groupBy, Ks), _, grouped(Cols)) :- !,
    maplist(proj_lineage(Out, In), Ks, Cols),
    forall(member(K, Ks), (expr_cols(K, KCs), controls(Out, In, KCs))).
method(_, _, call(alias, _), S, S) :- !.
method(_, _, call(orderBy, _), S, S) :- !.
method(_, _, call(limit, _), S, S) :- !.
method(_, _, call(M, _), S, S) :- format(user_error, "LINEAGEQ: no lineage rule for .~w()~n", [M]).

state_cols(pass(Cols), Cols).
state_cols(proj(Cols), Cols).
state_cols(grouped(Cols), Cols).

% one projection expression -> its output column name
proj_lineage(Out, In, dot(E, call(alias, [lit(A0)])), Col) :- !, lower(A0, Col), expr_cols(E, Cs), forall(member(C, Cs), assertz(col_lineage(Out, Col, In, C))).
proj_lineage(Out, In, E, Col) :- ( pycol(E, Col) -> true ; Col = '_auto' ), expr_cols(E, Cs), forall(member(C, Cs), assertz(col_lineage(Out, Col, In, C))).

% a filter condition: its columns control; a scalar bound in this block is a read of another dataset
cond_lineage(Out, In, Cond) :-
    expr_cols(Cond, Cs), controls(Out, In, Cs),
    forall(( sub_term_of(col(V), Cond), bound(V, call(scalar, [Sub])) ),
           ( chain(Sub, Root, Ms), root_ds(Root, KS), reads(Out, KS),
             findall(C, ( member(call(select, Es), Ms), member(E, Es), expr_cols(E, ECs), member(C, ECs) ), SCs), controls(Out, KS, SCs) )).

sub_term_of(X, T) :- X = T.
sub_term_of(X, T) :- compound(T), T =.. [_|As], member(A, As), sub_term_of(X, A).

% ----------------------------------------------------------- expressions
pycol(dot(col('F'), call(col, [lit(N0)])), N) :- lower(N0, N).
% expr_cols(+Expr, -Cols): the column names an expression reads — F.col("x") and nothing else
expr_cols(E, [N]) :- pycol(E, N), !.
expr_cols(lit(_), []) :- !.
expr_cols(col(_), []) :- !.
expr_cols(T, Cs) :- compound(T), !, T =.. [_|As], maplist(expr_cols, As, Css), append(Css, Cs0), list_to_set(Cs0, Cs).
expr_cols(_, []).
