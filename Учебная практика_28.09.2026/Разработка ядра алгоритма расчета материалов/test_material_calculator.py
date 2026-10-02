from pathlib import Path
import tempfile
import unittest

from create_database import initialize_database
from material_calculator import MaterialCalculator


class MaterialCalculatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.db"
        initialize_database(self.database_path)
        self.calculator = MaterialCalculator(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_calculation_uses_product_coefficient_and_waste(self) -> None:
        result = self.calculator.calculate_material_amount(1, 1, 10, 2.5, 4.0)
        self.assertEqual(result, 111)

    def test_result_is_rounded_up(self) -> None:
        result = self.calculator.calculate_material_amount(2, 3, 7, 1.2, 3.5)
        self.assertEqual(result, 75)

    def test_exact_integer_is_not_increased(self) -> None:
        result = self.calculator.calculate_material_amount(4, 4, 2, 1.5, 2.0)
        self.assertEqual(result, 6)

    def test_unknown_product_type_returns_minus_one(self) -> None:
        result = self.calculator.calculate_material_amount(999, 1, 10, 2.0, 3.0)
        self.assertEqual(result, -1)

    def test_unknown_material_type_returns_minus_one(self) -> None:
        result = self.calculator.calculate_material_amount(1, 999, 10, 2.0, 3.0)
        self.assertEqual(result, -1)

    def test_non_positive_quantity_returns_minus_one(self) -> None:
        for quantity in (0, -1):
            with self.subTest(quantity=quantity):
                result = self.calculator.calculate_material_amount(
                    1, 1, quantity, 2.0, 3.0
                )
                self.assertEqual(result, -1)

    def test_non_positive_parameters_return_minus_one(self) -> None:
        invalid_parameters = ((0.0, 3.0), (-2.0, 3.0), (2.0, 0.0), (2.0, -3.0))
        for param_1, param_2 in invalid_parameters:
            with self.subTest(param_1=param_1, param_2=param_2):
                result = self.calculator.calculate_material_amount(
                    1, 1, 10, param_1, param_2
                )
                self.assertEqual(result, -1)

    def test_non_finite_parameters_return_minus_one(self) -> None:
        for invalid_value in (float("inf"), float("-inf"), float("nan")):
            with self.subTest(value=invalid_value):
                result = self.calculator.calculate_material_amount(
                    1, 1, 10, invalid_value, 3.0
                )
                self.assertEqual(result, -1)

    def test_invalid_types_return_minus_one(self) -> None:
        self.assertEqual(
            self.calculator.calculate_material_amount(True, 1, 10, 2.0, 3.0),
            -1,
        )
        self.assertEqual(
            self.calculator.calculate_material_amount(1, 1, 10.5, 2.0, 3.0),
            -1,
        )
        self.assertEqual(
            self.calculator.calculate_material_amount(1, 1, 10, "2.0", 3.0),
            -1,
        )

    def test_database_error_returns_minus_one(self) -> None:
        missing_database = Path(self.temporary_directory.name) / "missing.db"
        calculator = MaterialCalculator(missing_database)
        result = calculator.calculate_material_amount(1, 1, 10, 2.0, 3.0)
        self.assertEqual(result, -1)


if __name__ == "__main__":
    unittest.main()
