from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "sales.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

HISTORY_QUERY = """
SELECT
    pr.name AS product_name,
    sh.quantity,
    strftime('%d.%m.%Y', sh.sale_date) AS sale_date
FROM sales_history AS sh
JOIN partners AS p ON p.partner_id = sh.partner_id
JOIN products AS pr ON pr.product_id = sh.product_id
WHERE p.partner_id = ?
ORDER BY sh.sale_date DESC, sh.sale_id DESC;
"""


@dataclass(frozen=True)
class Partner:
    partner_id: int
    partner_type: str
    name: str
    director: str
    phone: str
    email: str
    rating: int


@dataclass(frozen=True)
class HistoryRow:
    product_name: str
    quantity: int
    sale_date: str


def connect_database(database_path: str | Path = DATABASE_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(
    database_path: str | Path = DATABASE_PATH,
    reset: bool = False,
) -> None:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if reset and path.exists():
        path.unlink()
    with connect_database(path) as connection:
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


class SalesRepository:
    def __init__(self, database_path: str | Path = DATABASE_PATH) -> None:
        self.database_path = Path(database_path)

    def list_partners(self) -> list[Partner]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT partner_id, partner_type, name, director, phone, email, rating
                FROM partners
                ORDER BY name
                """
            ).fetchall()
        return [self._partner_from_row(row) for row in rows]

    def get_partner(self, partner_id: int) -> Partner | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT partner_id, partner_type, name, director, phone, email, rating
                FROM partners
                WHERE partner_id = ?
                """,
                (partner_id,),
            ).fetchone()
        return self._partner_from_row(row) if row else None

    def get_partner_history(self, partner_id: int) -> list[HistoryRow]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(HISTORY_QUERY, (partner_id,)).fetchall()
        return [
            HistoryRow(
                product_name=row["product_name"],
                quantity=row["quantity"],
                sale_date=row["sale_date"],
            )
            for row in rows
        ]

    @staticmethod
    def _partner_from_row(row: sqlite3.Row) -> Partner:
        return Partner(
            partner_id=row["partner_id"],
            partner_type=row["partner_type"],
            name=row["name"],
            director=row["director"],
            phone=row["phone"],
            email=row["email"],
            rating=row["rating"],
        )
