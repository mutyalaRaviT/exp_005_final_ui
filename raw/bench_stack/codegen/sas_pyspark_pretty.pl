% codegen/sas_pyspark_pretty.pl — SAS node/4 -> PySpark a person would write.
%
% Fix round 1 (2026-09-09): every proj(...) pattern in this file was arity-2
% (proj(Expr,AliasOpt)) while pipeline/specs/sas.py's PROJ has built arity-3
% (proj(Expr,AliasOpt,LengthOpt)) since task 5b's LENGTH support — this file was
% never touched or tested in 5b, so every proj/2 clause here silently matched
% nothing. run_all.sh step 4's Prolog-vs-Rust byte-diff caught it: this file was
% dropping the entire body of every CREATE TABLE AS SELECT. Fixed by widening
% every proj/2 to proj/3 (the third arg unused here, matched with `_`).
%
% Why: codegen/sas_pyspark.pl is the plain printer (easy to prove). This one
% prints the SAME node/4 for a reader: named DataFrames, the SAS statements of
% each step as a comment above the code (sliced from the source by the trace's
% byte offsets), one clause per line, SAS-flavoured helpers (read_datalines,
% merge_by, show). rust_engine/src/emit_pretty.rs is the same rule set in Rust;
% the two outputs are diffed byte for byte.
%
%   swipl -q -s codegen/sas_pyspark_pretty.pl -g main -- <node4.pl> <preamble.py> <out.py>
:- dynamic node/4.
:- dynamic node_comment/5.
:- dynamic schema/2.
:- dynamic scalar_name/1.
:- dynamic src_text/1.

main :-
    current_prolog_flag(argv, [Node4, Preamble, Out]),
    style_check(-discontiguous),
    consult(Node4),
    read_file_to_string(Preamble, Pre, []),
    load_source,
    program_lines(Lines),
    setup_call_cleanup(open(Out, write, S),
        ( write(S, Pre), nl(S), forall(member(L, Lines), (write(S, L), nl(S))) ),
        close(S)),
    length(Lines, N), format("wrote ~w (~w generated lines)~n", [Out, N]),
    halt(0).
main :- format(user_error, "usage: swipl -q -s codegen/sas_pyspark_pretty.pl -g main -- node4.pl preamble.py out.py~n", []), halt(1).

% the source file named in the traces (one file per node/4 fact file)
load_source :-
    once(node(_, _, _, trace(File, _, _, _, _))),
    ( exists_file(File) -> read_file_to_string(File, T, []) ; T = "" ),
    assertz(src_text(T)).

% ---------------------------------------------------------------- blocks
blocks(Bs) :- findall(B, node(B, _, _, _), Bs0), list_to_set(Bs0, Bs).
block_nodes(B, Ns) :- findall(Seq-n(T, L0, L1, B0, B1), node(B, Seq, T, trace(_, L0, L1, B0, B1)), Ps), keysort(Ps, S), pairs_values(S, Ns).
block_terms(B, Ts) :- block_nodes(B, Ns), findall(T, member(n(T, _, _, _, _), Ns), Ts).
block_span(B, L0, L1) :- block_nodes(B, Ns), findall(A, member(n(_, A, _, _, _), Ns), As), findall(Z, member(n(_, _, Z, _, _), Ns), Zs), min_list(As, L0), max_list(Zs, L1).

program_lines(Lines) :-
    blocks(Bs),
    findall(L, ( member(B, Bs), block_lines(B, BL), member(L, BL) ), Body),
    findall(K-V, ( member(B, Bs), block_terms(B, Ts), out_ds(Ts, D), ds_key(D, K), pyvar(D, V) ), Outs0),
    dedup_keys(Outs0, Outs),
    findall(L, ( member(K-V, Outs), format(atom(L), "show(\"~w\", ~w)", [K, V]) ), Shows),
    rule_line("every dataset the program created, in SAS log order", Foot),
    append(["spark = make_spark()", ""], Body, L1),
    append(L1, [Foot|Shows], L2),
    append(L2, ["spark.stop()"], Lines).

dedup_keys([], []).
dedup_keys([K-V|R], [K-V|Out]) :- exclude([K2-_]>>(K2 == K), R, R1), dedup_keys(R1, Out).

out_ds([data(D)|_], D).
out_ds([proc_sql|Body], D) :- member(create_table_as(D, _), Body).

% "# ---- <label>  (<kind>, SAS lines L0-L1) ----…" padded to 78 columns
rule_line(Label, Line) :-
    format(atom(Head), "# ---- ~w ", [Label]),
    atom_length(Head, N), Pad is max(4, 78 - N),
    length(Ds, Pad), maplist(=('-'), Ds), atom_chars(D, Ds),
    atom_concat(Head, D, Line).

block_lines(B, Lines) :-
    block_terms(B, Ts), block_span(B, L0, L1), once(step_label(Ts, Label, Kind)),
    format(atom(LabelFull), "~w  (~w, SAS lines ~w-~w)", [Label, Kind, L0, L1]),
    rule_line(LabelFull, H),
    block_nodes(B, Ns), findall(C, ( member(n(T, _, _, B0, B1), Ns), source_comment(T, B0, B1, Cs), member(C, Cs) ), Comments),
    ( once(step_lines(Ts, Body)) -> true
    ; format(atom(E), "# no rule for this step yet: ~q", [Ts]), Body = [E] ),
    append([H|Comments], Body, L2), append(L2, [""], Lines).

step_label([libname(L, _)|_], T, "LIBNAME") :- format(atom(T), "libref ~w", [L]).
step_label([data(D)|_], K, "DATA step") :- ds_key(D, K).
step_label([proc_sql|Body], K, "PROC SQL") :- member(create_table_as(D, _), Body), ds_key(D, K).
step_label([proc_sql|_], "proc sql", "PROC SQL").
step_label([proc_print(D)|_], T, "PROC PRINT") :- ds_key(D, K), format(atom(T), "print ~w", [K]).
step_label(_, "step", "step").

% the SAS statement, sliced from the source by byte offsets, one comment line per source line
source_comment(empty, _, _, []) :- !.
source_comment(datalines(Body), _, _, [C]) :- !,
    split_string(Body, "\n", " \t\r", Ls0), exclude(==(""), Ls0, Ls), length(Ls, N),
    format(atom(C), "#   datalines;  ... ~w rows ...", [N]).
source_comment(_, B0, B1, Cs) :-
    src_text(T), string_length(T, Len), B1 =< Len, !,
    L is B1 - B0, sub_string(T, B0, L, _, Slice),
    split_string(Slice, "\n", " \t\r", Ls0), exclude(==(""), Ls0, Ls1),
    reflow(Ls1, Ls),
    findall(C, ( member(S, Ls), format(atom(C), "#   ~w", [S]) ), Cs).
source_comment(_, _, _, []).

% a statement written over several source lines is re-flowed: joined with one
% space, then broken before FROM / WHERE / GROUP BY / HAVING / ORDER BY
reflow([L], [L]) :- !.
reflow(Ls, Out) :-
    atomic_list_concat(Ls, ' ', Joined),
    foldl(break_before, ["FROM", "WHERE", "GROUP BY", "HAVING", "ORDER BY"], [Joined], Parts0),
    maplist([P, Q]>>(atom_string(P, S0), normalize_space(string(Q), S0)), Parts0, Parts1),
    exclude(==(""), Parts1, Out).
break_before(Kw, Parts, Out) :-
    findall(Q, ( member(P, Parts), split_kw(P, Kw, Qs), member(Q, Qs) ), Out).
split_kw(P, Kw, Qs) :-
    string_upper(P, U), string_concat(" ", Kw, Needle1), string_concat(Needle1, " ", Needle),
    ( sub_string(U, Before, _, After, Needle)
    -> sub_string(P, 0, Before, _, Head), string_length(Kw, KL), Rest is After + KL + 1, sub_string(P, _, Rest, 0, Tail),
       split_kw(Tail, Kw, More), Qs = [Head|More]
    ;  Qs = [P] ).

% ----------------------------------------------------------------- steps
step_lines([libname(Lib, lit(Path))], [L]) :-
    py_path(Path, P), format(atom(L), "libref(\"~w\", ~w)", [Lib, P]).

step_lines([proc_print(_)|_], ["# (shown by show() at the end of the program)"]).

step_lines([proc_sql|Body], Lines) :-
    findall(L, ( member(create_table_as(Out, Sel), Body), sql_lines(Out, Sel, Ls), member(L, Ls) ), Lines).

% INPUT + DATALINES
step_lines([data(Out)|Body], Lines) :-
    memberchk(input(Vars), Body), memberchk(datalines(Rows), Body), !,
    ds_key(Out, K), pyvar(Out, V),
    maplist(input_col, Vars, Cols), atomic_list_concat(Cols, ", ", ColsTxt),
    split_string(Rows, "\n", " \t\r", RowLs0), exclude(==(""), RowLs0, RowLs),
    findall(RL, ( member(R, RowLs), format(atom(RL), "        ~w", [R]) ), RowLines),
    format(atom(L1), "~w = read_datalines(", [V]),
    format(atom(L3), "    schema=[~w],", [ColsTxt]),
    format_lines(Body, FmtLines),
    maplist(var_name, Vars, Names), set_schema(K, Names),
    append([[L1, "    spark,", L3, "    rows=\"\"\""], RowLines, ["    \"\"\",", ")"], FmtLines], Lines).

% IF _N_ = 1 THEN SET lookup; SET main
step_lines([data(Out)|Body], [L1|FmtLines]) :-
    memberchk(if_then_set(_, lit(1, _), Look), Body), memberchk(set(In), Body), !,
    ds_key(Out, K), ds_key(In, KI), ds_key(Look, KL), pyvar(Out, V), pyvar(In, VI), pyvar(Look, VL),
    format(atom(L1), "~w = attach_first_row(~w, ~w)", [V, VI, VL]),
    format_lines(Body, FmtLines),
    findall(C, ( member(DK, [KI, KL]), schema(DK, Cs), member(C, Cs) ), Cols0), list_to_set(Cols0, Cols), set_schema(K, Cols).

% SET + subsetting IFs
step_lines([data(Out)|Body], Lines) :-
    memberchk(set(In), Body), !,
    ds_key(Out, K), ds_key(In, KI), pyvar(Out, V), pyvar(In, VI),
    findall(S, ( member(subset_if(C), Body), pe(C, top, X, [], _), format(atom(S), ".filter(~w)", [X]) ), Steps),
    chain_lines(V, VI, Steps, CL),
    format_lines(Body, FmtLines),
    ( schema(KI, Cols) -> set_schema(K, Cols) ; true ),
    append(CL, FmtLines, Lines).

% MERGE ... BY
step_lines([data(Out)|Body], Lines) :-
    memberchk(merge(Srcs), Body), !,
    ds_key(Out, K), pyvar(Out, V),
    ( memberchk(by(Keys), Body) -> true ; Keys = [] ),
    findall(S, ( member(src(D, _), Srcs), ds_key(D, DK), pyvar(D, DV), format(atom(S), "(\"~w\", ~w)", [DK, DV]) ), SrcTxts),
    atomic_list_concat(SrcTxts, ", ", SrcsTxt),
    maplist([Kx, Q]>>format(atom(Q), "\"~w\"", [Kx]), Keys, KeyQs), atomic_list_concat(KeyQs, ", ", KeysTxt),
    findall(W, ( member(src(D, _), Srcs), ds_key(D, DK), schema(DK, Cols), member(Key, Keys), \+ memberchk(Key, Cols),
                 atomic_list_concat(Cols, ", ", ColsTxt),
                 format(atom(W1), "# WARNING  BY variable ~w is not on ~w (columns: ~w).", [Key, DK, ColsTxt]),
                 format(atom(W2), "#          SAS logs an ERROR and leaves ~w with 0 observations; merge_by does the same.", [K]),
                 member(W, [W1, W2]) ), Warns),
    format(atom(L1), "~w = merge_by(", [V]),
    format(atom(L2), "    [~w],", [SrcsTxt]),
    format(atom(L3), "    by=[~w],", [KeysTxt]),
    findall(C, ( member(src(D, _), Srcs), ds_key(D, DK), schema(DK, Cs), member(C, Cs) ), All0), list_to_set(All0, All), set_schema(K, All),
    append(Warns, [L1, L2, L3, ")"], Lines).

format_lines(Body, Lines) :-
    findall(L, ( member(format(Var, fmt(Fm)), Body), lower(Var, LV), format(atom(L), "display_format(\"~w\", \"~w.\")", [LV, Fm]) ), Lines).

input_col(cvar(N), T) :- lower(N, L), format(atom(T), "char(\"~w\")", [L]).
input_col(nvar(N, none), T) :- lower(N, L), format(atom(T), "num(\"~w\")", [L]).
input_col(nvar(N, some(informat(I))), T) :- lower(N, L), format(atom(T), "date(\"~w\", informat=\"~w.\")", [L, I]).
var_name(cvar(N), L) :- lower(N, L).
var_name(nvar(N, _), L) :- lower(N, L).

% a chain: one line when it has at most one single-line step, else vertical
chain_lines(V, Src, Steps, Lines) :-
    (   ( Steps = [] ; Steps = [S1], \+ sub_atom(S1, _, _, _, '\n') )
    ->  atomic_list_concat(Steps, StepsTxt), format(atom(L), "~w = ~w~w", [V, Src, StepsTxt]), Lines = [L]
    ;   format(atom(L1), "~w = (", [V]), format(atom(L2), "    ~w", [Src]),
        findall(IL, ( member(S, Steps), indent_step(S, ILs), member(IL, ILs) ), StepLines),
        append([L1, L2|StepLines], [")"], Lines)
    ).
indent_step(S, Lines) :- split_string(S, "\n", "", Parts), findall(L, ( member(P, Parts), format(atom(L), "    ~w", [P]) ), Lines).

% -------------------------------------------------------------- PROC SQL
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
sql_lines(Out, select_stmt([Core|Cores], OrderOpt, _), Lines) :-
    ds_key(Out, K), pyvar(Out, V),
    core_parts(Core, Src, Steps1, [], Pre1),
    union_steps(Cores, US, Pre1, Pre),
    append(Steps1, US, Steps0),
    ( OrderOpt = some(Keys) -> maplist(key_txt0, Keys, KTs), atomic_list_concat(KTs, ", ", KT), format(atom(OS), ".orderBy(~w)", [KT]), append(Steps0, [OS], Steps) ; Steps = Steps0 ),
    chain_lines(V, Src, Steps, CL),
    core_out_cols(Core, Cols), set_schema(K, Cols),
    append(Pre, CL, Lines).

% union_steps(+Cores, -Steps, +Pre0, -Pre): one ".union(<branch>)" step per
% extra UNION ALL branch, each branch flattened to a single expression the
% same way from_txt/4's subquery arm already flattens a nested core.
union_steps([], [], P, P).
union_steps([C|Cs], [S|Ss], P0, P) :-
    core_parts(C, Src, Steps, P0, P1),
    atomic_list_concat(Steps, ST),
    format(atom(S), ".union(~w~w)", [Src, ST]),
    union_steps(Cs, Ss, P1, P).

% core_parts(+Core, -SourceTxt, -Steps, +Pre0, -Pre)
% task 5c: Joins is a LIST now (was `JoinOpt = none | some(join(JS,On))`);
% S1 gets one ".join(...)" step per list item, source order — maplist_pre
% (defined below) already threads Pre through a list this same way.
core_parts(select_core(Cols, From, Joins, WhereOpt, GroupOpt, HavingOpt), Src, Steps, P0, P) :-
    from_txt(From, Src, P0, P1),
    maplist_pre(join_step, Joins, S1, P1, P3),
    ( WhereOpt = some(W) -> pe(W, top, WT, P3, P4), format(atom(WStep), ".filter(~w)", [WT]), S2 = [WStep] ; S2 = [], P4 = P3 ),
    select_steps(Cols, GroupOpt, S3, P4, P5),
    ( HavingOpt = some(H) -> pe(H, top, HT, P5, P), format(atom(HStep), ".filter(~w)", [HT]), S4 = [HStep] ; S4 = [], P = P5 ),
    append([S1, S2, S3, S4], Steps).

% task 5d: a join whose own arity is 1 (cross_join(Src): no ON) renders
% ".crossJoin(src)" instead — arity decides this, not the functor name.
join_step(J, JStep, P0, P) :-
    functor(J, _, Arity), J =.. [_, JS|Rest], from_txt(JS, JT, P0, P1),
    ( Arity =:= 2 -> [On] = Rest, pe(On, top, OT, P1, P), format(atom(JStep), ".join(~w, ~w, \"inner\")", [JT, OT])
    ; P = P1, format(atom(JStep), ".crossJoin(~w)", [JT]) ).

from_txt(table(D, none), T, P, P) :- pyvar(D, T).
from_txt(table(D, some(A)), T, P, P) :- pyvar(D, V), lower(A, LA), format(atom(T), "~w.alias(\"~w\")", [V, LA]).
from_txt(subquery(Core, AliasOpt), T, P0, P) :-
    core_parts(Core, S, Steps, P0, P), atomic_list_concat(Steps, ST),
    ( AliasOpt = some(A) -> lower(A, LA), format(atom(T), "(~w~w).alias(\"~w\")", [S, ST, LA]) ; format(atom(T), "(~w~w)", [S, ST]) ).

% SELECT list -> [] | [.select(...)] | [.agg(...)] | [.groupBy(...), .agg(...)]
% task 5d: NOT widened to a qualified star (`a.*`) — unlike the bare star/0
% fast path (implicit "pass every column through" is sound when there is no
% join, or the whole joined row equals the whole source anyway), skipping
% .select() entirely for a lone `a.*` would pass through every JOINed
% column, not just `a`'s — wrong the moment a join is present. No file in
% this corpus hits this (a lone single-item `a.*` projection list), so left
% as the general sel_item/pe path below, which renders it correctly via
% "alias.*" regardless.
select_steps([proj(star, none, _)], none, [], P, P) :- !.
select_steps(Cols, none, [Step], P0, P) :-
    (   member(proj(E, _, _), Cols), is_agg(E)
    ->  maplist_pre(agg_item, Cols, Items, P0, P), call_lines("agg", Items, Step)
    ;   ( forall(member(proj(E, A, _), Cols), (E = col(_), A == none)) -> maplist_pre(sel_item, Cols, Items, P0, P), atomic_list_concat(Items, ", ", IT), format(atom(Step), ".select(~w)", [IT])
        ; maplist_pre(sel_item, Cols, Items, P0, P), call_lines("select", Items, Step) )
    ).
select_steps(Cols, some(Keys), [GStep, AStep], P0, P) :-
    findall(KT, ( member(Key, Keys), key_txt(Key, Cols, KT) ), KTs), atomic_list_concat(KTs, ", ", KeysTxt),
    format(atom(GStep), ".groupBy(~w)", [KeysTxt]),
    include(agg_proj, Cols, Aggs), maplist_pre(agg_item, Aggs, Items, P0, P), call_lines("agg", Items, AStep).

% .name(a) on one line; several items each on their own line
call_lines(Name, [I], Step) :- !, format(atom(Step), ".~w(~w)", [Name, I]).
call_lines(Name, Items, Step) :-
    findall(L, ( member(I, Items), format(atom(L), "    ~w,", [I]) ), Ls), atomic_list_concat(Ls, "\n", Body),
    format(atom(Step), ".~w(\n~w\n)", [Name, Body]).

agg_proj(proj(E, _, _)) :- is_agg(E).
key_txt(Key, Cols, T) :- member(proj(E, some(A), _), Cols), same_expr(E, Key), !, pe(Key, sub, KP, [], _), lower(A, LA), format(atom(T), "~w.alias(\"~w\")", [KP, LA]).
key_txt(Key, _, T) :- key_txt0(Key, T).
key_txt0(col(N), T) :- !, lower(N, L), format(atom(T), "\"~w\"", [L]).
key_txt0(E, T) :- pe(E, sub, T, [], _).
same_expr(A, B) :- lower_term(A, LA), lower_term(B, LB), LA == LB.

sel_item(proj(col(N), none, _), T, P, P) :- !, lower(N, L), format(atom(T), "\"~w\"", [L]).
sel_item(proj(star, none, _), "\"*\"", P, P) :- !.
% task 5d: a qualified star (`a.*`), same idea as the bare star arm above.
sel_item(proj(star(A0), none, _), T, P, P) :- !, lower(A0, A), format(atom(T), "\"~w.*\"", [A]).
sel_item(proj(E, none, _), T, P0, P) :- pe(E, sub, T, P0, P).
sel_item(proj(E, some(A), _), T, P0, P) :- pe(E, sub, X, P0, P), lower(A, LA), format(atom(T), "~w.alias(\"~w\")", [X, LA]).
agg_item(P, T, P0, P1) :- sel_item(P, T, P0, P1).

maplist_pre(_, [], [], P, P).
maplist_pre(G, [X|Xs], [Y|Ys], P0, P) :- call(G, X, Y, P0, P1), maplist_pre(G, Xs, Ys, P1, P).

is_agg(call(N, _)) :- lower(N, L), memberchk(L, [sum, avg, mean, max, min, count, std, var, nmiss]).

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
% helper shape as sas_pyspark.pl's own alias_schema.
alias_schema(From, _Joins, Al, Cols) :- from_source_alias(From, Al), !, table_schema(From, Cols).
alias_schema(_From, Joins, Al, Cols) :- member(J, Joins), arg(1, J, Src), from_source_alias(Src, Al), !, table_schema(Src, Cols).
from_source_alias(table(_, some(A0)), Al) :- !, lower(A0, Al).
from_source_alias(subquery(_, some(A0)), Al) :- !, lower(A0, Al).
table_schema(table(D, _), Cols) :- !, ds_key(D, K), schema(K, Cols).
table_schema(_, []).

% ------------------------------------------------------------ expressions
% pe(+Term, +Ctx, -Py, +Pre0, -Pre)   Ctx: top (a whole condition) | sub (an operand) | arg (a function argument)
pe(col(N), arg, T, P, P) :- !, lower(N, L), format(atom(T), "\"~w\"", [L]).
pe(col(N), _, T, P, P) :- lower(N, L), format(atom(T), "F.col(\"~w\")", [L]).
pe(col(A, N), _, T, P, P) :- lower(A, LA), lower(N, L), format(atom(T), "F.col(\"~w.~w\")", [LA, L]).
% M3a defect 1: a NUMBER leaf now folds to lit(Value, Lexeme) (specs/sas.py
% keep_lexeme=True). Only the printer reads the lexeme; every consumer below
% reads Value and ignores it, so lit/2 is handled by one clause that defers to
% the existing lit/1 clause rather than by duplicating any rule.
pe(lit(V, _), Ctx, T, P0, P) :- !, pe(lit(V), Ctx, T, P0, P).
pe(lit(V), top, T, P, P) :- !, py_lit(V, X), format(atom(T), "F.lit(~w)", [X]).
pe(lit(V), _, T, P, P) :- py_lit(V, T).
pe(star, _, "\"*\"", P, P).
pe(star(A0), _, T, P, P) :- lower(A0, A), format(atom(T), "\"~w.*\"", [A]).
pe(paren(E), _, T, P0, P) :- pe(E, sub, X, P0, P), format(atom(T), "(~w)", [X]).
pe(neg(E), _, T, P0, P) :- wrap(E, X, P0, P), format(atom(T), "-~w", [X]).
pe(not(E), _, T, P0, P) :- wrap(E, X, P0, P), format(atom(T), "~~~w", [X]).
pe(cat(A, B), _, T, P0, P) :- pe(A, arg, X, P0, P1), pe(B, arg, Y, P1, P), format(atom(T), "F.concat(~w, ~w)", [X, Y]).
pe(in(A, Items), _, T, P0, P) :- wrap(A, X, P0, P), maplist([I, S]>>(lit_value(I, V), py_lit(V, S)), Items, Ls), atomic_list_concat(Ls, ", ", LT), format(atom(T), "~w.isin([~w])", [X, LT]).
% task 5c: the "simple" fast-path guard used to compare the JOIN position to
% the atom `none`; it is a LIST now, so "no join" is `[]`, not `none` — the
% other three tail positions (WHERE/GROUP BY/HAVING) are unaffected and stay
% `none`. Getting this wrong would not crash: it would just silently miss the
% fast path for every 0-join scalar subquery and fall through to the general
% core_parts branch below, a formatting drift the byte-diff regression check
% (run_all.sh step 4) would have caught.
pe(subquery_expr(Core), _, Name, P0, P) :-
    scalar_var(Core, Name0), unique_scalar(Name0, Name),
    (   Core = select_core([proj(E, _, _)], table(D, none), [], none, none, none), ( E = col(C) ; E = call(_, _), fail )
    ->  pyvar(D, DV), lower(C, LC), format(atom(Line), "~w = scalar(~w, \"~w\")", [Name, DV, LC]), P1 = P0
    ;   core_parts(Core, S, Steps, P0, P1), atomic_list_concat(Steps, ST), format(atom(Line), "~w = scalar(~w~w)", [Name, S, ST])
    ),
    append(P1, [Line], P).
% task 5c: COUNT(DISTINCT x) -> F.countDistinct(x) — ahead of the generic
% call/2 clause, same reasoning as sas_pyspark.pl's own px/4.
pe(call(Name, [distinct(Arg)]), _, T, P0, P) :-
    lower(Name, count), !, pe(Arg, arg, X, P0, P), format(atom(T), "F.countDistinct(~w)", [X]).
pe(call(Name, Args), _, T, P0, P) :-
    lower(Name, L), once(sas_fn(L, Py)),
    maplist_pre([A, X, Q0, Q]>>pe(A, arg, X, Q0, Q), Args, Xs, P0, P), atomic_list_concat(Xs, ", ", XT),
    format(atom(T), "F.~w(~w)", [Py, XT]).
pe(Term, _, T, P0, P) :-
    Term =.. [Op, A, B], binop(Op, Sym),
    wrap(A, X, P0, P1), wrap(B, Y, P1, P), format(atom(T), "~w ~w ~w", [X, Sym, Y]).

% an operand: parenthesised when it is itself a binary operation
wrap(E, T, P0, P) :- E =.. [Op, _, _], binop(Op, _), !, pe(E, sub, X, P0, P), format(atom(T), "(~w)", [X]).
wrap(E, T, P0, P) :- pe(E, sub, T, P0, P).

binop(mul, "*"). binop(div, "/"). binop(add, "+"). binop(sub, "-").
binop(eq, "=="). binop(ne, "!="). binop(lt, "<"). binop(le, "<="). binop(gt, ">"). binop(ge, ">=").
binop(and, "&"). binop(or, "|").

scalar_var(select_core([proj(_, some(A), _)|_], _, _, _, _, _), N) :- !, lower(A, L), format(atom(N), "~w_value", [L]).
scalar_var(select_core([proj(col(C), none, _)|_], _, _, _, _, _), N) :- !, lower(C, L), format(atom(N), "~w_value", [L]).
scalar_var(_, subquery_value).
unique_scalar(N0, N) :- ( scalar_name(N0) -> between(2, 99, I), format(atom(N), "~w_~w", [N0, I]), \+ scalar_name(N), ! ; N = N0 ), assertz(scalar_name(N)).

sas_fn(month, month).  sas_fn(year, year).  sas_fn(day, dayofmonth).
sas_fn(sum, sum).  sas_fn(avg, avg).  sas_fn(mean, avg).  sas_fn(max, max).  sas_fn(min, min).  sas_fn(count, count).
sas_fn(upcase, upper).  sas_fn(lowcase, lower).  sas_fn(abs, abs).  sas_fn(round, round).  sas_fn(substr, substring).
sas_fn(F, _) :- \+ clause(sas_fn(F, _), true), format(user_error, "LINEAGEQ: no PySpark mapping for SAS function ~w~n", [F]), fail.

% M3a defect 1: an IN list item is lit/1 (string) or lit/2 (number).
lit_value(lit(V), V).
lit_value(lit(V, _), V).
py_lit(V, T) :- number(V), !, format(atom(T), "~w", [V]).
py_lit(V, T) :- py_str(V, T).

% ----------------------------------------------------------------- names
ds_key(ds(L, N), K) :- lower(L, LL), lower(N, LN), format(atom(K), "~w.~w", [LL, LN]).
ds_key(ds(N), K) :- lower(N, LN), format(atom(K), "work.~w", [LN]).
% the Python variable: the dataset name; lib_name when two libs share a name
pyvar(D, V) :-
    ( D = ds(L0, N0) -> lower(L0, L), lower(N0, N) ; D = ds(N0), L = work, lower(N0, N) ),
    ( findall(L2, ( node(_, _, T, _), sub_ds(T, ds(L2a, N2)), lower(L2a, L2), lower(N2, N) ), Libs), sort(Libs, SL), SL = [_, _|_]
    -> format(atom(V0), "~w_~w", [L, N]) ; V0 = N ),
    py_ident(V0, V).
sub_ds(T, D) :- compound(T), ( T = ds(_, _) -> D = T ; T = ds(_) -> D = T ; T =.. [_|As], member(A, As), sub_ds(A, D) ).
py_ident(A, V) :- atom_codes(A, Cs), maplist([C, D]>>( ( code_type(C, alnum) ; C == 0'_ ) -> D = C ; D = 0'_ ), Cs, Ds),
    ( Ds = [F|_], code_type(F, digit) -> atom_codes(V1, [0'_|Ds]) ; atom_codes(V1, Ds) ),
    ( py_keyword(V1) -> atom_concat(V1, '_', V) ; V = V1 ).
py_keyword(K) :- memberchk(K, [class, def, if, in, is, for, from, import, and, or, not, return, pass, with, as, lambda, while, try, except, global, del, yield, raise, break, continue, elif, else, finally, assert, nonlocal, async, await, 'None', 'True', 'False']).

set_schema(K, Cols) :- retractall(schema(K, _)), assertz(schema(K, Cols)).
lower(A, L) :- ( atom(A) -> downcase_atom(A, L) ; L = A ).
lower_term(T, L) :- ( atom(T) -> downcase_atom(T, L) ; compound(T) -> T =.. [F|As], maplist(lower_term, As, Ls), L =.. [F|Ls] ; L = T ).
py_str(A, S) :- atom_codes(A, Cs), py_esc(Cs, Es), atom_codes(Body, Es), format(atom(S), "\"~w\"", [Body]).
py_esc([], []).
py_esc([0'\\|Cs], [0'\\, 0'\\|Es]) :- !, py_esc(Cs, Es).
py_esc([0'"|Cs], [0'\\, 0'"|Es]) :- !, py_esc(Cs, Es).
py_esc([0'\n|Cs], [0'\\, 0'n|Es]) :- !, py_esc(Cs, Es).
py_esc([C|Cs], [C|Es]) :- py_esc(Cs, Es).
% a path: raw string when that is safe (no quote, no trailing backslash), else escaped
py_path(A, S) :- \+ sub_atom(A, _, _, _, '"'), \+ sub_atom(A, _, 1, 0, '\\'), !, format(atom(S), "r\"~w\"", [A]).
py_path(A, S) :- py_str(A, S).
