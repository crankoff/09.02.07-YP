"""Запуск трёх SQL-запросов на тестовой SQLite-базе."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Mapping


PROJECT_DIR = Path(__file__).resolve().parent
QUERIES_PATH = PROJECT_DIR / "queries.sql"
SCHEMA_PATH = (
    PROJECT_DIR.parent
    / "Написание DDL-скрипта (База данных в коде)"
    / "schema.sql"
)

SEED_SQL = """
INSERT INTO partners (name, inn, email, phone, address) VALUES
    ('АО Север', '7812345678', 'info@sever.example', '+7 812 555-10-10', 'Санкт-Петербург'),
    ('ИП Маяк', '770112345678', 'mail@mayak.example', NULL, 'Москва'),
    ('ООО Альфа', '5401234567', 'sales@alfa.example', '+7 383 555-20-20', 'Новосибирск');

INSERT INTO products (sku, name, unit, price) VALUES
    ('PRD-001', 'Кабель силовой', 'шт.', 820.00),
    ('PRD-002', 'Распределительный щит', 'шт.', 12400.00);

INSERT INTO deliveries (
    partner_id, delivery_number, delivery_date, status
) VALUES
    ((SELECT partner_id FROM partners WHERE inn = '5401234567'), 'DLV-001', '2026-08-15', 'delivered'),
    ((SELECT partner_id FROM partners WHERE inn = '5401234567'), 'DLV-002', '2026-09-02', 'shipped'),
    ((SELECT partner_id FROM partners WHERE inn = '7812345678'), 'DLV-003', '2026-09-05', 'delivered');

INSERT INTO delivery_items (delivery_id, product_id, quantity, unit_price) VALUES
    ((SELECT delivery_id FROM deliveries WHERE delivery_number = 'DLV-001'),
     (SELECT product_id FROM products WHERE sku = 'PRD-001'), 10, 800.00),
    ((SELECT delivery_id FROM deliveries WHERE delivery_number = 'DLV-002'),
     (SELECT product_id FROM products WHERE sku = 'PRD-002'), 2, 12000.00),
    ((SELECT delivery_id FROM deliveries WHERE delivery_number = 'DLV-003'),
     (SELECT product_id FROM products WHERE sku = 'PRD-001'), 5, 810.00);
"""

DEMO_PARAMETERS: dict[str, object] = {
    "partner_name": "ООО Вектор Тест",
    "partner_inn": "7701234567",
    "partner_email": "delivery@vector.example",
    "partner_phone": "+7 495 555-01-20",
    "partner_address": "Москва, Тестовая улица, 10",
    "product_sku": "TEST-001",
    "product_name": "Тестовый комплект",
    "product_unit": "шт.",
    "product_price": 1500.00,
    "delivery_number": "TEST-2026-001",
    "delivery_date": "2026-09-10",
    "delivery_status": "delivered",
    "quantity": 5,
    "date_from": "2026-09-01",
    "date_to": "2026-09-30",
}


def load_query_section(number: int) -> str:
    """Возвращает один отмеченный блок из queries.sql."""
    sql = QUERIES_PATH.read_text(encoding="utf-8")
    start_marker = f"-- QUERY_{number}_BEGIN"
    end_marker = f"-- QUERY_{number}_END"
    if start_marker not in sql or end_marker not in sql:
        raise ValueError(f"В queries.sql отсутствуют маркеры запроса {number}")
    return sql.split(start_marker, 1)[1].split(end_marker, 1)[0].strip()


def split_sql_statements(script: str) -> list[str]:
    """Разделяет SQL-блок на законченные выражения SQLite."""
    statements: list[str] = []
    buffer = ""
    for line in script.splitlines():
        buffer += line + "\n"
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if statement:
                statements.append(statement)
            buffer = ""
    if buffer.strip():
        raise ValueError("Обнаружено незавершённое SQL-выражение")
    return statements


def create_demo_database() -> sqlite3.Connection:
    """Создаёт тестовую БД по DDL-скрипту предыдущего задания."""
    connection = sqlite3.connect(":memory:", isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    connection.executescript(SEED_SQL)
    return connection


def execute_select(
    connection: sqlite3.Connection,
    query_number: int,
    parameters: Mapping[str, object] | None = None,
) -> list[sqlite3.Row]:
    query = load_query_section(query_number)
    return connection.execute(query, parameters or {}).fetchall()


def execute_transaction(
    connection: sqlite3.Connection,
    parameters: Mapping[str, object],
) -> None:
    """Исполняет второй блок и откатывает его целиком при любой ошибке."""
    statements = split_sql_statements(load_query_section(2))
    try:
        for statement in statements:
            connection.execute(statement, parameters)
    except Exception:
        if connection.in_transaction:
            connection.rollback()
        raise


def format_table(rows: Iterable[sqlite3.Row]) -> str:
    rows = list(rows)
    if not rows:
        return "Нет данных"

    headers = list(rows[0].keys())
    values = [["" if row[key] is None else str(row[key]) for key in headers] for row in rows]
    widths = [
        max(len(headers[index]), *(len(row[index]) for row in values))
        for index in range(len(headers))
    ]

    def render(row: list[str]) -> str:
        return " | ".join(value.ljust(widths[index]) for index, value in enumerate(row))

    separator = "-+-".join("-" * width for width in widths)
    return "\n".join([render(headers), separator, *(render(row) for row in values)])


def main() -> None:
    with create_demo_database() as connection:
        print("1. Список партнёров до тестовой транзакции")
        print(format_table(execute_select(connection, 1)))

        execute_transaction(connection, DEMO_PARAMETERS)
        print("\n2. Транзакция выполнена: партнёр и первая доставка сохранены")

        print("\n3. История доставок тестового партнёра за сентябрь 2026 года")
        print(format_table(execute_select(connection, 3, DEMO_PARAMETERS)))

        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        print(f"\nПроверка целостности: {integrity}")
        print(f"Ошибки внешних ключей: {len(foreign_key_errors)}")


if __name__ == "__main__":
    main()
