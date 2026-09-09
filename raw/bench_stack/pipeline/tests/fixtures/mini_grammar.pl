% mini_grammar.pl — hand-written 2-statement-type fixture grammar for the
% exp_014 FOLD HARNESS. It exists to prove pipeline/prolog/driver.pl and
% pipeline/run_fold.py against a grammar the harness agent actually owns,
% without needing the real out/grammar/pig.pl (owned by another agent).
% It conforms EXACTLY to the stmt/3 + print_stmt/2 contract every real
% out/grammar/<lang>.pl must also honor:
%
%   stmt(Term, Tokens, [])  — DCG-callable (written below as stmt//1,
%                             which SWI expands to stmt/3 automatically).
%                             Tokens is [tok(Kind,Text), ...], Kind in
%                             {keyword,word,number,string,symbol}, Text
%                             the exact source text (keywords keep their
%                             original source case in Text).
%   print_stmt(Term, Texts) — Texts is the list of canonical token texts
%                             (keywords lowercase, one canonical spelling
%                             per token). print then parse must reproduce
%                             Term (term fixpoint) — see run_fold.py's
%                             round-trip check.
%
% No :- module/2 directive on purpose: real out/grammar/<lang>.pl files
% are plain consult()able Prolog, loaded straight into the caller's
% module (driver.pl calls stmt/3 and print_stmt/2 unqualified right
% after consult), so this fixture matches that shape rather than adding
% module-visibility machinery the real grammars won't have either.
%
% Two toy statement types:
%
%   Type A — LOAD assignment:
%     REL = LOAD 'FILE' ;
%       --> assign(rel(Rel), load(lit(File)))
%     (File is the string's content with its source quote characters
%     stripped — the Term holds the *value*, not the raw source text.)
%
%   Type B — FILTER assignment (this is literally the contract's own
%   worked example: assign(rel(b), filter(rel(a), gt(col(v), lit(15))))):
%     REL = FILTER SRC BY FIELD > NUM ;
%       --> assign(rel(Rel), filter(rel(Src), gt(col(Field), lit(Num))))
%
% Keywords LOAD / FILTER / BY are matched case-insensitively (Pig-style),
% same as a real grammar would have to, so the fixture also proves the
% "keywords keep original case in Text" half of the contract: a source
% file spelling `load` or `Load` still folds, and print_stmt always
% re-emits the canonical lowercase spelling.

% ---- parse direction (stmt//1, DCG) ----

stmt(assign(rel(Rel), load(lit(File)))) -->
    [tok(word, Rel)],
    [tok(symbol, '=')],
    [tok(keyword, KwLoad)], { downcase_atom(KwLoad, load) },
    [tok(string, RawFile)], { unquote(RawFile, File) },
    [tok(symbol, ';')].

stmt(assign(rel(Rel), filter(rel(Src), gt(col(Field), lit(Num))))) -->
    [tok(word, Rel)],
    [tok(symbol, '=')],
    [tok(keyword, KwFilter)], { downcase_atom(KwFilter, filter) },
    [tok(word, Src)],
    [tok(keyword, KwBy)], { downcase_atom(KwBy, by) },
    [tok(word, Field)],
    [tok(symbol, '>')],
    [tok(number, NumText)], { atom_number(NumText, Num) },
    [tok(symbol, ';')].

% ---- print direction ----

print_stmt(assign(rel(Rel), load(lit(File))), [Rel, '=', load, Quoted, ';']) :-
    quote_source(File, Quoted).

print_stmt(assign(rel(Rel), filter(rel(Src), gt(col(Field), lit(Num)))),
           [Rel, '=', filter, Src, by, Field, '>', NumText, ';']) :-
    atom_number(NumText, Num).

% ---- helpers (fixture-local; a real grammar owns its own equivalents) ----

% unquote/2 — strip exactly one leading and one trailing source quote
% character. Deliberately does NOT undo backslash-escapes: the fixture's
% string leaf (see mini_spec.py) allows `\.` inside a string, and Term
% only needs to round-trip through this same grammar, so keeping the
% escapes verbatim in File is enough for the term-fixpoint law.
unquote(Raw, Unquoted) :-
    atom_string(Raw, S0),
    string_concat('\'', S1, S0),
    string_concat(S2, '\'', S1),
    atom_string(Unquoted, S2).

quote_source(File, Quoted) :-
    atomic_list_concat(['\'', File, '\''], Quoted).
