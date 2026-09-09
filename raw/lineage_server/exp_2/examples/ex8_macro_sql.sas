/* ex8: a macro wrapping PROC SQL — must be unwrapped, params substituted,
   then handed to sqlglot; %let feeds the invocation */
%let src_lib = raw;

%macro load_customers(month, mart=work);
proc sql;
    create table &mart..cust_&month. as
    select c.id, c.name, r.region_name
    from &src_lib..customer as c
    left join &src_lib..region as r
        on c.region_id = r.id;
quit;
%mend load_customers;

%load_customers(jan);

data work.cust_jan_active;
    set work.cust_jan(where=(region_name ne ""));
run;
