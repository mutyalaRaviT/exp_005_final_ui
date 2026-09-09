% codegen/sas_interp.pl — the executable node/4: run a SAS program's node/4 on data (exp_42, 2026-09-07).
%
% Why: loops 3 and 4 need the SAS side to RUN, and SAS is not on this machine.
% exp_009's idea: an interpreter over the IR proves the parse by the answers it
% produces. This file executes the same node/4 the PySpark was generated from,
% and writes every dataset as a CSV in the convention sas_print uses (integers
% bare, floats with 12 significant digits, dates by their format, missing as .)
% so the two sides diff byte for byte. rust_engine/src/interp.rs is the mirror.
%
%   swipl -q -s codegen/sas_interp.pl -g main -- <node4.pl> <data_dir> <out_dir> [Block]
%   file mode  (no Block): every block in order; DATALINES are the sources.
%   block mode (Block):    every <data_dir>/<lib.name>.csv (+ .schema.json) is loaded first
%                          as an existing dataset, then only that block runs.
% A dataset lives as dataset(Key, Cols, Rows): Cols = [col(Name, Type)], Type in num|char|date,
% Rows = lists of values; a value is a number, an atom (char), or `missing`.
% A date is a number of days since 1960-01-01, SAS's own representation.
:- use_module(library(http/json)).
:- dynamic node/4, dataset/3, order/1, fmt/2.

main :-
    current_prolog_flag(argv, Argv), style_check(-discontiguous),
    ( Argv = [Node4, DataDir, OutDir] -> Block = all ; Argv = [Node4, DataDir, OutDir, Block] ),
    consult(Node4),
    ( Block == all -> true ; load_inputs(DataDir) ),
    blocks(Bs),
    forall(member(B, Bs), ( (Block == all ; Block == B) -> block_terms(B, Ts), run_step(Ts) ; true )),
    make_directory_path(OutDir),
    forall(order(K), write_csv(OutDir, K)),
    halt(0).
main :- format(user_error, "usage: swipl -q -s codegen/sas_interp.pl -g main -- node4.pl data_dir out_dir [block]~n", []), halt(1).

blocks(Bs) :- findall(B, node(B, _, _, _), Bs0), list_to_set(Bs0, Bs).
block_terms(B, Ts) :- findall(Seq-T, node(B, Seq, T, _), Ps), keysort(Ps, Sorted), pairs_values(Sorted, Ts).
lower(A, L) :- ( atom(A) -> downcase_atom(A, L) ; L = A ).
ds_key(ds(L, N), K) :- lower(L, LL), lower(N, LN), format(atom(K), "~w.~w", [LL, LN]).
ds_key(ds(N), K) :- lower(N, LN), format(atom(K), "work.~w", [LN]).

% put/3: a step creates a dataset — replace if it exists, remember creation order
put(K, Cols, Rows) :- retractall(dataset(K, _, _)), assertz(dataset(K, Cols, Rows)), ( order(K) -> true ; assertz(order(K)) ).
get(K, Cols, Rows) :- ( dataset(K, Cols, Rows) -> true ; format(user_error, "ERROR: dataset ~w does not exist~n", [K]), Cols = [], Rows = [] ).

% ------------------------------------------------------------------ steps
run_step(Ts) :- once(step(Ts)).

% DATA out; INPUT vars; [FORMAT v f.;] DATALINES; rows
step([data(Out)|Body]) :-
    memberchk(input(Vars), Body), memberchk(datalines(Text), Body),
    ds_key(Out, K), maplist(input_col, Vars, Cols),
    remember_formats(Body),
    split_string(Text, "\n", "\r", Lines0), exclude(==(""), Lines0, Lines),
    findall(Row, ( member(L, Lines), split_string(L, " \t", " \t", Toks0), exclude(==(""), Toks0, Toks), Toks \== [],
                   read_row(Vars, Toks, Row) ), Rows),
    put(K, Cols, Rows).

% DATA out; IF _N_ = 1 THEN SET look; SET main  ->  main's rows, each carrying look's first row
step([data(Out)|Body]) :-
    memberchk(if_then_set(_, lit(1), Look), Body), memberchk(set(In), Body),
    ds_key(Out, K), ds_key(In, KI), ds_key(Look, KL), remember_formats(Body),
    get(KI, C1, R1), get(KL, C2, R2),
    ( R2 = [First|_] -> true ; length(C2, N2), length(First, N2), maplist(=(missing), First) ),
    append(C1, C2, Cols),
    findall(Row, ( member(R, R1), append(R, First, Row) ), Rows),
    put(K, Cols, Rows).

% DATA out; SET in; IF cond; ...  ->  keep the rows every IF accepts (SAS: missing compares low)
step([data(Out)|Body]) :-
    memberchk(set(In), Body),
    ds_key(Out, K), ds_key(In, KI), remember_formats(Body), get(KI, Cols, R0),
    findall(C, member(subset_if(C), Body), Conds),
    include(row_passes(Cols, Conds), R0, Rows),
    put(K, Cols, Rows).

% DATA out; MERGE a(in=x) b(in=y); BY keys  ->  full outer join on the keys, ordered by them
step([data(Out)|Body]) :-
    memberchk(merge(Srcs), Body),
    ds_key(Out, K), ( memberchk(by(Keys0), Body) -> maplist(lower, Keys0, Keys) ; Keys = [] ),
    findall(KD-cr(Cs, Rs), ( member(src(D, _), Srcs), ds_key(D, KD), get(KD, Cs, Rs) ), Sources),
    findall(C, ( member(_-cr(Cs, _), Sources), member(C, Cs) ), Cols0), col_union(Cols0, Cols),
    findall(KD-Key, ( member(KD-cr(Cs, _), Sources), member(Key, Keys), \+ memberchk(col(Key, _), Cs) ), Missing),
    ( Missing \== [] ->
        forall(member(KD-Key, Missing), ( upcase_atom(Key, UK), upcase_atom(KD, UD), format("ERROR: BY variable ~w is not on input data set ~w.~n", [UK, UD]) )),
        format("NOTE: The SAS System stopped processing this step because of errors. The data set is created with 0 observations.~n"),
        put(K, Cols, [])
    ;   merge_rows(Sources, Keys, Cols, Rows), put(K, Cols, Rows) ).

% PROC SQL; CREATE TABLE out AS SELECT ...; ...
step([proc_sql|Body]) :-
    forall(member(create_table_as(Out, Sel), Body), ( ds_key(Out, K), select_stmt(Sel, Cols, Rows), put(K, Cols, Rows) )).

step(_).   % LIBNAME, PROC PRINT, TITLE, RUN, QUIT

remember_formats(Body) :- forall(member(format(V, fmt(F)), Body), ( lower(V, LV), retractall(fmt(LV, _)), assertz(fmt(LV, F)) )).

input_col(cvar(N), col(L, char)) :- lower(N, L).
input_col(nvar(N, none), col(L, num)) :- lower(N, L).
input_col(nvar(N, some(informat(_))), col(L, date)) :- lower(N, L).

% list input: one token per variable; a missing token at the end is a missing value
read_row([], _, []).
read_row([_|Vs], [], [missing|Rest]) :- !, read_row(Vs, [], Rest).
read_row([V|Vs], [T|Ts], [X|Rest]) :- read_value(V, T, X), read_row(Vs, Ts, Rest).
read_value(cvar(_), T, A) :- atom_string(A, T).
read_value(nvar(_, none), T, X) :- ( T == "." -> X = missing ; number_string(X, T) ).
read_value(nvar(_, some(informat(I))), T, X) :- informat_date(I, T, X).

informat_date(I, T, Days) :-
    downcase_atom(I, LI),
    ( sub_atom(LI, 0, _, _, mmddyy) -> split_string(T, "/", "", [M, D, Y])
    ; sub_atom(LI, 0, _, _, ddmmyy) -> split_string(T, "/", "", [D, M, Y])
    ; sub_atom(LI, 0, _, _, yymmdd) -> split_string(T, "-", "", [Y, M, D])
    ; format(user_error, "informat not supported: ~w~n", [I]), fail ),
    number_string(Yn, Y), number_string(Mn, M), number_string(Dn, D), sas_days(Yn, Mn, Dn, Days).

% ---------------------------------------------------------------- filters
row_passes(Cols, Conds, Row) :- forall(member(C, Conds), ( eval(C, Cols, Row, V), truthy(V) )).
truthy(V) :- number(V), V =\= 0.

% ------------------------------------------------------------------ merge
% full outer join on the BY keys: the union of key values, in sorted order; for each key
% value the rows from every source are paired positionally (one-to-one and one-to-many
% the SAS way: the shorter source's last row is retained).
merge_rows(Sources, Keys, Cols, Rows) :-
    findall(KV, ( member(_-cr(Cs, Rs), Sources), member(R, Rs), key_of(Keys, Cs, R, KV) ), KVs0),
    predsort(cmp_keys, KVs0, KVs),          % SAS order: missing first, then by value; equal keys collapse
    findall(Row, ( member(KV, KVs), merge_group(Sources, Keys, Cols, KV, Row) ), Rows).

key_of(Keys, Cs, R, KV) :- findall(V, ( member(Key, Keys), value_of(Key, Cs, R, V) ), KV).

merge_group(Sources, Keys, Cols, KV, Row) :-
    findall(Cs-Group, ( member(_-cr(Cs, Rs), Sources), findall(R, ( member(R, Rs), key_of(Keys, Cs, R, KV) ), Group) ), Groups),
    findall(N, ( member(_-G, Groups), length(G, N) ), Ns), max_list(Ns, Max),
    between(1, Max, I),
    findall(C-V, ( member(col(C, _), Cols), ( member(Cs-G, Groups), memberchk(col(C, _), Cs), nth_or_last(I, G, R), value_of(C, Cs, R, V) -> true ; V = missing ) ), Pairs),
    pairs_values(Pairs, Row).

% the I-th row, or the last one when the group is shorter (SAS retains it); fails on an empty group
nth_or_last(_, [], _) :- !, fail.
nth_or_last(I, G, R) :- length(G, N), ( I =< N -> nth1(I, G, R) ; last(G, R) ).

col_union(Cols, Out) :- col_union_(Cols, [], Out).
col_union_([], _, []).
col_union_([col(C, T)|Cs], Seen, Out) :-
    ( memberchk(C, Seen) -> col_union_(Cs, Seen, Out) ; Out = [col(C, T)|Rest], col_union_(Cs, [C|Seen], Rest) ).

% -------------------------------------------------------------------- SQL
select_stmt(select_stmt([Core|_], OrderOpt, _Limit), Cols, Rows) :-
    select_core(Core, Cols, Rows0),
    ( OrderOpt = some(Keys) -> order_rows(Keys, Cols, Rows0, Rows) ; Rows = Rows0 ).

% task 5c: Joins is a LIST now (was `JoinOpt = none | some(join(Src,On))`, at
% most one) — every join folds through the running (Cols,Rows) pair left to
% right, same "inner join" semantics as before (this interpreter never
% distinguished LEFT from INNER; that pre-existing simplification is
% unchanged here). rust_engine's interp.rs::select_core is the mirror.
select_core(select_core(Projs, From, Joins, WhereOpt, GroupOpt, HavingOpt), Cols, Rows) :-
    from_rows(From, C0, R0),
    foldl(apply_join, Joins, C0-R0, CIn-RIn),
    ( WhereOpt = some(W) -> include(row_passes(CIn, [W]), RIn, RW) ; RW = RIn ),
    ( GroupOpt = some(Keys) -> group_rows(Keys, CIn, RW, Groups) ; ( has_agg(Projs) -> Groups = [RW] ; Groups = none ) ),
    ( Groups == none -> findall(Row, ( member(R, RW), project(Projs, CIn, [R], Row) ), Rows0)
    ; findall(Row, ( member(G, Groups), project(Projs, CIn, G, Row) ), Rows0) ),
    out_cols(Projs, CIn, Cols),
    ( HavingOpt = some(H) -> include(row_passes(Cols, [H]), Rows0, Rows) ; Rows = Rows0 ).

from_rows(table(D, _), Cols, Rows) :- ds_key(D, K), get(K, Cols, Rows).
from_rows(subquery(Core, _), Cols, Rows) :- select_core(Core, Cols, Rows).

% apply_join/3: one step of the foldl over Joins — J's functor is not
% checked (left_join/2 and inner_join/2 both read the same way).
apply_join(J, C0-R0, Cols-Rows) :-
    J =.. [_, Src, On], from_rows(Src, C1, R1), inner_join(C0, R0, C1, R1, On, Cols, Rows).

inner_join(C0, R0, C1, R1, On, Cols, Rows) :-
    append(C0, C1, Cols),
    findall(Row, ( member(A, R0), member(B, R1), append(A, B, Row), eval(On, Cols, Row, V), truthy(V) ), Rows).

has_agg(Projs) :- member(proj(E, _), Projs), is_agg(E), !.
is_agg(call(N, _)) :- lower(N, L), memberchk(L, [sum, avg, mean, max, min, count]).

% GROUP BY: groups in the order their key first appears (Spark's single-partition order is
% not defined; the comparator sorts rows, so first-seen is as good as any)
group_rows(Keys, Cols, Rows, Groups) :-
    findall(KV-R, ( member(R, Rows), findall(V, ( member(Key, Keys), eval(Key, Cols, R, V) ), KV) ), Pairs),
    findall(KV, member(KV-_, Pairs), KVs0), list_to_set(KVs0, KVs),
    findall(G, ( member(KV, KVs), findall(R, member(KV-R, Pairs), G) ), Groups).

% one output row from one group (a plain SELECT is a group of one row)
project(Projs, Cols, Group, Row) :- findall(V, ( member(proj(E, _), Projs), proj_values(E, Cols, Group, Vs), member(V, Vs) ), Row).
proj_values(star, _, [R|_], R) :- !.
% task 5c: COUNT(DISTINCT x) — the aggregate's one arg may itself be
% distinct(Inner); dedup the per-row values before handing them to
% aggregate/3, same as before for every other aggregate.
proj_values(E, Cols, Group, [V]) :-
    is_agg(E), !, E = call(N, [Arg0]), lower(N, LN),
    ( Arg0 = distinct(Arg) -> DoDistinct = true ; Arg = Arg0, DoDistinct = false ),
    findall(X, ( member(R, Group), eval(Arg, Cols, R, X) ), Xs0),
    ( DoDistinct == true -> list_to_set(Xs0, Xs) ; Xs = Xs0 ),
    aggregate(LN, Xs, V).
proj_values(E, Cols, [R|_], [V]) :- eval(E, Cols, R, V).

out_cols(Projs, Cols, Out) :- findall(C, ( member(proj(E, A), Projs), out_col(E, A, Cols, C) ), Cs), flatten(Cs, Out).
out_col(star, none, Cols, Cols) :- !.
out_col(E, some(A), Cols, col(L, T)) :- !, lower(A, L), expr_type(E, Cols, T).
out_col(col(N), none, Cols, col(L, T)) :- !, lower(N, L), ( memberchk(col(L, T), Cols) -> true ; T = num ).
out_col(E, none, Cols, col('_auto', T)) :- expr_type(E, Cols, T).

expr_type(col(N), Cols, T) :- lower(N, L), memberchk(col(L, T), Cols), !.
expr_type(call(F, [A]), Cols, T) :- lower(F, LF), memberchk(LF, [max, min]), !, expr_type(A, Cols, T).
expr_type(lit(V), _, T) :- !, ( number(V) -> T = num ; T = char ).
expr_type(_, _, num).

% aggregates over a list of values; missing values are skipped, like SAS and Spark
aggregate(count, Xs, N) :- exclude(==(missing), Xs, Ys), length(Ys, N).
aggregate(A, Xs, V) :- exclude(==(missing), Xs, Ys), ( Ys == [] -> V = missing ; agg_(A, Ys, V) ).
agg_(sum, Ys, V) :- foldl([X, Acc, S]>>(S is Acc + X), Ys, 0, V).
agg_(avg, Ys, V) :- agg_(sum, Ys, S), length(Ys, N), V is S / N.
agg_(mean, Ys, V) :- agg_(avg, Ys, V).
agg_(max, Ys, V) :- max_list(Ys, V).
agg_(min, Ys, V) :- min_list(Ys, V).

order_rows(Keys, Cols, Rows, Sorted) :-
    findall(kv(KV, I, R), ( nth1(I, Rows, R), findall(V, ( member(K, Keys), eval(K, Cols, R, V) ), KV) ), Triples),
    predsort(cmp_kv_idx, Triples, SortedTriples),      % stable: the row index breaks ties, so nothing is dropped
    findall(R, member(kv(_, _, R), SortedTriples), Sorted).

% key tuples in SAS order: element by element with compare_sas/3
cmp_keys(O, A, B) :- cmp_list(A, B, O).
cmp_list([], [], =).
cmp_list([X|Xs], [Y|Ys], O) :- compare_sas(X, Y, C), ( C == (=) -> cmp_list(Xs, Ys, O) ; O = C ).
cmp_kv_idx(O, kv(A, I, _), kv(B, J, _)) :- cmp_list(A, B, C), ( C == (=) -> compare(O, I, J) ; O = C ).

% ------------------------------------------------------------ expressions
% eval(+Expr, +Cols, +Row, -Value): SAS semantics — a missing operand makes an arithmetic
% result missing; in comparisons missing is smaller than every number.
value_of(Name, Cols, Row, V) :- nth1(I, Cols, col(Name, _)), !, nth1(I, Row, V).
value_of(_, _, _, missing).

eval(col(N), Cols, Row, V) :- !, lower(N, L), value_of(L, Cols, Row, V).
eval(col(_, N), Cols, Row, V) :- !, lower(N, L), value_of(L, Cols, Row, V).
eval(lit(X), _, _, X) :- !.
eval(paren(E), Cols, Row, V) :- !, eval(E, Cols, Row, V).
% task 5c: proj_values/4 always unwraps distinct(...) itself before calling eval/4
% (dedup happens at the aggregate, not per row) — this clause is the defensive
% fallback for any other context that hands eval/4 a bare distinct(E).
eval(distinct(E), Cols, Row, V) :- !, eval(E, Cols, Row, V).
eval(neg(E), Cols, Row, V) :- !, eval(E, Cols, Row, X), ( X == missing -> V = missing ; V is -X ).
eval(not(E), Cols, Row, V) :- !, eval(E, Cols, Row, X), ( truthy(X) -> V = 0 ; V = 1 ).
eval(and(A, B), Cols, Row, V) :- !, eval(A, Cols, Row, X), eval(B, Cols, Row, Y), ( truthy(X), truthy(Y) -> V = 1 ; V = 0 ).
eval(or(A, B), Cols, Row, V) :- !, eval(A, Cols, Row, X), eval(B, Cols, Row, Y), ( ( truthy(X) ; truthy(Y) ) -> V = 1 ; V = 0 ).
eval(subquery_expr(Core), _, _, V) :- !, select_core(Core, _, Rows), ( Rows = [[V|_]|_] -> true ; V = missing ).
eval(in(E, Items), Cols, Row, V) :- !, eval(E, Cols, Row, X), ( member(lit(X), Items) -> V = 1 ; V = 0 ).
eval(call(F, Args), Cols, Row, V) :- !, lower(F, LF), maplist([A, X]>>eval(A, Cols, Row, X), Args, Xs), sas_fn(LF, Xs, V).
eval(T, Cols, Row, V) :- T =.. [Op, A, B], eval(A, Cols, Row, X), eval(B, Cols, Row, Y), binop(Op, X, Y, V).

binop(Op, X, Y, V) :- memberchk(Op, [eq, ne, lt, le, gt, ge]), !, compare_sas(X, Y, C), ( cmp_true(Op, C) -> V = 1 ; V = 0 ).
binop(_, missing, _, missing) :- !.
binop(_, _, missing, missing) :- !.
binop(add, X, Y, V) :- V is X + Y.
binop(sub, X, Y, V) :- V is X - Y.
binop(mul, X, Y, V) :- V is X * Y.
binop(div, X, Y, V) :- ( Y =:= 0 -> V = missing ; V is X / Y ).
binop(pow, X, Y, V) :- V is X ** Y.
binop(cat, X, Y, V) :- atomic_list_concat([X, Y], V).

% missing < any number; numbers by value; text by code order
compare_sas(missing, missing, =) :- !.
compare_sas(missing, _, <) :- !.
compare_sas(_, missing, >) :- !.
compare_sas(X, Y, C) :- number(X), number(Y), !, ( X < Y -> C = (<) ; X > Y -> C = (>) ; C = (=) ).
compare_sas(X, Y, C) :- compare(C, X, Y).
cmp_true(eq, =). cmp_true(ne, <). cmp_true(ne, >). cmp_true(lt, <). cmp_true(le, <). cmp_true(le, =).
cmp_true(gt, >). cmp_true(ge, >). cmp_true(ge, =).

sas_fn(_, Xs, missing) :- memberchk(missing, Xs), !.
sas_fn(month, [D], M) :- !, civil(D, _, M, _).
sas_fn(year, [D], Y) :- !, civil(D, Y, _, _).
sas_fn(day, [D], Dd) :- !, civil(D, _, _, Dd).
sas_fn(abs, [X], V) :- !, V is abs(X).
sas_fn(round, [X], V) :- !, V is round(X).
sas_fn(upcase, [X], V) :- !, upcase_atom(X, V).
sas_fn(lowcase, [X], V) :- !, downcase_atom(X, V).
sas_fn(F, _, _) :- format(user_error, "LINEAGEQ: function ~w not executable~n", [F]), fail.

% ----------------------------------------------------------------- dates
% days since 1960-01-01 <-> civil date (Howard Hinnant's algorithms, proleptic Gregorian)
sas_days(Y, M, D, Days) :- days_from_civil(Y, M, D, N), days_from_civil(1960, 1, 1, N0), Days is N - N0.
days_from_civil(Y0, M, D, N) :-
    ( M =< 2 -> Y is Y0 - 1 ; Y = Y0 ),
    Era is floor(Y / 400), Yoe is Y - Era * 400,
    ( M > 2 -> Mp is M - 3 ; Mp is M + 9 ),
    Doy is (153 * Mp + 2) // 5 + D - 1,
    Doe is Yoe * 365 + Yoe // 4 - Yoe // 100 + Doy,
    N is Era * 146097 + Doe - 719468.
civil(Days, Y, M, D) :-
    days_from_civil(1960, 1, 1, N0), Z is Days + N0 + 719468,
    Era is floor(Z / 146097), Doe is Z - Era * 146097,
    Yoe is (Doe - Doe // 1460 + Doe // 36524 - Doe // 146096) // 365,
    Doy is Doe - (365 * Yoe + Yoe // 4 - Yoe // 100),
    Mp is (5 * Doy + 2) // 153,
    D is Doy - (153 * Mp + 2) // 5 + 1,
    ( Mp < 10 -> M is Mp + 3 ; M is Mp - 9 ),
    ( M =< 2 -> Y is Yoe + Era * 400 + 1 ; Y is Yoe + Era * 400 ).

% -------------------------------------------------------------- CSV out
% the sas_print convention: header = column names; a value as fmt_value prints it
write_csv(OutDir, K) :-
    dataset(K, Cols, Rows), format(atom(F), "~w/~w.csv", [OutDir, K]),
    setup_call_cleanup(open(F, write, S),
        ( findall(N, member(col(N, _), Cols), Names), atomic_list_concat(Names, ',', H), format(S, "~w\r\n", [H]),
          forall(member(R, Rows), ( maplist(fmt_cell, Cols, R, Cells), atomic_list_concat(Cells, ',', Line), format(S, "~w\r\n", [Line]) )) ),
        close(S)).

fmt_cell(_, missing, '.') :- !.
fmt_cell(col(N, date), Days, T) :- !, ( fmt(N, F), downcase_atom(F, LF), sub_atom(LF, 0, _, _, mmddyy) -> civil(Days, Y, M, D), format(atom(T), "~|~`0t~d~2+/~|~`0t~d~2+/~d", [M, D, Y]) ; format(atom(T), "~w", [Days]) ).
fmt_cell(_, V, T) :- number(V), !, fmt_number(V, T).
fmt_cell(_, V, V).

fmt_number(V, T) :- integer(V), !, format(atom(T), "~d", [V]).
fmt_number(V, T) :- V =:= truncate(V), abs(V) < 1.0e15, !, I is truncate(V), format(atom(T), "~d", [I]).
fmt_number(V, T) :- format(atom(T), "~12g", [V]).

% ---------------------------------------------------------------- CSV in (block mode)
load_inputs(DataDir) :-
    directory_files(DataDir, Fs),
    forall(( member(F, Fs), file_name_extension(K, csv, F) ), load_csv(DataDir, K)).
load_csv(DataDir, K) :-
    format(atom(SchemaF), "~w/~w.schema.json", [DataDir, K]), format(atom(CsvF), "~w/~w.csv", [DataDir, K]),
    open(SchemaF, read, S1), json_read_dict(S1, Schema), close(S1),
    findall(col(N, T), ( member(C, Schema.columns), atom_string(N, C.name), atom_string(T, C.type),
                         ( C.format \== null -> atom_string(Fm, C.format), retractall(fmt(N, _)), assertz(fmt(N, Fm)) ; true ) ), Cols),
    read_file_to_string(CsvF, Text, []), split_string(Text, "\n", "\r", [_Header|Lines0]), exclude(==(""), Lines0, Lines),
    findall(Row, ( member(L, Lines), split_string(L, ",", "", Cells), maplist(read_cell, Cols, Cells, Row) ), Rows),
    retractall(dataset(K, _, _)), assertz(dataset(K, Cols, Rows)).
read_cell(_, ".", missing) :- !.
read_cell(col(_, num), S, V) :- !, number_string(V, S).
read_cell(col(_, date), S, V) :- !, ( sub_string(S, _, _, _, "/") -> informat_date(mmddyy10, S, V) ; number_string(V, S) ).
read_cell(col(_, char), S, A) :- atom_string(A, S).
