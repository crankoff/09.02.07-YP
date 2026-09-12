"""Автоматические проверки ограничений и основных сценариев задания."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from main import (
    connect_database,
    get_delivery_history,
    init_database,
    list_partners,
    seed_demo_data,
    update_partner,
)


class DatabaseTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.connection = connect_database(self.db_path)
        init_database(self.connection)
        seed_demo_data(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp_dir.cleanup()

    def test_demo_data_and_history(self) -> None:
        partners = list_partners(self.connection)
        self.assertEqual(len(partners), 6)

        alpha_id = next(row["id"] for row in partners if row["inn"] == "7701234567")
        history = get_delivery_history(self.connection, alpha_id)
        self.assertEqual(len(history), 5)
        self.assertEqual(history[0]["delivery_number"], "DEL-2026-002")

    def test_partner_can_be_updated(self) -> None:
        partner_id = list_partners(self.connection)[0]["id"]
        self.assertTrue(update_partner(self.connection, partner_id, phone="+7 999 123-45-67"))
        phone = self.connection.execute(
            "SELECT phone FROM partners WHERE id = ?", (partner_id,)
        ).fetchone()["phone"]
        self.assertEqual(phone, "+7 999 123-45-67")

    def test_inn_is_unique(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                "INSERT INTO partners(name, inn, email) VALUES (?, ?, ?)",
                ("Дубликат", "7701234567", "duplicate@example.com"),
            )

    def test_foreign_key_is_checked(self) -> None:
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT INTO deliveries(partner_id, delivery_number, delivery_date)
                VALUES (?, ?, ?)
                """,
                (9999, "DEL-INVALID", "2026-09-12"),
            )

    def test_quantity_must_be_positive(self) -> None:
        delivery_id = self.connection.execute("SELECT id FROM deliveries LIMIT 1").fetchone()["id"]
        product_id = self.connection.execute("SELECT id FROM products LIMIT 1").fetchone()["id"]
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute(
                """
                INSERT OR REPLACE INTO delivery_items(
                    delivery_id, product_id, quantity, unit_price
                ) VALUES (?, ?, ?, ?)
                """,
                (delivery_id, product_id, 0, 100),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
