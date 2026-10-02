from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING
from pathlib import Path
import sqlite3


class MaterialCalculator:
    """Рассчитывает необходимое целое количество материала."""

    def __init__(self, database_path: Path | str) -> None:
        self.database_path = Path(database_path)

    def calculate_material_amount(
        self,
        product_type_id: int,
        material_type_id: int,
        quantity: int,
        param_1: float,
        param_2: float,
    ) -> int:
        if not self._valid_integer(product_type_id):
            return -1
        if not self._valid_integer(material_type_id):
            return -1
        if not self._valid_integer(quantity):
            return -1
        if not self._valid_parameter(param_1):
            return -1
        if not self._valid_parameter(param_2):
            return -1

        try:
            product_coefficient = self._get_reference_value(
                "product_types",
                "product_type_id",
                "coefficient",
                product_type_id,
            )
            waste_percent = self._get_reference_value(
                "material_types",
                "material_type_id",
                "waste_percent",
                material_type_id,
            )
            if product_coefficient is None or waste_percent is None:
                return -1

            base_amount = (
                Decimal(str(param_1))
                * Decimal(str(param_2))
                * product_coefficient
            )
            clean_amount = base_amount * Decimal(quantity)
            final_amount = clean_amount * (
                Decimal("1") + waste_percent / Decimal("100")
            )
            return int(final_amount.to_integral_value(rounding=ROUND_CEILING))
        except (InvalidOperation, OSError, sqlite3.Error, ValueError):
            return -1

    def _get_reference_value(
        self,
        table: str,
        id_column: str,
        value_column: str,
        reference_id: int,
    ) -> Decimal | None:
        allowed_references = {
            ("product_types", "product_type_id", "coefficient"),
            ("material_types", "material_type_id", "waste_percent"),
        }
        if (table, id_column, value_column) not in allowed_references:
            raise ValueError("Неизвестный справочник")

        query = (
            f"SELECT {value_column} FROM {table} "
            f"WHERE {id_column} = ?"
        )
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute(query, (reference_id,)).fetchone()
        return Decimal(str(row[0])) if row is not None else None

    @staticmethod
    def _valid_integer(value: object) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    @staticmethod
    def _valid_parameter(value: object) -> bool:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False
        try:
            decimal_value = Decimal(str(value))
            return decimal_value.is_finite() and decimal_value > 0
        except (InvalidOperation, ValueError):
            return False
