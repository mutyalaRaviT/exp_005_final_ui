% driver.pl — exp_014 FOLD HARNESS Prolog driver (language-agnostic).
%
% Why this file exists: every out/grammar/<lang>.pl defines the SAME two
% predicates (stmt//1 for parse, print_stmt/2 for print — see the module
% header of pipeline/tests/fixtures/mini_grammar.pl for the exact
% contract). This file is the one place that loads a grammar, drives it
% over a batch of statements, and writes the results back out as Prolog
% facts. It holds NO language knowledge of its own — swap the grammar
% file on the command line and it works unchanged (that is the whole
% point of the pyDSL-only law: language shape lives in specs/grammars,
% never in this scaffolding).
%
% ---------------------------------------------------------------------
% Invocation (two goals, same driver):
%
%   swipl -q -s driver.pl -g main   -- <grammar.pl> <stmts_in.pl> <terms_out.pl>
%   swipl -q -s driver.pl -g unfold -- <grammar.pl> <terms_in.pl>  <printed_out.pl>
%
% main:   stmts_in.pl holds facts   stmt_tokens(Seq, TokensList).
%         TokensList is [tok(Kind,Text), ...], Kind in
%         {keyword,word,number,string,symbol}, Text the exact source text.
%         For each Seq, calls the grammar's stmt(Term, TokensList, [])
%         (the DCG-expanded form of stmt//1 — Tokens fully consumed, []
%         left over, or it does not count as a parse). Writes one line
%         per Seq to terms_out.pl:
%             folded(Seq, Term).      -- Term written via writeq/2, quoted
%             failed(Seq).            -- no parse (grammar failed or raised)
%
% unfold: terms_in.pl holds facts   folded(Seq, Term).  (terms_out.pl from
%         a prior main run is itself a valid terms_in.pl — same shape).
%         For each Seq, calls the grammar's print_stmt(Term, Texts) — the
%         print direction: Texts is the list of canonical token texts.
%         Writes one line per Seq to printed_out.pl:
%             printed(Seq, [T1, T2, ...]).   -- every Ti ALWAYS single-quoted
%             printfailed(Seq).              -- print_stmt failed/raised
%
%         Every Ti is written through write_quoted_atom/2 below, which
%         ALWAYS wraps it in single quotes (backslash doubled, then quote
%         doubled) rather than relying on writeq's "quote only if needed"
%         heuristic. This is a deliberate, self-imposed format: it makes
%         printed_out.pl parseable on the Python side with a tiny,
%         hand-written scanner (open-quote, escaped-quote/backslash body,
%         close-quote, repeat) instead of a general Prolog term reader.
%         folded/failed lines, by contrast, use plain writeq — nothing
%         downstream re-parses Term's *text*; it is carried as an opaque
%         string and only ever compared for equality against another
%         writeq'd Term (see run_fold.py's round-trip check), and writeq
%         is deterministic for a given term so that comparison is sound.

% No :- initialization/1,2 directive here on purpose: this file is always
% loaded with an explicit -g main or -g unfold on the command line (see
% invocation block above), and initialization(_, main) has its own
% argv/halt semantics in SWI that would fight with that -g goal. main/0
% and unfold/0 below are the only two entry points, selected by -g.

% ---------------------------------------------------------------------
% main/0 — fold direction.

main :-
    current_prolog_flag(argv, Argv),
    ( Argv = [GrammarFile, StmtsInFile, TermsOutFile] ->
        true
    ;
        format(user_error, "driver.pl main: expected 3 args (grammar stmts_in terms_out), got ~q~n", [Argv]),
        halt(1)
    ),
    load_grammar(GrammarFile),
    load_facts(StmtsInFile),
    findall(Seq-Tokens, stmt_tokens(Seq, Tokens), Pairs),
    setup_call_cleanup(
        open(TermsOutFile, write, Out),
        fold_all(Pairs, Out),
        close(Out)
    ),
    halt(0).

fold_all([], _).
fold_all([Seq-Tokens|Rest], Out) :-
    ( catch(stmt(Term, Tokens, []), Err, (report_grammar_error(Seq, Err), fail)) ->
        format(Out, "folded(~w, ", [Seq]),
        writeq(Out, Term),
        format(Out, ").~n", [])
    ;
        format(Out, "failed(~w).~n", [Seq])
    ),
    fold_all(Rest, Out).

% ---------------------------------------------------------------------
% unfold/0 — print direction.

unfold :-
    current_prolog_flag(argv, Argv),
    ( Argv = [GrammarFile, TermsInFile, PrintedOutFile] ->
        true
    ;
        format(user_error, "driver.pl unfold: expected 3 args (grammar terms_in printed_out), got ~q~n", [Argv]),
        halt(1)
    ),
    load_grammar(GrammarFile),
    load_facts(TermsInFile),
    findall(Seq-Term, folded(Seq, Term), Pairs),
    setup_call_cleanup(
        open(PrintedOutFile, write, Out),
        unfold_all(Pairs, Out),
        close(Out)
    ),
    halt(0).

unfold_all([], _).
unfold_all([Seq-Term|Rest], Out) :-
    ( catch(print_stmt(Term, Texts), Err, (report_grammar_error(Seq, Err), fail)) ->
        format(Out, "printed(~w, [", [Seq]),
        write_quoted_list(Out, Texts),
        format(Out, "]).~n", [])
    ;
        format(Out, "printfailed(~w).~n", [Seq])
    ),
    unfold_all(Rest, Out).

% ---------------------------------------------------------------------
% shared helpers

load_grammar(File) :-
    catch(consult(File), Err,
          ( format(user_error, "driver.pl: could not load grammar ~q: ~q~n", [File, Err]),
            halt(1) )).

load_facts(File) :-
    catch(consult(File), Err,
          ( format(user_error, "driver.pl: could not load facts ~q: ~q~n", [File, Err]),
            halt(1) )).

report_grammar_error(Seq, Err) :-
    format(user_error, "driver.pl: seq ~w raised ~q~n", [Seq, Err]).

% write_quoted_list/2 — comma-separated, every element forced through
% write_quoted_atom/2. Numbers are stringified first (atom_number/2) so a
% numeric token text still comes out as a quoted atom, e.g. '15'.
write_quoted_list(_, []).
write_quoted_list(Out, [T]) :-
    !,
    write_quoted_atom(Out, T).
write_quoted_list(Out, [T|Ts]) :-
    write_quoted_atom(Out, T),
    write(Out, ', '),
    write_quoted_list(Out, Ts).

write_quoted_atom(Out, A) :-
    ( number(A) -> atom_number(Text, A) ; Text = A ),
    escape_pl_atom(Text, Escaped),
    format(Out, "'~w'", [Escaped]).

% escape_pl_atom/2 — backslash doubled first, THEN single quote doubled.
% Mirrors run_fold.py's quote_atom() exactly (same order, same two rules)
% so the two ends of this format always agree.
escape_pl_atom(In, Out) :-
    atomic_list_concat(BSParts, '\\', In),
    atomic_list_concat(BSParts, '\\\\', Tmp),
    atomic_list_concat(QParts, '''', Tmp),
    atomic_list_concat(QParts, '''''', Out).
