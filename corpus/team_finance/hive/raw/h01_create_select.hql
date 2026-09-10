-- h01_create_select.hql
-- CTAS: pick COMPLETED orders, cast amount, order + limit.
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

CREATE TABLE out_h01_create_select AS
SELECT
  order_id,
  customer_id,
  CAST(amount AS DOUBLE) AS amount,
  status,
  order_date
FROM orders
WHERE status = 'COMPLETED'
ORDER BY amount DESC
LIMIT 5;
