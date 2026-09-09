-- h06_nested_subquery.hql
-- Customers whose COMPLETED-order total exceeds the average total across
-- all customers: a join against a grouped subquery, filtered by a scalar
-- subquery average.
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

CREATE EXTERNAL TABLE customers (
  customer_id INT,
  name STRING,
  region STRING
)
ROW FORMAT DELIMITED FIELDS TERMINATED BY ','
LOCATION 'corpus/data/hive/customers.csv'
TBLPROPERTIES ('skip.header.line.count'='1');

CREATE TABLE out_h06_nested_subquery AS
SELECT
  c.customer_id,
  c.name,
  c.region,
  t.total_amount
FROM customers c
JOIN (
  SELECT customer_id, SUM(COALESCE(amount, 0.0)) AS total_amount
  FROM orders
  WHERE status = 'COMPLETED'
  GROUP BY customer_id
) t ON c.customer_id = t.customer_id
WHERE t.total_amount > (
  SELECT AVG(total_amount) FROM (
    SELECT customer_id, SUM(COALESCE(amount, 0.0)) AS total_amount
    FROM orders
    WHERE status = 'COMPLETED'
    GROUP BY customer_id
  ) avg_sub
)
ORDER BY t.total_amount DESC;
