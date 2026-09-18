"""Интеграция SQLite с функцией расчёта скидки партнёра."""

from __future__ import annotations

import importlib.util
import sqlite3
from collections.abc import Callable
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = PROJECT_DIR / "practice.db"
SCHEMA_PATH = PROJECT_DIR / "schema.sql"
DISCOUNT_MODULE_PATH = (
    PROJECT_DIR.parent
    / "Разработка ядра бизнес-логики (Расчет скидки)"
    / "discount.py"
)

PARTNER_SALES_QUERY = """
SELECT
    p.partner_id,
    p.name,
    p.inn,
    p.email,
    COALESCE(SUM(sh.quantity), 0) AS total_quantity
FROM partners AS p
LEFT JOIN sales_history AS sh
    ON sh.partner_id = p.partner_id
WHERE p.partner_id = ?
GROUP BY p.partner_id, p.name, p.inn, p.email;
"""


class PartnerNotFoundError(LookupError):
    """Партнёр с указанным идентификатором не найден."""


def load_discount_function() -> Callable[[int], int]:
    """Загружает функцию из решения предыдущего подзадания."""
    module_spec = importlib.util.spec_from_file_location(
        "partner_discount",
        DISCOUNT_MODULE_PATH,
    )
    if module_spec is None or module_spec.loader is None:
        raise ImportError("Не удалось загрузить функцию расчёта скидки")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module.calculate_partner_discount


calculate_partner_discount = load_discount_function()


def connect_database(database_path: str | Path = DATABASE_PATH) -> sqlite3.Connection:
    """Открывает соединение с SQLite и включает контроль внешних ключей."""
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(connection: sqlite3.Connection) -> None:
    """Создаёт таблицы базы данных по schema.sql."""
    connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def get_partner_sales_summary(
    connection: sqlite3.Connection,
    partner_id: int,
) -> dict[str, object]:
    """Возвращает партнёра и суммарный объём его продаж."""
    row = connection.execute(PARTNER_SALES_QUERY, (partner_id,)).fetchone()
    if row is None:
        raise PartnerNotFoundError(f"Партнёр с id={partner_id} не найден")
    return dict(row)


def get_partner_with_discount(
    connection: sqlite3.Connection,
    partner_id: int,
) -> dict[str, object]:
    """Дополняет данные партнёра текущим процентом скидки."""
    partner = get_partner_sales_summary(connection, partner_id)
    total_quantity = int(partner["total_quantity"])
    partner["discount_percent"] = calculate_partner_discount(total_quantity)
    return partner


def get_partner_with_discount_from_database(
    partner_id: int,
    database_path: str | Path = DATABASE_PATH,
) -> dict[str, object]:
    """Эмулирует метод бэкенда, самостоятельно подключающийся к БД."""
    with connect_database(database_path) as connection:
        return get_partner_with_discount(connection, partner_id)
