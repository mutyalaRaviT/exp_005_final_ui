#%%
scriptName='file_lineage_example1'
workspace = '/sas2py/app/workspace'
import sys
sys.path.insert(1, f'{workspace}/commonlib')
from common_pyspark import *
init(globals(), workspace, logBaseDir = f'{workspace}/logs',
    scriptName=scriptName, ENV="local")
def setv(name, val=""):
    pyspark.setv(name, val, global_dict=globals())
#execute_external_file('globals.py')
def sparkSQL(sql):
    try:
        return spark.sql(sql)
    except Exception as e:
        print("Error:", e)
    return None
conf = spark.sparkContext.getConf().getAll()
for key, value in conf:
    if 'memory' in key:
        print(f"{key}: {value}")

#%%
setlib('sales', 'C:/SASData/Sales')

#%%
START_BLOCK('Passed DataStep',
            '4:6887988991394376008 - Lines: 12 - 15 to 27 : 14%')
sales_sales_data_data = [
    ('001', 100),
    ('002', 150),
    ('003', 200)]
sales_sales_data_schema = StructType([
        StructField('Sale_Id', StringType(), True),
        StructField('Sale_Amount', DateType(), True)
])
sales_sales_data = spark.createDataFrame(
    sales_sales_data_data, schema=sales_sales_data_schema)
setdf('sales_sales_data', sales_sales_data)
END_BLOCK('Passed DataStep', '4:6887988991394376008')

#%%
START_BLOCK('Passed ProcSQL',
            '6:6887988991394376008 - Lines: 13 - 30 to 43 : 23%')
sales_total_sales = sparkSQL(
        f'''
    SELECT
        SUM(sale_amount) AS total_sales
    FROM
        sales.sales_data
'''
)
setdf('sales_total_sales', sales_total_sales)
END_BLOCK('Passed ProcSQL', '6:6887988991394376008')

#%%
#  1. Calculate Total Sales

#%%
START_BLOCK('Passed ProcSQL',
            '8:6887988991394376008 - Lines: 13 - 46 to 59 : 32%')
sales_avg_sales = sparkSQL(
        f'''
    SELECT
        AVG(sale_amount) AS avg_sales
    FROM
        sales.sales_data
'''
)
setdf('sales_avg_sales', sales_avg_sales)
END_BLOCK('Passed ProcSQL', '8:6887988991394376008')

#%%
START_BLOCK('Passed DataStep',
            '10:6887988991394376008 - Lines: 6 - 62 to 68 : 37%')
sales_q1_sales = sparkSQL(
        f'''
    WITH _setCTE AS(
        SELECT
            *
        FROM
            sales.sales_data
    )
    SELECT
        *
    FROM
        _setCTE
    WHERE
        MONTH(DATE) <= 3
'''
)
setdf('sales.q1_sales', sales_q1_sales)
END_BLOCK('Passed DataStep', '10:6887988991394376008')

#%%
START_BLOCK('Passed ProcSQL',
            '12:6887988991394376008 - Lines: 13 - 71 to 84 : 45%')
sales_q1_total_sales = sparkSQL(
        f'''
    SELECT
        SUM(sale_amount) AS q1_total_sales
    FROM
        sales.q1_sales
'''
)
setdf('sales_q1_total_sales', sales_q1_total_sales)
END_BLOCK('Passed ProcSQL', '12:6887988991394376008')

#%%
#  3. Extract Sales in Q1

#%%
START_BLOCK('Passed ProcSQL',
            '14:6887988991394376008 - Lines: 13 - 87 to 100 : 54%')
sales_q1_avg_sales = sparkSQL(
        f'''
    SELECT
        AVG(sale_amount) AS q1_avg_sales
    FROM
        sales.q1_sales
'''
)
setdf('sales_q1_avg_sales', sales_q1_avg_sales)
END_BLOCK('Passed ProcSQL', '14:6887988991394376008')

#%%
START_BLOCK('Passed ProcSQL',
            '16:6887988991394376008 - Lines: 13 - 103 to 116 : 63%')
sales_max_sale = sparkSQL(
        f'''
    SELECT
        MAX(sale_amount) AS max_sale_amount
    FROM
        sales.sales_data
'''
)
setdf('sales_max_sale', sales_max_sale)
END_BLOCK('Passed ProcSQL', '16:6887988991394376008')

#%%
START_BLOCK('Passed ProcSQL',
            '18:6887988991394376008 - Lines: 13 - 119 to 132 : 72%')
sales_min_sale = sparkSQL(
        f'''
    SELECT
        MIN(sale_amount) AS min_sale_amount
    FROM
        sales.sales_data
'''
)
setdf('sales_min_sale', sales_min_sale)
END_BLOCK('Passed ProcSQL', '18:6887988991394376008')

#%%
#  5. Calculate Average Sales in Q1

#%%
START_BLOCK('Passed ProcSQL',
            '20:6887988991394376008 - Lines: 20 - 135 to 155 : 84%')
sales_above_avg_sales = sparkSQL(
        f'''
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
        )
'''
)
setdf('sales_above_avg_sales', sales_above_avg_sales)
END_BLOCK('Passed ProcSQL', '20:6887988991394376008')

#%%
START_BLOCK('Passed ProcSQL',
            '22:6887988991394376008 - Lines: 16 - 158 to 174 : 95%')
sales_monthly_sales = sparkSQL(
        f'''
    SELECT
        MONTH(DATE) AS sale_month,
        SUM(sale_amount) AS total_monthly_sales
    FROM
        sales.sales_data
    GROUP BY
        MONTH(DATE)
'''
)
setdf('sales_monthly_sales', sales_monthly_sales)
END_BLOCK('Passed ProcSQL', '22:6887988991394376008')

#%%
START_BLOCK('Passed DataStep',
            '24:6887988991394376008 - Lines: 6 - 177 to 183 : 100%')
sales_monthly_sales = getdf('sales.monthly_sales')
sales_monthly_sales = sales_monthly_sales.withColumn("a", F.lit(1))
sales_q1_total_sales = getdf('sales.q1_total_sales')
sales_q1_total_sales = sales_q1_total_sales.withColumn("b", F.lit(1))
useColumns = filter(lambda x: x != 'None', ['sale_month'])
sales_final_summary_out = pyspark.mergedatasets(
    sales_monthly_sales, sales_q1_total_sales, list(useColumns))
END_BLOCK('Passed DataStep', '24:6887988991394376008')

#%%
#  7. Find Minimum Sale Amount

#%%
#  8. Filter Sales above Average

#%%
#  9. Create Monthly Sales Summary

#%%
#  10. Merge Sales Summary with Q1 Total

