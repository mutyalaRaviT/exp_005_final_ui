/* ex7: PROC SQL — create-as-select with joins, a CTE-less subquery,
   an insert-select, and a read-only select */
proc sql;
    create table work.cust_orders as
    select c.id, c.name, o.amount
    from raw.customers as c
    inner join raw.orders as o
        on c.id = o.cust_id
    where o.amount > (select avg(amount) from raw.orders);

    insert into work.audit_log
    select id, 'loaded' as status
    from work.cust_orders;

    select count(*) from work.cust_orders;
quit;
