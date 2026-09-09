/*Analyzed: 08/24/2026 13:07:20
Complexity: 3 210.5 LoC: 14
Errors: 0 in 0/2 Blocks
*/

/*BLOCKID 1:3535353535353535, Data Step, Lines: 5 - 7 to 11 : 100%;*/
data mart.dashboard;
    merge mart.cust_acct(in=a) work.combined(in=b);
    by id;
    if a or b;
run;
/*ENDBLOCKID 1:3535353535353535, Data Step;*/

/*BLOCKID 2:3636363636363636, Proc Sort, Lines: 3 - 13 to 15 : 100%;*/
proc sort data=mart.dashboard out=mart.dashboard_final;
    by descending total_amt;
run;
/*ENDBLOCKID 2:3636363636363636, Proc Sort;*/
