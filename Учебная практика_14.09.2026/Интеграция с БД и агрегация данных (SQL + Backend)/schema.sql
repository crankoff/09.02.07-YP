PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS sales_history;
DROP TABLE IF EXISTS partners;

CREATE TABLE partners (
    partner_id  INTEGER PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    inn         VARCHAR(12) NOT NULL UNIQUE,
    email       VARCHAR(254) COLLATE NOCASE NOT NULL UNIQUE
);

CREATE TABLE sales_history (
    sale_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id   INTEGER NOT NULL,
    sale_date    DATE NOT NULL,
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    CONSTRAINT fk_sales_history_partner
        FOREIGN KEY (partner_id)
        REFERENCES partners (partner_id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
);

CREATE INDEX idx_sales_history_partner
    ON sales_history (partner_id);
