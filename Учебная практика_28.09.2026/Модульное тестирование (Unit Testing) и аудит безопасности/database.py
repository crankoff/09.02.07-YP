from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


PRODUCT_TYPES_QUERY = """
    SELECT product_type_id, name, coefficient
    FROM product_types
    ORDER BY product_type_id
"""

MATERIAL_TYPES_QUERY = """
    SELECT material_type_id, name, waste_percent
    FROM material_types
    ORDER BY material_type_id
"""


@dataclass(frozen=True)
class CatalogItem:
    item_id: int
    name: str
    value: float


class CatalogRepository:
    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)

    def get_product_types(self) -> list[CatalogItem]:
        return self._fetch_catalog(PRODUCT_TYPES_QUERY)

    def get_material_types(self) -> list[CatalogItem]:
        return self._fetch_catalog(MATERIAL_TYPES_QUERY)

    def _fetch_catalog(self, query: str) -> list[CatalogItem]:
        with sqlite3.connect(self.database_path) as connection:
            rows = connection.execute(query).fetchall()
        return [CatalogItem(row[0], row[1], row[2]) for row in rows]
