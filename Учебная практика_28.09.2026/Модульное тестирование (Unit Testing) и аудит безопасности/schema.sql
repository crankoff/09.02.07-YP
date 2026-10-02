PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS product_types (
    product_type_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    coefficient REAL NOT NULL CHECK (coefficient > 0)
);

CREATE TABLE IF NOT EXISTS material_types (
    material_type_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    waste_percent REAL NOT NULL CHECK (
        waste_percent >= 0 AND waste_percent < 100
    )
);

INSERT OR IGNORE INTO product_types (
    product_type_id,
    name,
    coefficient
) VALUES
    (1, 'Ламинированная панель', 1.10),
    (2, 'Модульная секция', 2.50),
    (3, 'Фасадный элемент', 3.20),
    (4, 'Стандартное изделие', 1.00);

INSERT OR IGNORE INTO material_types (
    material_type_id,
    name,
    waste_percent
) VALUES
    (1, 'Древесная плита', 0.80),
    (2, 'Листовой металл', 0.50),
    (3, 'Композит', 1.50),
    (4, 'Материал без технологических потерь', 0.00);
