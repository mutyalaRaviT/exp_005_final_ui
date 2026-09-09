/* Define library */

/*BLOCKID 2:6887988991394376008, LIBNAME, Lines: 3 - 9 to 12 : 6%;*/
libname sales 'C:\SASData\Sales';
/*ENDBLOCKID 2:6887988991394376008, LIBNAME;*/

/* Create Sales Data */

/*BLOCKID 4:6887988991394376008, DataStep, Lines: 12 - 15 to 27 : 14%;*/
data sales.sales_data;
input sale_id $ sale_amount date :mmddyy10.;
format date mmddyy10.;
datalines;

001 100 01/01/2023
002 150 02/15/2023
003 200 03/20/2023
;
run;
/*ENDBLOCKID 4:6887988991394376008, DataStep;*/

/* 1. Calculate Total Sales */

/*BLOCKID 6:6887988991394376008, Proc SQL, Lines: 13 - 30 to 43 : 23%;*/
PROC SQL;

CREATE TABLE sales.total_sales AS
SELECT
    SUM(sale_amount) AS total_sales
FROM
    sales.sales_data;

;

run;
/*ENDBLOCKID 6:6887988991394376008, Proc SQL;*/

/* 2. Calculate Average Sales */

/*BLOCKID 8:6887988991394376008, Proc SQL, Lines: 13 - 46 to 59 : 32%;*/
PROC SQL;

CREATE TABLE sales.avg_sales AS
SELECT
    AVG(sale_amount) AS avg_sales
FROM
    sales.sales_data;

;

run;
/*ENDBLOCKID 8:6887988991394376008, Proc SQL;*/

/* 3. Extract Sales in Q1 */

/*BLOCKID 10:6887988991394376008, DataStep, Lines: 6 - 62 to 68 : 37%;*/
data sales.q1_sales;
	set sales.sales_data;
	if month(date) <= 3;
run;
/*ENDBLOCKID 10:6887988991394376008, DataStep;*/

/* 4. Calculate Total Sales in Q1 */

/*BLOCKID 12:6887988991394376008, Proc SQL, Lines: 13 - 71 to 84 : 45%;*/
PROC SQL;

CREATE TABLE sales.q1_total_sales AS
SELECT
    SUM(sale_amount) AS q1_total_sales
FROM
    sales.q1_sales;

;

run;
/*ENDBLOCKID 12:6887988991394376008, Proc SQL;*/

/* 5. Calculate Average Sales in Q1 */

/*BLOCKID 14:6887988991394376008, Proc SQL, Lines: 13 - 87 to 100 : 54%;*/
PROC SQL;

CREATE TABLE sales.q1_avg_sales AS
SELECT
    AVG(sale_amount) AS q1_avg_sales
FROM
    sales.q1_sales;

;

run;
/*ENDBLOCKID 14:6887988991394376008, Proc SQL;*/

/* 6. Find Maximum Sale Amount */

/*BLOCKID 16:6887988991394376008, Proc SQL, Lines: 13 - 103 to 116 : 63%;*/
PROC SQL;

CREATE TABLE sales.max_sale AS
SELECT
    MAX(sale_amount) AS max_sale_amount
FROM
    sales.sales_data;

;

run;
/*ENDBLOCKID 16:6887988991394376008, Proc SQL;*/

/* 7. Find Minimum Sale Amount */

/*BLOCKID 18:6887988991394376008, Proc SQL, Lines: 13 - 119 to 132 : 72%;*/
PROC SQL;

CREATE TABLE sales.min_sale AS
SELECT
    MIN(sale_amount) AS min_sale_amount
FROM
    sales.sales_data;

;

run;
/*ENDBLOCKID 18:6887988991394376008, Proc SQL;*/

/* 8. Filter Sales above Average */

/*BLOCKID 20:6887988991394376008, Proc SQL, Lines: 20 - 135 to 155 : 84%;*/
PROC SQL;

CREATE TABLE sales.above_avg_sales AS
SELECT
    *
FROM
    sales.sales_data
WHERE
    sale_amount > (
        SELECT
            avg_sales
        FROM
            sales.avg_sales
    );

;

run;
/*ENDBLOCKID 20:6887988991394376008, Proc SQL;*/

/* 9. Create Monthly Sales Summary */

/*BLOCKID 22:6887988991394376008, Proc SQL, Lines: 16 - 158 to 174 : 95%;*/
PROC SQL;

CREATE TABLE sales.monthly_sales AS
SELECT
    MONTH(DATE) AS sale_month,
    SUM(sale_amount) AS total_monthly_sales
FROM
    sales.sales_data
GROUP BY
    MONTH(DATE);

;

run;
/*ENDBLOCKID 22:6887988991394376008, Proc SQL;*/

/* 10. Merge Sales Summary with Q1 Total */

/*BLOCKID 24:6887988991394376008, DataStep, Lines: 6 - 177 to 183 : 100%;*/
data sales.final_summary;
	merge sales.monthly_sales(in=a) sales.q1_total_sales(in=b);
by sale_month;
run;
/*ENDBLOCKID 24:6887988991394376008, DataStep;*/

