from __future__ import annotations

from pathlib import Path

from database import (
    DATABASE_PATH,
    Partner,
    PartnerRepository,
    connect_database,
    initialize_database,
)


DEMO_PARTNERS = [
    Partner(None, "ООО", "Альфа Снаб", "г. Москва, ул. Деловая, д. 12", "Соколов Артём Ильич", "+7 900 111-22-33", "info@alpha-snab.example", 8),
    Partner(None, "ИП", "Вектор", "г. Тула, пр-т Центральный, д. 7", "Крылова Елена Олеговна", "+7 900 222-33-44", "office@vector.example", 7),
    Partner(None, "ЗАО", "Городские решения", "г. Казань, ул. Проектная, д. 25", "Петров Максим Сергеевич", "+7 900 333-44-55", "mail@city-solutions.example", 10),
]

DEMO_SALES = [
    (1, "2026-03-12", 4_000),
    (1, "2026-06-21", 7_500),
    (2, "2026-05-05", 12_000),
]


def create_demo_database(database_path: str | Path = DATABASE_PATH) -> None:
    initialize_database(database_path, reset=True)
    repository = PartnerRepository(database_path)
    for partner in DEMO_PARTNERS:
        repository.save(partner)
    with connect_database(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO sales_history (partner_id, sale_date, quantity)
            VALUES (?, ?, ?)
            """,
            DEMO_SALES,
        )


if __name__ == "__main__":
    create_demo_database()
    print(f"Демонстрационная база создана: {DATABASE_PATH}")
