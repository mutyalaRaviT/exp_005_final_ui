-- h05_insert_union.hql
-- CREATE TABLE for the target shape, then INSERT INTO ... SELECT a UNION ALL
-- of two disjoint slices (high-value COMPLETED vs low-value PENDING).
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

CREATE TABLE out_h05_insert_union (
  order_id INT,
  customer_id INT,
  amount DOUBLE,
  status STRING,
  source_flag STRING
);

INSERT INTO out_h05_insert_union
SELECT order_id, customer_id, COALESCE(amount, 0.0), status, 'HIGH_VALUE'
FROM orders
WHERE status = 'COMPLETED' AND COALESCE(amount, 0.0) >= 500.0
UNION ALL
SELECT order_id, customer_id, COALESCE(amount, 0.0), status, 'PENDING_LOW'
FROM orders
WHERE status = 'PENDING' AND COALESCE(amount, 0.0) < 50.0
ORDER BY order_id;
