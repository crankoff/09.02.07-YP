-- Проверочные запросы после выполнения python3 etl.py.

SELECT COUNT(*) AS partners_count FROM partners;
SELECT COUNT(*) AS products_count FROM products;
SELECT COUNT(*) AS sales_count FROM sales;

-- Дополнительная проверка: результат должен быть равен 0.
SELECT COUNT(*) AS orphan_sales_count
FROM sales AS s
LEFT JOIN partners AS p ON p.partner_id = s.partner_id
LEFT JOIN products AS pr ON pr.product_id = s.product_id
WHERE p.partner_id IS NULL OR pr.product_id IS NULL;
