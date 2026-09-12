-- Схема базы данных партнёров и истории отгрузок.
-- Диалект: SQLite 3. Имена таблиц и полей оформлены в snake_case.

PRAGMA foreign_keys = ON;

-- Сначала удаляются зависимые объекты, затем родительские таблицы.
DROP VIEW IF EXISTS partner_delivery_history;
DROP TABLE IF EXISTS delivery_items;
DROP TABLE IF EXISTS deliveries;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS partners;

CREATE TABLE partners (
    partner_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(200) NOT NULL,
    inn         VARCHAR(12) NOT NULL,
    email       VARCHAR(254) COLLATE NOCASE NOT NULL,
    phone       VARCHAR(20),
    address     VARCHAR(300),
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_partners_inn UNIQUE (inn),
    CONSTRAINT uq_partners_email UNIQUE (email),
    CONSTRAINT chk_partners_name CHECK (length(trim(name)) > 0),
    CONSTRAINT chk_partners_inn CHECK (
        length(inn) IN (10, 12)
        AND inn NOT GLOB '*[^0-9]*'
    ),
    CONSTRAINT chk_partners_email CHECK (email LIKE '%_@_%._%')
);

CREATE TABLE products (
    product_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    sku         VARCHAR(30) NOT NULL,
    name        VARCHAR(200) NOT NULL,
    unit        VARCHAR(20) NOT NULL,
    price       DECIMAL(12, 2) NOT NULL,

    CONSTRAINT uq_products_sku UNIQUE (sku),
    CONSTRAINT chk_products_sku CHECK (length(trim(sku)) > 0),
    CONSTRAINT chk_products_name CHECK (length(trim(name)) > 0),
    CONSTRAINT chk_products_unit CHECK (length(trim(unit)) > 0),
    CONSTRAINT chk_products_price CHECK (price >= 0)
);

CREATE TABLE deliveries (
    delivery_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id       INT NOT NULL,
    delivery_number  VARCHAR(30) NOT NULL,
    delivery_date    DATE NOT NULL,
    status           VARCHAR(20) NOT NULL DEFAULT 'planned',
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_deliveries_number UNIQUE (delivery_number),
    CONSTRAINT chk_deliveries_number CHECK (length(trim(delivery_number)) > 0),
    CONSTRAINT chk_deliveries_date CHECK (delivery_date = date(delivery_date)),
    CONSTRAINT chk_deliveries_status CHECK (
        status IN ('planned', 'shipped', 'delivered', 'cancelled')
    ),
    CONSTRAINT fk_deliveries_partner
        FOREIGN KEY (partner_id)
        REFERENCES partners (partner_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE TABLE delivery_items (
    delivery_id  INT NOT NULL,
    product_id   INT NOT NULL,
    quantity     INT NOT NULL,
    unit_price   DECIMAL(12, 2) NOT NULL,

    CONSTRAINT pk_delivery_items PRIMARY KEY (delivery_id, product_id),
    CONSTRAINT chk_delivery_items_quantity CHECK (quantity > 0),
    CONSTRAINT chk_delivery_items_price CHECK (unit_price >= 0),
    CONSTRAINT fk_delivery_items_delivery
        FOREIGN KEY (delivery_id)
        REFERENCES deliveries (delivery_id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,
    CONSTRAINT fk_delivery_items_product
        FOREIGN KEY (product_id)
        REFERENCES products (product_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE INDEX idx_deliveries_partner_date
    ON deliveries (partner_id, delivery_date);

CREATE INDEX idx_delivery_items_product
    ON delivery_items (product_id);

CREATE VIEW partner_delivery_history AS
SELECT
    p.partner_id,
    p.name AS partner_name,
    d.delivery_id,
    d.delivery_number,
    d.delivery_date,
    d.status,
    pr.product_id,
    pr.sku,
    pr.name AS product_name,
    di.quantity,
    di.unit_price,
    ROUND(di.quantity * di.unit_price, 2) AS line_total
FROM partners AS p
JOIN deliveries AS d
    ON d.partner_id = p.partner_id
JOIN delivery_items AS di
    ON di.delivery_id = d.delivery_id
JOIN products AS pr
    ON pr.product_id = di.product_id;
