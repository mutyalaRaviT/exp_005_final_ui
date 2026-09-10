-- h02_where_case.hql
-- WHERE filter + CASE WHEN bucketing + COALESCE on nullable amount.
CREATE EXTERNAL TABLE orders (
  order_id INT,
  customer_id INT,
  amount DOUBLE,
  status STRING,
  order_date STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
LOCATION 'corpus/data/hive/orders.csv'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE TABLE out_h02_where_case AS
SELECT
  order_id,
  customer_id,
  COALESCE(amount, 0.0) AS amount_filled,
  CASE
    WHEN COALESCE(amount, 0.0) >= 500.0 THEN 'LARGE'
    WHEN COALESCE(amount, 0.0) >= 100.0 THEN 'MEDIUM'
    WHEN COALESCE(amount, 0.0) > 0.0 THEN 'SMALL'
    ELSE 'ZERO'
  END AS amount_bucket,
  status
FROM orders
WHERE status IN ('COMPLETED', 'PENDING')
ORDER BY order_id;
