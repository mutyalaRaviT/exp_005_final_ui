/*Analyzed: 08/24/2026 13:02:11
Complexity: 2 120.4 LoC: 9
Errors: 0 in 0/1 Blocks
*/

/*BLOCKID 1:3131313131313131, Data Step, Lines: 4 - 7 to 10 : 100%;*/
data work.customers;
    set raw.cust_extract(where=(active = 1));
run;
/*ENDBLOCKID 1:3131313131313131, Data Step;*/
