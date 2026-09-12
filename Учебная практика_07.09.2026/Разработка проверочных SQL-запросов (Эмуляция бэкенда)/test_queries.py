"""Автоматические проверки файла queries.sql."""

from __future__ import annotations

import sqlite3
import unittest

from demo_queries import (
    DEMO_PARAMETERS,
    create_demo_database,
    execute_select,
    execute_transaction,
)


class QueriesTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = create_demo_database()

    def tearDown(self) -> None:
        self.connection.close()

    def test_partner_list_uses_left_join_semantics(self) -> None:
        rows = execute_select(self.connection, 1)
        counts = {row["partner_name"]: row["delivery_count"] for row in rows}

        self.assertEqual(counts["ООО Альфа"], 2)
        self.assertEqual(counts["АО Север"], 1)
        self.assertEqual(counts["ИП Маяк"], 0)
        self.assertEqual(
            [row["partner_name"] for row in rows],
            sorted(row["partner_name"] for row in rows),
        )

    def test_transaction_creates_partner_and_first_delivery(self) -> None:
        execute_transaction(self.connection, DEMO_PARAMETERS)

        partner_count = self.connection.execute(
            "SELECT COUNT(*) FROM partners WHERE inn = :partner_inn",
            DEMO_PARAMETERS,
        ).fetchone()[0]
        delivery_count = self.connection.execute(
            "SELECT COUNT(*) FROM deliveries WHERE delivery_number = :delivery_number",
            DEMO_PARAMETERS,
        ).fetchone()[0]
        item_count = self.connection.execute(
            """
            SELECT COUNT(*)
            FROM delivery_items AS di
            JOIN deliveries AS d ON d.delivery_id = di.delivery_id
            WHERE d.delivery_number = :delivery_number
            """,
            DEMO_PARAMETERS,
        ).fetchone()[0]

        self.assertEqual((partner_count, delivery_count, item_count), (1, 1, 1))

    def test_transaction_is_idempotent_and_updates_data(self) -> None:
        execute_transaction(self.connection, DEMO_PARAMETERS)
        updated = {**DEMO_PARAMETERS, "partner_name": "ООО Вектор Обновлённый"}
        execute_transaction(self.connection, updated)

        partner = self.connection.execute(
            "SELECT name FROM partners WHERE inn = :partner_inn",
            DEMO_PARAMETERS,
        ).fetchone()
        delivery_count = self.connection.execute(
            "SELECT COUNT(*) FROM deliveries WHERE delivery_number = :delivery_number",
            DEMO_PARAMETERS,
        ).fetchone()[0]

        self.assertEqual(partner["name"], "ООО Вектор Обновлённый")
        self.assertEqual(delivery_count, 1)

    def test_failed_transaction_is_rolled_back(self) -> None:
        invalid = {
            **DEMO_PARAMETERS,
            "partner_inn": "5001234567",
            "partner_email": "rollback@example.com",
            "delivery_number": "ROLLBACK-001",
            "quantity": 0,
        }

        with self.assertRaises(sqlite3.IntegrityError):
            execute_transaction(self.connection, invalid)

        partner_count = self.connection.execute(
            "SELECT COUNT(*) FROM partners WHERE inn = :partner_inn",
            invalid,
        ).fetchone()[0]
        delivery_count = self.connection.execute(
            "SELECT COUNT(*) FROM deliveries WHERE delivery_number = :delivery_number",
            invalid,
        ).fetchone()[0]
        self.assertEqual((partner_count, delivery_count), (0, 0))

    def test_history_contains_details_and_delivery_total(self) -> None:
        execute_transaction(self.connection, DEMO_PARAMETERS)
        rows = execute_select(self.connection, 3, DEMO_PARAMETERS)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["product_name"], "Тестовый комплект")
        self.assertEqual(rows[0]["quantity"], 5)
        self.assertEqual(rows[0]["line_total"], 7500.0)
        self.assertEqual(rows[0]["delivery_total"], 7500.0)

        outside_period = {
            **DEMO_PARAMETERS,
            "date_from": "2026-10-01",
            "date_to": "2026-10-31",
        }
        self.assertEqual(execute_select(self.connection, 3, outside_period), [])

    def test_database_integrity_after_queries(self) -> None:
        execute_transaction(self.connection, DEMO_PARAMETERS)
        self.assertEqual(
            self.connection.execute("PRAGMA integrity_check").fetchone()[0],
            "ok",
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(),
            [],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
