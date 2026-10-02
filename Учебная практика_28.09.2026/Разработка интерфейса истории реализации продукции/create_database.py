from __future__ import annotations

from pathlib import Path

from database import DATABASE_PATH, connect_database, initialize_database


PARTNERS = [
    ("ООО", "Альфа Снаб", "Соколов Артём Ильич", "+7 900 111-22-33", "info@alpha-snab.example", 8),
    ("ИП", "Вектор", "Крылова Елена Олеговна", "+7 900 222-33-44", "office@vector.example", 7),
    ("ЗАО", "Городские решения", "Петров Максим Сергеевич", "+7 900 333-44-55", "mail@city-solutions.example", 10),
    ("ООО", "Новый партнёр", "Орлова Анна Викторовна", "+7 900 444-55-66", "hello@new-partner.example", 5),
]

PRODUCTS = [
    ("Панель акустическая",),
    ("Плитка декоративная",),
    ("Комплект перегородок",),
    ("Профиль алюминиевый",),
]

SALES = [
    (1, 1, 850, "2026-09-14"),
    (1, 2, 1_200, "2026-08-28"),
    (1, 3, 240, "2026-06-10"),
    (2, 4, 3_500, "2026-09-02"),
    (2, 1, 430, "2026-07-19"),
    (3, 2, 5_000, "2026-09-21"),
    (3, 3, 780, "2026-05-06"),
]


def create_demo_database(database_path: str | Path = DATABASE_PATH) -> None:
    initialize_database(database_path, reset=True)
    with connect_database(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO partners (
                partner_type, name, director, phone, email, rating
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            PARTNERS,
        )
        connection.executemany("INSERT INTO products (name) VALUES (?)", PRODUCTS)
        connection.executemany(
            """
            INSERT INTO sales_history (
                partner_id, product_id, quantity, sale_date
            ) VALUES (?, ?, ?, ?)
            """,
            SALES,
        )


if __name__ == "__main__":
    create_demo_database()
    print(f"Демонстрационная база создана: {DATABASE_PATH}")
