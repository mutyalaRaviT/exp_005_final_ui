/* ex2: merge with in= flags, by-group logic, conditional logic noise */
data work.matched;
    merge
        work.customers(in=in_cust keep=id name)
        work.orders(in=in_ord rename=(order_amt=amount));
    by id;
    if in_cust and in_ord;
    if amount > 1000 then tier = "GOLD";
    else tier = "STD";
run;
