/*Analyzed: 08/24/2026 12:41:09
Complexity: 4 310.2 LoC: 18
Errors: 0 in 0/3 Blocks
*/

%include 'inc_common_setup.sas';

/*BLOCKID 1:9990005556667778, Data Step, Lines: 4 - 9 to 12 : 100%;*/
data work.tx_recent;
    set raw.transactions(where=(year >= &cutoff.));
run;
/*ENDBLOCKID 1:9990005556667778, Data Step;*/

/*BLOCKID 2:1010106667778889, Macro Call, Lines: 1 - 14 to 14 : 100%;*/
%dedupe(work.tx_recent, mart.tx_dedup);
/*ENDBLOCKID 2:1010106667778889, Macro Call;*/
