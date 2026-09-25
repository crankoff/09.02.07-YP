from __future__ import annotations

from pathlib import Path

from database import DATABASE_PATH, Partner, PartnerRepository, initialize_database


DEMO_PARTNERS = [
    Partner(None, "ООО", "Альфа Снаб", "Соколов Артём Ильич", "+7 900 111-22-33", "info@alpha-snab.example", 8),
    Partner(None, "ИП", "Вектор", "Крылова Елена Олеговна", "+7 900 222-33-44", "office@vector.example", 7),
    Partner(None, "АО", "Городские решения", "Петров Максим Сергеевич", "+7 900 333-44-55", "mail@city-solutions.example", 10),
]


def create_demo_database(database_path: str | Path = DATABASE_PATH) -> None:
    initialize_database(database_path, reset=True)
    repository = PartnerRepository(database_path)
    for partner in DEMO_PARTNERS:
        repository.save(partner)


if __name__ == "__main__":
    create_demo_database()
    print(f"Демонстрационная база создана: {DATABASE_PATH}")
