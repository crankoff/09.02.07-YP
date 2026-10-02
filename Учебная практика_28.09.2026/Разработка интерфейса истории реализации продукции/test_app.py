from pathlib import Path
import sqlite3
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from app import create_server
from create_database import create_demo_database
from database import HISTORY_QUERY, SalesRepository, connect_database


class PartnerHistoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.db"
        create_demo_database(self.database_path)
        self.repository = SalesRepository(self.database_path)
        self.server = create_server(port=0, database_path=self.database_path)
        self.server_thread = Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=5)
        self.temporary_directory.cleanup()

    def get_page(self, path: str) -> str:
        with urlopen(f"{self.base_url}{path}", timeout=5) as response:
            return response.read().decode("utf-8")

    def test_history_query_uses_required_joins(self) -> None:
        normalized_query = " ".join(HISTORY_QUERY.upper().split())
        self.assertIn("JOIN PARTNERS", normalized_query)
        self.assertIn("JOIN PRODUCTS", normalized_query)
        self.assertIn("SH.QUANTITY", normalized_query)
        self.assertIn("STRFTIME('%D.%M.%Y'", normalized_query)

    def test_main_window_contains_partner_selection_and_button(self) -> None:
        page = self.get_page("/")
        self.assertEqual(page.count('name="partner_id"'), 4)
        self.assertIn("История продаж", page)
        self.assertIn('action="/partner/history"', page)

    def test_history_window_has_partner_name_and_required_columns(self) -> None:
        page = self.get_page("/partner/history?partner_id=1")
        self.assertIn("CRM: История реализации продукции — Альфа Снаб", page)
        self.assertIn("Наименование продукции", page)
        self.assertIn("Количество (шт.)", page)
        self.assertIn("Дата продажи", page)
        self.assertIn("Панель акустическая", page)

    def test_history_is_filtered_by_partner_id(self) -> None:
        alpha_history = self.repository.get_partner_history(1)
        vector_history = self.repository.get_partner_history(2)
        self.assertEqual(len(alpha_history), 3)
        self.assertEqual(len(vector_history), 2)
        self.assertNotEqual(
            {row.product_name for row in alpha_history},
            {row.product_name for row in vector_history},
        )

    def test_dates_are_returned_in_human_readable_format(self) -> None:
        history = self.repository.get_partner_history(1)
        self.assertEqual(history[0].sale_date, "14.09.2026")
        self.assertRegex(history[-1].sale_date, r"^\d{2}\.\d{2}\.\d{4}$")

    def test_partner_without_sales_has_empty_state(self) -> None:
        page = self.get_page("/partner/history?partner_id=4")
        self.assertIn("История пока пуста", page)
        self.assertNotIn("<table>", page)

    def test_missing_partner_selection_returns_clear_error(self) -> None:
        with self.assertRaises(HTTPError) as context:
            urlopen(f"{self.base_url}/partner/history", timeout=5)
        page = context.exception.read().decode("utf-8")
        self.assertEqual(context.exception.code, 400)
        self.assertIn("Выберите партнёра", page)

    def test_unknown_partner_returns_not_found(self) -> None:
        with self.assertRaises(HTTPError) as context:
            urlopen(f"{self.base_url}/partner/history?partner_id=999", timeout=5)
        self.assertEqual(context.exception.code, 404)

    def test_foreign_keys_protect_references(self) -> None:
        with connect_database(self.database_path) as connection:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    """
                    INSERT INTO sales_history (
                        partner_id, product_id, quantity, sale_date
                    ) VALUES (999, 1, 10, '2026-09-28')
                    """
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
