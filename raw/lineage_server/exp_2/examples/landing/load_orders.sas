/*Analyzed: 08/24/2026 13:02:11
Complexity: 2 130.1 LoC: 10
Errors: 0 in 0/1 Blocks
*/

/*BLOCKID 1:3232323232323232, Proc SQL, Lines: 6 - 7 to 12 : 100%;*/
proc sql;
    create table work.orders as
    select order_id, id, order_amt
    from raw.order_extract
    where status ne 'VOID';
quit;
/*ENDBLOCKID 1:3232323232323232, Proc SQL;*/
