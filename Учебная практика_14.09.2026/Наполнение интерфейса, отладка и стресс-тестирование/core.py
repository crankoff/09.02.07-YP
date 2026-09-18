from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "practice.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"

PARTNER_LIST_QUERY = """
SELECT
    p.partner_id,
    p.partner_type,
    p.name,
    p.director,
    p.phone,
    p.email,
    p.rating,
    COALESCE(SUM(sh.quantity), 0) AS total_quantity
FROM partners AS p
LEFT JOIN sales_history AS sh ON sh.partner_id = p.partner_id
GROUP BY
    p.partner_id,
    p.partner_type,
    p.name,
    p.director,
    p.phone,
    p.email,
    p.rating
ORDER BY p.name;
"""


@dataclass(frozen=True)
class PartnerCard:
    partner_id: int
    partner_type: str
    name: str
    director: str
    phone: str
    email: str
    rating: int
    total_quantity: int
    discount: int

    def to_dict(self) -> dict[str, int | str]:
        return asdict(self)


def calculate_partner_discount(total_quantity: int) -> int:
    if isinstance(total_quantity, bool) or not isinstance(total_quantity, int):
        raise TypeError("Общий объем должен быть целым числом")
    if total_quantity < 0:
        raise ValueError("Общий объем не может быть отрицательным")
    if total_quantity < 10_000:
        return 0
    if total_quantity < 50_000:
        return 5
    if total_quantity < 300_000:
        return 10
    return 15


def connect_database(database_path: str | Path = DATABASE_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
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


def get_partner_cards(
    database_path: str | Path = DATABASE_PATH,
) -> list[PartnerCard]:
    with connect_database(database_path) as connection:
        rows = connection.execute(PARTNER_LIST_QUERY).fetchall()

    cards = []
    for row in rows:
        total_quantity = int(row["total_quantity"] or 0)
        cards.append(
            PartnerCard(
                partner_id=row["partner_id"],
                partner_type=row["partner_type"],
                name=row["name"],
                director=row["director"],
                phone=row["phone"],
                email=row["email"],
                rating=row["rating"],
                total_quantity=total_quantity,
                discount=calculate_partner_discount(total_quantity),
            )
        )
    return cards
