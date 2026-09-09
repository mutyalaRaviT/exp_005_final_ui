/*Analyzed: 08/24/2026 12:05:42
Complexity: 5 402.7 LoC: 31
Errors: 0 in 0/4 Blocks
*/

/*BLOCKID 1:5550001112223334, Macro, Lines: 8 - 7 to 14 : 100%;*/
%macro stage_table(src, dst);
data &dst.;
    set &src.(where=(status = 'A'));
run;
%mend stage_table;
/*ENDBLOCKID 1:5550001112223334, Macro;*/

/*BLOCKID 2:6660002223334445, Macro Call, Lines: 1 - 16 to 16 : 100%;*/
%stage_table(raw.customers, work.customers_stg);
/*ENDBLOCKID 2:6660002223334445, Macro Call;*/

/*BLOCKID 3:7770003334445556, Macro Call, Lines: 1 - 18 to 18 : 100%;*/
%stage_table(raw.accounts, work.accounts_stg);
/*ENDBLOCKID 3:7770003334445556, Macro Call;*/

/*BLOCKID 4:8880004445556667, Data Step, Lines: 5 - 20 to 24 : 100%;*/
data mart.cust_acct;
    merge work.customers_stg(in=c) work.accounts_stg(in=a);
    by cust_id;
    if c and a;
run;
/*ENDBLOCKID 4:8880004445556667, Data Step;*/
