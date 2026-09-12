"""Автоматическая проверка DDL-скрипта schema.sql."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path


SCHEMA_PATH = Path(__file__).with_name("schema.sql")
EXPECTED_TABLES = {"partners", "products", "deliveries", "delivery_items"}


def expect_integrity_error(action, message: str) -> None:
    """Проверяет, что операция блокируется ограничением целостности."""
    try:
        action()
    except sqlite3.IntegrityError:
        return
    raise AssertionError(message)


def deploy_schema(connection: sqlite3.Connection) -> None:
    """Разворачивает DDL из файла и проверяет включение внешних ключей."""
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    enabled = connection.execute("PRAGMA foreign_keys").fetchone()[0]
    if enabled != 1:
        raise AssertionError("Проверка внешних ключей не включена")


def check_structure(connection: sqlite3.Connection) -> None:
    """Проверяет таблицы, первичные и внешние ключи."""
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    if tables != EXPECTED_TABLES:
        raise AssertionError(f"Неверный набор таблиц: {sorted(tables)}")

    expected_primary_keys = {
        "partners": {"partner_id"},
        "products": {"product_id"},
        "deliveries": {"delivery_id"},
        "delivery_items": {"delivery_id", "product_id"},
    }
    for table, expected_columns in expected_primary_keys.items():
        actual_columns = {
            row[1]
            for row in connection.execute(f"PRAGMA table_info({table})")
            if row[5] > 0
        }
        if actual_columns != expected_columns:
            raise AssertionError(f"Неверный PRIMARY KEY таблицы {table}: {actual_columns}")

    deliveries_fk = connection.execute("PRAGMA foreign_key_list(deliveries)").fetchall()
    if not any(row[2] == "partners" and row[6] == "RESTRICT" for row in deliveries_fk):
        raise AssertionError("Не найден FOREIGN KEY deliveries -> partners ON DELETE RESTRICT")

    items_fk = connection.execute("PRAGMA foreign_key_list(delivery_items)").fetchall()
    if not any(row[2] == "deliveries" and row[6] == "CASCADE" for row in items_fk):
        raise AssertionError("Не найден FOREIGN KEY delivery_items -> deliveries ON DELETE CASCADE")
    if not any(row[2] == "products" and row[6] == "RESTRICT" for row in items_fk):
        raise AssertionError("Не найден FOREIGN KEY delivery_items -> products ON DELETE RESTRICT")


def check_constraints(connection: sqlite3.Connection) -> None:
    """Проверяет ограничения на реальных операциях INSERT и DELETE."""
    partner_id = connection.execute(
        """
        INSERT INTO partners(name, inn, email, phone)
        VALUES ('ООО Тестовый партнёр', '7701234567', 'test@partner.example', '+7 495 111-22-33')
        """
    ).lastrowid
    product_id = connection.execute(
        """
        INSERT INTO products(sku, name, unit, price)
        VALUES ('TEST-001', 'Тестовый товар', 'шт.', 1250.50)
        """
    ).lastrowid
    delivery_id = connection.execute(
        """
        INSERT INTO deliveries(partner_id, delivery_number, delivery_date, status)
        VALUES (?, 'TEST-DEL-001', '2026-09-12', 'shipped')
        """,
        (partner_id,),
    ).lastrowid
    connection.execute(
        """
        INSERT INTO delivery_items(delivery_id, product_id, quantity, unit_price)
        VALUES (?, ?, 3, 1200.00)
        """,
        (delivery_id, product_id),
    )
    connection.commit()

    expect_integrity_error(
        lambda: connection.execute(
            "INSERT INTO partners(name, inn, email) VALUES ('Дубликат', '7701234567', 'other@example.com')"
        ),
        "Ограничение UNIQUE для ИНН не сработало",
    )
    connection.rollback()

    expect_integrity_error(
        lambda: connection.execute(
            "INSERT INTO products(sku, name, unit, price) VALUES ('BAD', 'Ошибка', 'шт.', -1)"
        ),
        "Ограничение CHECK для цены не сработало",
    )
    connection.rollback()

    expect_integrity_error(
        lambda: connection.execute("DELETE FROM partners WHERE partner_id = ?", (partner_id,)),
        "ON DELETE RESTRICT для партнёра не сработал",
    )
    connection.rollback()

    connection.execute("DELETE FROM deliveries WHERE delivery_id = ?", (delivery_id,))
    remaining_items = connection.execute(
        "SELECT COUNT(*) FROM delivery_items WHERE delivery_id = ?", (delivery_id,)
    ).fetchone()[0]
    if remaining_items != 0:
        raise AssertionError("ON DELETE CASCADE не удалил позиции отгрузки")


def check_repeatable_deployment(connection: sqlite3.Connection) -> None:
    """Повторно запускает schema.sql и подтверждает правильный порядок DROP."""
    deploy_schema(connection)
    check_structure(connection)


def main() -> None:
    if not SCHEMA_PATH.exists():
        raise SystemExit(f"Не найден файл: {SCHEMA_PATH}")

    ddl = SCHEMA_PATH.read_text(encoding="utf-8").upper()
    if ddl.count("DROP TABLE IF EXISTS") != 4:
        raise AssertionError("Для каждой таблицы требуется DROP TABLE IF EXISTS")
    if ddl.count("CREATE TABLE") != 4:
        raise AssertionError("Ожидалось четыре команды CREATE TABLE")

    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "schema_check.db"
        with sqlite3.connect(database_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            deploy_schema(connection)
            check_structure(connection)
            check_constraints(connection)
            check_repeatable_deployment(connection)

    print("schema.sql успешно проверен.")
    print("Таблицы: partners, products, deliveries, delivery_items.")
    print("Проверены PRIMARY KEY, UNIQUE, CHECK и FOREIGN KEY RESTRICT/CASCADE.")
    print("Повторный запуск DDL выполняется без ошибок.")


if __name__ == "__main__":
    main()
