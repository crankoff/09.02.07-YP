"""Проверки очистки данных и импорта в SQLite."""

from __future__ import annotations

import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from etl import DEFAULT_PARTNERS_PATH, DEFAULT_SALES_PATH, run_etl


class EtlTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.work_dir = Path(self.temp_dir.name)
        self.output_dir = self.work_dir / "output"
        self.database_path = self.work_dir / "etl.db"
        self.result = run_etl(
            DEFAULT_PARTNERS_PATH,
            DEFAULT_SALES_PATH,
            self.output_dir,
            self.database_path,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_expected_row_counts(self) -> None:
        self.assertEqual(self.result.database_counts, {"partners": 3, "products": 3, "sales": 4})

    def test_partner_values_are_normalized(self) -> None:
        first = self.result.partners[0]
        second = self.result.partners[1]
        third = self.result.partners[2]
        self.assertEqual(first.company_name, 'ООО "Логистик-Экспресс"')
        self.assertEqual(first.phone, "+7 999 111-22-33")
        self.assertIsNone(second.phone)
        self.assertEqual(third.phone, "+7 812 555-44-33")
        self.assertIsNone(third.rating)

    def test_date_is_normalized(self) -> None:
        sale = next(sale for sale in self.result.sales if sale.sale_id == 102)
        self.assertEqual(sale.sale_date, "2026-03-15")
        self.assertEqual(sale.total_amount, "18000.50")

    def test_unknown_partner_is_rejected(self) -> None:
        self.assertEqual(len(self.result.rejected_rows), 1)
        rejected = self.result.rejected_rows[0]
        self.assertEqual(rejected.record_id, "104")
        self.assertIn("partner_id=4", rejected.reason)

    def test_clean_files_match_imported_rows(self) -> None:
        with (self.output_dir / "clean_partners.csv").open(encoding="utf-8") as source:
            partners_count = sum(1 for _ in csv.DictReader(source))
        with (self.output_dir / "clean_sales.csv").open(encoding="utf-8") as source:
            sales_count = sum(1 for _ in csv.DictReader(source))
        self.assertEqual(partners_count, 3)
        self.assertEqual(sales_count, 4)

    def test_database_relations_are_valid(self) -> None:
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(connection.execute("PRAGMA foreign_key_check").fetchall(), [])
            joined_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM sales AS s
                JOIN partners AS p ON p.partner_id = s.partner_id
                JOIN products AS pr ON pr.product_id = s.product_id
                """
            ).fetchone()[0]
            self.assertEqual(joined_count, 4)

    def test_repeated_run_is_idempotent(self) -> None:
        second_result = run_etl(
            DEFAULT_PARTNERS_PATH,
            DEFAULT_SALES_PATH,
            self.output_dir,
            self.database_path,
        )
        self.assertEqual(second_result.database_counts, self.result.database_counts)


if __name__ == "__main__":
    unittest.main(verbosity=2)
