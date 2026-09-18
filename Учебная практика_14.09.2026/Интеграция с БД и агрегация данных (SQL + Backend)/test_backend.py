"""Тесты интеграции базы данных и расчёта скидки."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend import (
    PARTNER_SALES_QUERY,
    PartnerNotFoundError,
    connect_database,
    get_partner_sales_summary,
    get_partner_with_discount,
    get_partner_with_discount_from_database,
)
from create_database import create_demo_database


class BackendIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.db"
        create_demo_database(self.database_path)
        self.connection = connect_database(self.database_path)

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary_directory.cleanup()

    def test_query_contains_required_aggregation(self) -> None:
        normalized_query = " ".join(PARTNER_SALES_QUERY.upper().split())
        self.assertIn("LEFT JOIN SALES_HISTORY", normalized_query)
        self.assertIn("SUM(SH.QUANTITY)", normalized_query)
        self.assertIn("GROUP BY", normalized_query)

    def test_all_discount_levels_are_calculated_from_database(self) -> None:
        expected_results = {
            1: (9_999, 0),
            2: (49_999, 5),
            3: (299_999, 10),
            4: (300_000, 15),
        }
        for partner_id, expected in expected_results.items():
            with self.subTest(partner_id=partner_id):
                partner = get_partner_with_discount(self.connection, partner_id)
                self.assertEqual(
                    (partner["total_quantity"], partner["discount_percent"]),
                    expected,
                )

    def test_partner_without_sales_is_returned_by_left_join(self) -> None:
        partner = get_partner_sales_summary(self.connection, 5)
        self.assertEqual(partner["name"], "ИП Без продаж")
        self.assertEqual(partner["total_quantity"], 0)

    def test_backend_method_opens_database_and_returns_dictionary(self) -> None:
        partner = get_partner_with_discount_from_database(2, self.database_path)
        self.assertIsInstance(partner, dict)
        self.assertEqual(partner["partner_id"], 2)
        self.assertEqual(partner["discount_percent"], 5)

    def test_missing_partner_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(PartnerNotFoundError, "id=999"):
            get_partner_with_discount(self.connection, 999)

    def test_database_integrity(self) -> None:
        self.assertEqual(
            self.connection.execute("PRAGMA integrity_check").fetchone()[0],
            "ok",
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(),
            [],
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO sales_history (partner_id, sale_date, quantity)
                VALUES (999, '2026-09-18', 1)
                """
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
