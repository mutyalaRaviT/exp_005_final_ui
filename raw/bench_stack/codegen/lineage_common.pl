% codegen/lineage_common.pl — what both lineage extractors share (exp_42, 2026-09-07).
%
% Why: sas_lineage.pl reads SAS node/4, pyspark_lineage.pl reads PySpark node/4;
% both must write the SAME four facts the same way so the files can be diffed:
%     schema(Ds, [Col, ...]).                  columns of a dataset, in order
%     ds_lineage(OutDs, InDs).                 OutDs reads InDs
%     col_lineage(OutDs, OutCol, InDs, InCol). OutCol's value depends on InCol
%     ctl_lineage(OutDs, InDs, InCol).         InCol decides which rows reach OutDs
% Names are lower-cased atoms; a dataset is 'lib.name'. Facts are written sorted
% by their text (byte order), duplicates removed — lineage.rs does the same.
:- dynamic schema/2, ds_lineage/2, col_lineage/4, ctl_lineage/3.
:- dynamic node/4.

lower(A, L) :- ( atom(A) -> downcase_atom(A, L) ; L = A ).
ds_key(ds(L, N), K) :- lower(L, LL), lower(N, LN), format(atom(K), "~w.~w", [LL, LN]).
ds_key(ds(N), K) :- lower(N, LN), format(atom(K), "work.~w", [LN]).

set_schema(K, Cols) :- retractall(schema(K, _)), assertz(schema(K, Cols)).
schema_or_empty(K, Cols) :- ( schema(K, Cols) -> true ; Cols = [] ).

blocks(Bs) :- findall(B, node(B, _, _, _), Bs0), list_to_set(Bs0, Bs).
block_terms(B, Ts) :- findall(Seq-T, node(B, Seq, T, _), Ps), keysort(Ps, Sorted), pairs_values(Sorted, Ts).

% every output column of Out copies the same-named column of In
copy_cols(Out, In) :- schema_or_empty(In, Cols), forall(member(C, Cols), assertz(col_lineage(Out, C, In, C))).
reads(Out, In) :- ( ds_lineage(Out, In) -> true ; assertz(ds_lineage(Out, In)) ).
controls(Out, In, Cols) :- forall(member(C, Cols), assertz(ctl_lineage(Out, In, C))).

write_facts(File) :-
    findall(A, ( ( schema(D, Cs), T = schema(D, Cs) ; ds_lineage(O, I), T = ds_lineage(O, I)
                 ; col_lineage(O, OC, I, IC), T = col_lineage(O, OC, I, IC) ; ctl_lineage(O, I, C), T = ctl_lineage(O, I, C) ),
                 format(atom(A), "~q.", [T]) ), As),
    sort(As, Sorted),
    setup_call_cleanup(open(File, write, S), forall(member(A, Sorted), (write(S, A), nl(S))), close(S)),
    length(Sorted, N), format("wrote ~w (~w facts)~n", [File, N]).
