% codegen/pyspark_block.pl — one runnable PySpark program per block, from the PySpark node/4 (exp_42, 2026-09-07).
%
% Why: loop 3's PySpark side is "PySpark -> node/4 -> block test data -> execution".
% Each PySpark block (the assigns and X[k] = v lines before a put, and the put) is
% printed back through the PySpark grammar's own print_stmt/2 — so the program that
% runs is the print-back, which also proves the print direction executes — wrapped
% with the runtime preamble, a CSV load for every input the block's manifest names,
% and the sas_print tail. rust_engine (block-programs) writes the same files as
% *_rust.py; the two are diffed, then one is run under Spark.
%
%   swipl -q -s codegen/pyspark_block.pl -g main -- out/grammar/pyspark.pl out/ir/pyspark/<stem>.node4.pl \
%         codegen/sas_runtime_preamble.py out/loops/blocks/<stem>
:- use_module(library(http/json)).
:- dynamic node/4.

main :-
    current_prolog_flag(argv, [Grammar, Node4, Preamble, BlocksDir]),
    style_check(-discontiguous), consult(Grammar), consult(Node4),
    read_file_to_string(Preamble, Pre, []),
    format(atom(MF), "~w/manifest.json", [BlocksDir]), open(MF, read, S), json_read_dict(S, Manifest), close(S),
    findall(B, node(B, _, _, _), Bs0), list_to_set(Bs0, Bs),
    forall(( member(B, Bs), findall(Seq-T, node(B, Seq, T, _), Ps), keysort(Ps, Sorted), pairs_values(Sorted, Ts),
             member(put(lit(K0), _), Ts), downcase_atom(K0, K) ),
           write_block(Manifest, BlocksDir, Pre, K, Ts)),
    halt(0).
main :- format(user_error, "usage: swipl -q -s codegen/pyspark_block.pl -g main -- grammar.pl node4.pl preamble.py blocks_dir~n", []), halt(1).

% the manifest entry whose `creates` names K -> its block dir and its inputs
write_block(Manifest, BlocksDir, Pre, K, Ts) :-
    ( member(E, Manifest), member(C, E.creates), atom_string(K, C) ->
        atom_string(SasBlock, E.block),
        format(atom(Dir), "~w/~w", [BlocksDir, SasBlock]),
        findall(L, ( member(I, E.inputs), format(atom(L), "ds[\"~w\"] = sas_load_csv(spark, \"~w/in/~w.csv\", \"~w/in/~w.schema.json\")", [I, Dir, I, Dir, I]) ), Loads),
        findall(L, ( member(T, Ts), print_stmt(T, Texts), atomic_list_concat(Texts, ' ', L) ), Body),
        format(atom(Head), "# ---- block ~w creates ~w: inputs loaded from ~w/in, statements printed back from node/4", [SasBlock, K, Dir]),
        append([[Pre, "", "spark = make_spark()", "", Head], Loads, Body, ["", "for _name in ORDER:", "    sas_print(_name)", "spark.stop()"]], Lines),
        atomic_list_concat(Lines, '\n', Prog),
        format(atom(F), "~w/block_~w_prolog.py", [Dir, K]),
        setup_call_cleanup(open(F, write, O), (write(O, Prog), nl(O)), close(O)),
        format("wrote ~w~n", [F])
    ; format("  (no manifest block creates ~w — skipped)~n", [K]) ).
