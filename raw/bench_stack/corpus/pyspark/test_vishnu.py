spark = make_spark()

# ---- b_001  lines 4-4  LIBNAME sales 'C:\SASData\Sales'
LIBS["sales"] = "C:\\SASData\\Sales"

# ---- b_002  lines 10-19  DATA sales.sales_data
FORMATS["date"] = "mmddyy10."
put("sales.sales_data", sas_datalines(spark,
    columns=[("sale_id", "char", None), ("sale_amount", "num", None), ("date", "num", "mmddyy10")],
    rows="001 100 01/01/2023\n002 150 02/15/2023\n003 200 03/20/2023"))

# ---- b_003  lines 25-35  PROC SQL
put("sales.total_sales", ds["sales.sales_data"].agg(F.sum(F.col("sale_amount")).alias("total_sales")))

# ---- b_004  lines 41-51  PROC SQL
put("sales.avg_sales", ds["sales.sales_data"].agg(F.avg(F.col("sale_amount")).alias("avg_sales")))

# ---- b_005  lines 57-60  DATA sales.q1_sales
put("sales.q1_sales", ds["sales.sales_data"].filter((F.month(F.col("date")) <= F.lit(3))))

# ---- b_006  lines 66-76  PROC SQL
put("sales.q1_total_sales", ds["sales.q1_sales"].agg(F.sum(F.col("sale_amount")).alias("q1_total_sales")))

# ---- b_007  lines 82-92  PROC SQL
put("sales.q1_avg_sales", ds["sales.q1_sales"].agg(F.avg(F.col("sale_amount")).alias("q1_avg_sales")))

# ---- b_008  lines 98-108  PROC SQL
put("sales.max_sale", ds["sales.sales_data"].agg(F.max(F.col("sale_amount")).alias("max_sale_amount")))

# ---- b_009  lines 114-124  PROC SQL
put("sales.min_sale", ds["sales.sales_data"].agg(F.min(F.col("sale_amount")).alias("min_sale_amount")))

# ---- b_010  lines 130-147  PROC SQL
_scalar1 = scalar(ds["sales.avg_sales"].select(F.col("avg_sales")))
put("sales.above_avg_sales", ds["sales.sales_data"].filter((F.col("sale_amount") > F.lit(_scalar1))).select("*"))

# ---- b_011  lines 153-166  PROC SQL
put("sales.monthly_sales", ds["sales.sales_data"].groupBy(F.month(F.col("date")).alias("sale_month")).agg(F.sum(F.col("sale_amount")).alias("total_monthly_sales")))

# ---- b_012  lines 172-175  DATA sales.final_summary
# LINEAGEQ CHECK: BY variable sale_month is not on sales.q1_total_sales (its columns: q1_total_sales) -> SAS logs an ERROR, stops the step, and leaves 0 observations.
put("sales.final_summary", sas_merge(spark, [("sales.monthly_sales", ds["sales.monthly_sales"]), ("sales.q1_total_sales", ds["sales.q1_total_sales"])], by=["sale_month"]))


# ---- every dataset the program created, in SAS log order
for _name in ORDER:
    sas_print(_name)
spark.stop()
