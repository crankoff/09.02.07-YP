PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS partners (
    partner_id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_type VARCHAR(50) NOT NULL,
    name VARCHAR(150) NOT NULL,
    director VARCHAR(150) NOT NULL,
    phone VARCHAR(30) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 0 AND 10)
);

CREATE TABLE IF NOT EXISTS sales_history (
    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id INTEGER NOT NULL,
    sale_date DATE NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    FOREIGN KEY (partner_id)
        REFERENCES partners (partner_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sales_history_partner_id
    ON sales_history (partner_id);
