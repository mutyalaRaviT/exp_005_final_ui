-- h04_join_two_tables.hql
-- Inner join orders to customers, keep COMPLETED orders only.
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

CREATE TABLE out_h04_join_two_tables AS
SELECT
  o.order_id,
  c.name,
  c.region,
  o.amount,
  o.status
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.status = 'COMPLETED'
ORDER BY o.order_id;
