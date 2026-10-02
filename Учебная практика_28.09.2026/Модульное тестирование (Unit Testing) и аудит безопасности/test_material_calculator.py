from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from create_database import initialize_database
from logging_config import create_logger
from material_calculator import MaterialCalculator


class MaterialCalculatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        directory = Path(self.temporary_directory.name)
        self.database_path = directory / "test.db"
        self.log_path = directory / "test.log"
        initialize_database(self.database_path)
        logger = create_logger(self.log_path)
        self.calculator = MaterialCalculator(self.database_path, logger)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_standard_calculation(self) -> None:
        result = self.calculator.calculate_material_amount(1, 1, 10, 2.5, 4.0)
        self.assertEqual(result, 111)

    def test_fractional_result_is_rounded_up(self) -> None:
        result = self.calculator.calculate_material_amount(2, 3, 7, 1.2, 3.5)
        self.assertEqual(result, 75)

    def test_unknown_product_or_material_type_returns_minus_one(self) -> None:
        invalid_ids = ((999, 1), (1, 999))
        for product_type_id, material_type_id in invalid_ids:
            with self.subTest(
                product_type_id=product_type_id,
                material_type_id=material_type_id,
            ):
                result = self.calculator.calculate_material_amount(
                    product_type_id,
                    material_type_id,
                    10,
                    2.5,
                    4.0,
                )
                self.assertEqual(result, -1)

    def test_negative_parameters_return_minus_one(self) -> None:
        invalid_parameters = ((-1.0, 4.0), (2.5, -1.0))
        for param_1, param_2 in invalid_parameters:
            with self.subTest(param_1=param_1, param_2=param_2):
                result = self.calculator.calculate_material_amount(
                    1,
                    1,
                    10,
                    param_1,
                    param_2,
                )
                self.assertEqual(result, -1)

    def test_zero_or_negative_quantity_returns_minus_one(self) -> None:
        for quantity in (0, -1):
            with self.subTest(quantity=quantity):
                result = self.calculator.calculate_material_amount(
                    1,
                    1,
                    quantity,
                    2.5,
                    4.0,
                )
                self.assertEqual(result, -1)

    def test_exact_integer_is_not_increased(self) -> None:
        result = self.calculator.calculate_material_amount(4, 4, 2, 1.5, 2.0)
        self.assertEqual(result, 6)


if __name__ == "__main__":
    unittest.main()
