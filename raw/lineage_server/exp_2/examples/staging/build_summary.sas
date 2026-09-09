/*Analyzed: 08/24/2026 13:04:55
Complexity: 3 240.8 LoC: 18
Errors: 0 in 0/2 Blocks
*/

/*BLOCKID 1:3333333333333333, Proc SQL, Lines: 7 - 7 to 13 : 100%;*/
proc sql;
    create table work.summary as
    select c.id, count(o.order_id) as order_cnt, sum(o.order_amt) as total_amt
    from work.customers as c
    left join work.orders as o on c.id = o.id
    group by c.id;
quit;
/*ENDBLOCKID 1:3333333333333333, Proc SQL;*/

/*BLOCKID 2:3434343434343434, Data Step, Lines: 5 - 15 to 19 : 100%;*/
data work.metrics_long;
    set work.summary;
    metric_name = 'total_amt';
    metric_value = total_amt;
run;
/*ENDBLOCKID 2:3434343434343434, Data Step;*/
