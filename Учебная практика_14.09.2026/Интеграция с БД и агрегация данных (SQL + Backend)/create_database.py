"""Создание демонстрационной SQLite-базы с вымышленными данными."""

from __future__ import annotations

from pathlib import Path

from backend import DATABASE_PATH, connect_database, initialize_database


PARTNERS = (
    (1, "ООО Малый партнёр", "7701000001", "small@example.com"),
    (2, "ООО Средний партнёр", "7701000002", "medium@example.com"),
    (3, "ООО Крупный партнёр", "7701000003", "large@example.com"),
    (4, "АО Стратегический партнёр", "7701000004", "strategic@example.com"),
    (5, "ИП Без продаж", "770100000005", "empty@example.com"),
)

SALES = (
    (1, "2026-01-15", 4_000),
    (1, "2026-02-15", 5_999),
    (2, "2026-01-20", 10_000),
    (2, "2026-02-20", 39_999),
    (3, "2026-03-10", 50_000),
    (3, "2026-04-10", 249_999),
    (4, "2026-05-01", 300_000),
)


def create_demo_database(database_path: str | Path = DATABASE_PATH) -> Path:
    """Пересоздаёт БД и заполняет её тестовыми партнёрами и продажами."""
    path = Path(database_path)
    with connect_database(path) as connection:
        initialize_database(connection)
        connection.executemany(
            "INSERT INTO partners (partner_id, name, inn, email) VALUES (?, ?, ?, ?)",
            PARTNERS,
        )
        connection.executemany(
            """
            INSERT INTO sales_history (partner_id, sale_date, quantity)
            VALUES (?, ?, ?)
            """,
            SALES,
        )
    return path


def main() -> None:
    database_path = create_demo_database()
    print(f"Тестовая база данных создана: {database_path}")


if __name__ == "__main__":
    main()
