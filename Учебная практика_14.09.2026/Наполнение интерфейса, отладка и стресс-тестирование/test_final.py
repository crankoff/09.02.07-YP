import json
from pathlib import Path
import sqlite3
import tempfile
from threading import Thread
import unittest
from urllib.request import urlopen

from app import create_server, render_page
from core import (
    PARTNER_LIST_QUERY,
    calculate_partner_discount,
    connect_database,
    get_partner_cards,
)
from create_database import create_demo_database
from stress_test import run_stress_test


class FinalApplicationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.db"
        create_demo_database(self.database_path)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_all_discount_levels_are_calculated_from_database(self) -> None:
        cards = get_partner_cards(self.database_path)
        self.assertEqual([card.discount for card in cards], [0, 5, 10, 0, 15])
        self.assertEqual(sorted(card.discount for card in cards), [0, 0, 5, 10, 15])

    def test_discount_boundary_values(self) -> None:
        quantities = [9_999, 10_000, 49_999, 50_000, 300_000]
        discounts = [calculate_partner_discount(value) for value in quantities]
        self.assertEqual(discounts, [0, 5, 5, 10, 15])

    def test_partner_without_sales_has_zero_quantity_and_discount(self) -> None:
        partner = next(
            card
            for card in get_partner_cards(self.database_path)
            if card.name == "Новый партнёр"
        )
        self.assertEqual(partner.total_quantity, 0)
        self.assertEqual(partner.discount, 0)

    def test_aggregation_query_meets_task_requirements(self) -> None:
        normalized_query = " ".join(PARTNER_LIST_QUERY.upper().split())
        self.assertIn("LEFT JOIN SALES_HISTORY", normalized_query)
        self.assertIn("COALESCE(SUM(SH.QUANTITY), 0)", normalized_query)
        self.assertIn("GROUP BY", normalized_query)

    def test_page_contains_database_data_without_none_values(self) -> None:
        page = render_page(get_partner_cards(self.database_path))
        self.assertEqual(page.count('class="partner-card"'), 5)
        self.assertIn("Новый партнёр", page)
        self.assertIn("0%", page)
        self.assertNotIn(">None<", page)

    def test_http_interface_and_api(self) -> None:
        server = create_server(port=0, database_path=self.database_path)
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        base_url = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(f"{base_url}/", timeout=5) as response:
                page = response.read().decode("utf-8")
            with urlopen(f"{base_url}/api/partners", timeout=5) as response:
                partners = json.loads(response.read().decode("utf-8"))
            with urlopen(f"{base_url}/health", timeout=5) as response:
                health = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)
        self.assertIn("Партнёры и скидки", page)
        self.assertEqual(len(partners), 5)
        self.assertEqual(health, {"status": "ok"})

    def test_database_constraints_are_active(self) -> None:
        with connect_database(self.database_path) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO sales_history (partner_id, sale_date, quantity)
                    VALUES (9999, '2026-09-18', 100)
                    """
                )

    def test_small_stress_scenario(self) -> None:
        result = run_stress_test(
            partner_count=50,
            sales_per_partner=4,
            request_count=12,
            workers=4,
        )
        self.assertEqual(result["partners"], 50)
        self.assertEqual(result["sales"], 200)
        self.assertEqual(result["requests"], 12)


if __name__ == "__main__":
    unittest.main(verbosity=2)
