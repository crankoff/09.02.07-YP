from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "partners.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


@dataclass(frozen=True)
class Partner:
    partner_id: int | None
    partner_type: str
    name: str
    address: str
    director: str
    phone: str
    email: str
    rating: int
    sales_count: int = 0


class ReferentialIntegrityError(Exception):
    pass


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


class PartnerRepository:
    def __init__(self, database_path: str | Path = DATABASE_PATH) -> None:
        self.database_path = Path(database_path)

    def list_all(self) -> list[Partner]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    p.partner_id,
                    p.partner_type,
                    p.name,
                    p.address,
                    p.director,
                    p.phone,
                    p.email,
                    p.rating,
                    COUNT(s.sale_id) AS sales_count
                FROM partners AS p
                LEFT JOIN sales_history AS s ON s.partner_id = p.partner_id
                GROUP BY
                    p.partner_id,
                    p.partner_type,
                    p.name,
                    p.address,
                    p.director,
                    p.phone,
                    p.email,
                    p.rating
                ORDER BY p.name
                """
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def get(self, partner_id: int) -> Partner | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT
                    p.partner_id,
                    p.partner_type,
                    p.name,
                    p.address,
                    p.director,
                    p.phone,
                    p.email,
                    p.rating,
                    COUNT(s.sale_id) AS sales_count
                FROM partners AS p
                LEFT JOIN sales_history AS s ON s.partner_id = p.partner_id
                WHERE p.partner_id = ?
                GROUP BY p.partner_id
                """,
                (partner_id,),
            ).fetchone()
        return self._from_row(row) if row else None

    def save(self, partner: Partner) -> int:
        with connect_database(self.database_path) as connection:
            if partner.partner_id is None:
                cursor = connection.execute(
                    """
                    INSERT INTO partners (
                        partner_type, name, address, director, phone, email, rating
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        partner.partner_type,
                        partner.name,
                        partner.address,
                        partner.director,
                        partner.phone,
                        partner.email,
                        partner.rating,
                    ),
                )
                return int(cursor.lastrowid)
            connection.execute(
                """
                UPDATE partners
                SET partner_type = ?, name = ?, address = ?, director = ?,
                    phone = ?, email = ?, rating = ?
                WHERE partner_id = ?
                """,
                (
                    partner.partner_type,
                    partner.name,
                    partner.address,
                    partner.director,
                    partner.phone,
                    partner.email,
                    partner.rating,
                    partner.partner_id,
                ),
            )
            return partner.partner_id

    def delete(self, partner_id: int) -> None:
        with connect_database(self.database_path) as connection:
            related_rows = connection.execute(
                "SELECT COUNT(*) FROM sales_history WHERE partner_id = ?",
                (partner_id,),
            ).fetchone()[0]
            if related_rows:
                raise ReferentialIntegrityError(
                    "Нельзя удалить партнёра: у него есть история продаж"
                )
            cursor = connection.execute(
                "DELETE FROM partners WHERE partner_id = ?",
                (partner_id,),
            )
            if cursor.rowcount == 0:
                raise KeyError("Партнёр не найден")

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Partner:
        return Partner(
            partner_id=row["partner_id"],
            partner_type=row["partner_type"],
            name=row["name"],
            address=row["address"],
            director=row["director"],
            phone=row["phone"],
            email=row["email"],
            rating=row["rating"],
            sales_count=row["sales_count"],
        )
