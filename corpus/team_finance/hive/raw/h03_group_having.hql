-- h03_group_having.hql
-- GROUP BY customer with aggregates, HAVING keeps only customers above a
-- COMPLETED-order total.
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

CREATE TABLE out_h03_group_having AS
SELECT
  customer_id,
  COUNT(*) AS order_count,
  SUM(COALESCE(amount, 0.0)) AS total_amount,
  AVG(COALESCE(amount, 0.0)) AS avg_amount
FROM orders
WHERE status = 'COMPLETED'
GROUP BY customer_id
HAVING SUM(COALESCE(amount, 0.0)) > 200.0
ORDER BY total_amount DESC;
