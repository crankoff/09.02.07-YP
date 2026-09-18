from __future__ import annotations

from pathlib import Path

from core import DATABASE_PATH, connect_database, initialize_database


PARTNERS = [
    ("ООО", "Альфа Снаб", "Соколов Артём Ильич", "+7 900 111-22-33", "info@alpha-snab.example", 8),
    ("ИП", "Вектор", "Крылова Елена Олеговна", "+7 900 222-33-44", "office@vector.example", 7),
    ("АО", "Городские решения", "Петров Максим Сергеевич", "+7 900 333-44-55", "mail@city-solutions.example", 10),
    ("ООО", "Северный торговый дом", "Иванова Мария Андреевна", "+7 900 444-55-66", "sales@north-trade.example", 9),
    ("ИП", "Новый партнёр", "Орлова Анна Викторовна", "+7 900 555-66-77", "hello@new-partner.example", 6),
]

SALES = [
    (1, "2026-01-15", 3_500),
    (1, "2026-03-10", 5_000),
    (2, "2026-02-01", 7_000),
    (2, "2026-05-18", 8_000),
    (3, "2026-01-23", 30_000),
    (3, "2026-04-11", 50_000),
    (4, "2026-02-14", 150_000),
    (4, "2026-06-30", 200_000),
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
        connection.executemany(
            """
            INSERT INTO sales_history (partner_id, sale_date, quantity)
            VALUES (?, ?, ?)
            """,
            SALES,
        )


if __name__ == "__main__":
    create_demo_database()
    print(f"Демонстрационная база создана: {DATABASE_PATH}")
