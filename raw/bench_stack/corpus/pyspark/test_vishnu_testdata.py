spark = make_spark()

# ---- b_001  lines 11-11  LIBNAME sales 'C:\SASData\Sales'
LIBS["sales"] = "C:\\SASData\\Sales"

# ---- b_002  lines 17-44  DATA sales.sales_data
FORMATS["date"] = "mmddyy10."
put("sales.sales_data", sas_datalines(spark,
    columns=[("sale_id", "char", None), ("sale_amount", "num", None), ("date", "num", "mmddyy10")],
    rows="001 0 01/01/2023\n002 140 01/01/2023\n003 151 01/01/2023\n004 75 01/21/2023\n005 80 02/05/2023\n006 130 02/08/2023\n007 199.99 03/19/2023\n008 75 03/22/2023\n009 150 03/31/2023\n010 149.99 04/01/2023\n011 0 04/01/2023\n012 50 04/02/2023\n013 130 05/03/2023\n014 50 06/08/2023\n015 734.01 06/15/2023\n016 130 07/18/2023\n017 260 08/23/2023\n018 300 09/08/2023\n019 175 10/19/2023\n020 50 11/26/2023\n021 120 12/25/2023\n022 150.01 12/31/2023"))

# ---- b_003  lines 50-60  PROC SQL
put("sales.total_sales", ds["sales.sales_data"].agg(F.sum(F.col("sale_amount")).alias("total_sales")))

# ---- b_004  lines 66-76  PROC SQL
put("sales.avg_sales", ds["sales.sales_data"].agg(F.avg(F.col("sale_amount")).alias("avg_sales")))

# ---- b_005  lines 82-85  DATA sales.q1_sales
put("sales.q1_sales", ds["sales.sales_data"].filter((F.month(F.col("date")) <= F.lit(3))))

# ---- b_006  lines 91-101  PROC SQL
put("sales.q1_total_sales", ds["sales.q1_sales"].agg(F.sum(F.col("sale_amount")).alias("q1_total_sales")))

# ---- b_007  lines 107-117  PROC SQL
put("sales.q1_avg_sales", ds["sales.q1_sales"].agg(F.avg(F.col("sale_amount")).alias("q1_avg_sales")))

# ---- b_008  lines 123-133  PROC SQL
put("sales.max_sale", ds["sales.sales_data"].agg(F.max(F.col("sale_amount")).alias("max_sale_amount")))

# ---- b_009  lines 139-149  PROC SQL
put("sales.min_sale", ds["sales.sales_data"].agg(F.min(F.col("sale_amount")).alias("min_sale_amount")))

# ---- b_010  lines 155-172  PROC SQL
_scalar1 = scalar(ds["sales.avg_sales"].select(F.col("avg_sales")))
put("sales.above_avg_sales", ds["sales.sales_data"].filter((F.col("sale_amount") > F.lit(_scalar1))).select("*"))

# ---- b_011  lines 178-191  PROC SQL
put("sales.monthly_sales", ds["sales.sales_data"].groupBy(F.month(F.col("date")).alias("sale_month")).agg(F.sum(F.col("sale_amount")).alias("total_monthly_sales")))

# ---- b_012  lines 197-200  DATA sales.final_summary
# LINEAGEQ CHECK: BY variable sale_month is not on sales.q1_total_sales (its columns: q1_total_sales) -> SAS logs an ERROR, stops the step, and leaves 0 observations.
put("sales.final_summary", sas_merge(spark, [("sales.monthly_sales", ds["sales.monthly_sales"]), ("sales.q1_total_sales", ds["sales.q1_total_sales"])], by=["sale_month"]))

# ---- b_013  lines 206-206  PROC PRINT sales.sales_data
# PROC PRINT sales.sales_data -> listed by sas_print at the end of this program
# TITLE 'sales_data'

# ---- b_014  lines 207-207  PROC PRINT sales.total_sales
# PROC PRINT sales.total_sales -> listed by sas_print at the end of this program
# TITLE 'total_sales'

# ---- b_015  lines 208-208  PROC PRINT sales.avg_sales
# PROC PRINT sales.avg_sales -> listed by sas_print at the end of this program
# TITLE 'avg_sales'

# ---- b_016  lines 209-209  PROC PRINT sales.q1_sales
# PROC PRINT sales.q1_sales -> listed by sas_print at the end of this program
# TITLE 'q1_sales'

# ---- b_017  lines 210-210  PROC PRINT sales.q1_total_sales
# PROC PRINT sales.q1_total_sales -> listed by sas_print at the end of this program
# TITLE 'q1_total_sales'

# ---- b_018  lines 211-211  PROC PRINT sales.q1_avg_sales
# PROC PRINT sales.q1_avg_sales -> listed by sas_print at the end of this program
# TITLE 'q1_avg_sales'

# ---- b_019  lines 212-212  PROC PRINT sales.max_sale
# PROC PRINT sales.max_sale -> listed by sas_print at the end of this program
# TITLE 'max_sale'

# ---- b_020  lines 213-213  PROC PRINT sales.min_sale
# PROC PRINT sales.min_sale -> listed by sas_print at the end of this program
# TITLE 'min_sale'

# ---- b_021  lines 214-214  PROC PRINT sales.above_avg_sales
# PROC PRINT sales.above_avg_sales -> listed by sas_print at the end of this program
# TITLE 'above_avg_sales'

# ---- b_022  lines 215-215  PROC PRINT sales.monthly_sales
# PROC PRINT sales.monthly_sales -> listed by sas_print at the end of this program
# TITLE 'monthly_sales'

# ---- b_023  lines 216-216  PROC PRINT sales.final_summary
# PROC PRINT sales.final_summary -> listed by sas_print at the end of this program
# TITLE 'final_summary'


# ---- every dataset the program created, in SAS log order
for _name in ORDER:
    sas_print(_name)
spark.stop()
