"""Unit-тесты функции расчёта скидки."""

import unittest

from discount import calculate_partner_discount


class CalculatePartnerDiscountTests(unittest.TestCase):
    def test_discount_boundaries(self) -> None:
        test_cases = (
            (0, 0),
            (9_999, 0),
            (10_000, 5),
            (49_999, 5),
            (50_000, 10),
            (299_999, 10),
            (300_000, 15),
            (1_000_000, 15),
        )
        for total_quantity, expected_discount in test_cases:
            with self.subTest(total_quantity=total_quantity):
                self.assertEqual(
                    calculate_partner_discount(total_quantity),
                    expected_discount,
                )

    def test_negative_quantity_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "не может быть отрицательным"):
            calculate_partner_discount(-1)

    def test_non_integer_quantity_is_rejected(self) -> None:
        invalid_values = (10_000.0, "10000", None, True)
        for invalid_value in invalid_values:
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaisesRegex(TypeError, "должен быть целым числом"):
                    calculate_partner_discount(invalid_value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
