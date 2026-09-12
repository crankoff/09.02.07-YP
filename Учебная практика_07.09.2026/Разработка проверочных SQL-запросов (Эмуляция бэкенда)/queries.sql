-- Проверочные запросы для будущего приложения.
-- Диалект: SQLite 3. Значения с двоеточием являются именованными параметрами.

-- QUERY_1_BEGIN
-- 1. Список всех партнёров и количество их доставок.
SELECT
    p.partner_id,
    p.name AS partner_name,
    p.inn,
    p.email,
    p.phone,
    p.address,
    COUNT(d.delivery_id) AS delivery_count
FROM partners AS p
LEFT JOIN deliveries AS d
    ON d.partner_id = p.partner_id
GROUP BY
    p.partner_id,
    p.name,
    p.inn,
    p.email,
    p.phone,
    p.address
ORDER BY p.name COLLATE NOCASE, p.partner_id;
-- QUERY_1_END

-- QUERY_2_BEGIN
-- 2. Добавление или обновление партнёра и его первой тестовой доставки.
-- Все изменения выполняются атомарно в одной транзакции.
BEGIN IMMEDIATE TRANSACTION;

INSERT INTO partners (name, inn, email, phone, address)
VALUES (
    :partner_name,
    :partner_inn,
    :partner_email,
    :partner_phone,
    :partner_address
)
ON CONFLICT(inn) DO UPDATE SET
    name = excluded.name,
    email = excluded.email,
    phone = excluded.phone,
    address = excluded.address,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO products (sku, name, unit, price)
VALUES (:product_sku, :product_name, :product_unit, :product_price)
ON CONFLICT(sku) DO UPDATE SET
    name = excluded.name,
    unit = excluded.unit,
    price = excluded.price;

INSERT INTO deliveries (
    partner_id,
    delivery_number,
    delivery_date,
    status
)
SELECT
    p.partner_id,
    :delivery_number,
    :delivery_date,
    :delivery_status
FROM partners AS p
WHERE p.inn = :partner_inn
ON CONFLICT(delivery_number) DO UPDATE SET
    partner_id = excluded.partner_id,
    delivery_date = excluded.delivery_date,
    status = excluded.status;

INSERT INTO delivery_items (delivery_id, product_id, quantity, unit_price)
SELECT
    d.delivery_id,
    pr.product_id,
    :quantity,
    :product_price
FROM deliveries AS d
JOIN products AS pr
    ON pr.sku = :product_sku
WHERE d.delivery_number = :delivery_number
ON CONFLICT(delivery_id, product_id) DO UPDATE SET
    quantity = excluded.quantity,
    unit_price = excluded.unit_price;

COMMIT;
-- QUERY_2_END

-- QUERY_3_BEGIN
-- 3. Детальная история доставок партнёра за выбранный период.
WITH delivery_totals AS (
    SELECT
        delivery_id,
        ROUND(SUM(quantity * unit_price), 2) AS delivery_total
    FROM delivery_items
    GROUP BY delivery_id
)
SELECT
    p.partner_id,
    p.name AS partner_name,
    d.delivery_number,
    d.delivery_date,
    d.status,
    pr.sku,
    pr.name AS product_name,
    di.quantity,
    pr.unit,
    ROUND(di.unit_price, 2) AS unit_price,
    ROUND(di.quantity * di.unit_price, 2) AS line_total,
    dt.delivery_total
FROM partners AS p
JOIN deliveries AS d
    ON d.partner_id = p.partner_id
JOIN delivery_items AS di
    ON di.delivery_id = d.delivery_id
JOIN products AS pr
    ON pr.product_id = di.product_id
JOIN delivery_totals AS dt
    ON dt.delivery_id = d.delivery_id
WHERE p.inn = :partner_inn
  AND d.delivery_date BETWEEN :date_from AND :date_to
ORDER BY d.delivery_date, d.delivery_number, pr.name;
-- QUERY_3_END
