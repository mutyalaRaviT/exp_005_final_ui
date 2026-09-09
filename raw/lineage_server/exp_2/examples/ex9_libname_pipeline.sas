/* ex9: libname statements feeding the Excel export's lib-path columns */
libname raw '/data/landing/raw';
libname mart "/data/warehouse/mart";

data work.stage_orders;
    set raw.orders(where=(status ne 'CANCELLED'));
run;

proc sort data=work.stage_orders out=work.stage_orders_srt;
    by customer_id order_dt;
run;

data mart.orders_final;
    set work.stage_orders_srt;
    by customer_id;
    if last.customer_id;
run;
