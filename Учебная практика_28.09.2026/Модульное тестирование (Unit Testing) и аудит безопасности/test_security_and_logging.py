from __future__ import annotations

from pathlib import Path
import re
import sqlite3
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app import create_server
from create_database import initialize_database
from logging_config import create_logger
from material_calculator import MaterialCalculator
from security_audit import audit_sql_calls


class SecurityAndLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        directory = Path(self.temporary_directory.name)
        self.database_path = directory / "test.db"
        self.log_path = directory / "app.log"
        initialize_database(self.database_path)
        self.server = create_server(
            self.database_path,
            self.log_path,
            port=0,
        )
        self.server_thread = Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=3)
        self.temporary_directory.cleanup()

    def _post(self, form_data: dict[str, object]) -> tuple[int, str]:
        data = urlencode(form_data).encode("utf-8")
        request = Request(self.base_url + "/calculate", data=data)
        try:
            with urlopen(request, timeout=3) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as error:
            return error.code, error.read().decode("utf-8")

    def _get(self, path: str) -> tuple[int, str]:
        try:
            with urlopen(self.base_url + path, timeout=3) as response:
                return response.status, response.read().decode("utf-8")
        except HTTPError as error:
            return error.code, error.read().decode("utf-8")

    @staticmethod
    def _valid_form() -> dict[str, object]:
        return {
            "product_type_id": 1,
            "material_type_id": 1,
            "quantity": 10,
            "param_1": 2.5,
            "param_2": 4.0,
        }

    def _catalog_counts(self) -> tuple[int, int]:
        with sqlite3.connect(self.database_path) as connection:
            product_count = connection.execute(
                "SELECT COUNT(*) FROM product_types"
            ).fetchone()[0]
            material_count = connection.execute(
                "SELECT COUNT(*) FROM material_types"
            ).fetchone()[0]
        return product_count, material_count

    def test_static_audit_finds_no_sql_interpolation(self) -> None:
        self.assertEqual(audit_sql_calls(), [])

    def test_unknown_route_returns_utf8_error_page(self) -> None:
        status, page = self._get("/unknown")
        self.assertEqual(status, 404)
        self.assertIn("Страница не найдена", page)

    def test_sql_injection_in_product_id_is_rejected(self) -> None:
        form_data = self._valid_form()
        form_data["product_type_id"] = "1 OR 1=1"
        status, page = self._post(form_data)
        self.assertEqual(status, 400)
        self.assertIn("числовые значения", page)
        self.assertEqual(self._catalog_counts(), (4, 4))

    def test_sql_injection_in_parameter_is_rejected(self) -> None:
        form_data = self._valid_form()
        form_data["param_1"] = "2.5; DROP TABLE product_types;--"
        status, page = self._post(form_data)
        self.assertEqual(status, 400)
        self.assertIn("Расчёт не выполнен", page)
        self.assertEqual(self._catalog_counts(), (4, 4))

    def test_reflected_html_is_escaped(self) -> None:
        form_data = self._valid_form()
        form_data["param_2"] = '<script>alert("xss")</script>'
        status, page = self._post(form_data)
        self.assertEqual(status, 400)
        self.assertNotIn('<script>alert("xss")</script>', page)
        self.assertIn("&lt;script&gt;", page)

    def test_parse_error_is_written_to_log_with_timestamp(self) -> None:
        form_data = self._valid_form()
        form_data["quantity"] = "not-a-number"
        self._post(form_data)
        log_content = self.log_path.read_text(encoding="utf-8")
        self.assertIn("Некорректный ввод в форме", log_content)
        self.assertRegex(log_content, r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")

    def test_database_exception_is_logged_and_returns_minus_one(self) -> None:
        directory = Path(self.temporary_directory.name)
        broken_database = directory / "broken.db"
        logger = create_logger(directory / "broken.log")
        calculator = MaterialCalculator(broken_database, logger)
        result = calculator.calculate_material_amount(1, 1, 10, 2.5, 4.0)
        self.assertEqual(result, -1)
        log_content = (directory / "broken.log").read_text(encoding="utf-8")
        self.assertIn("Ошибка обращения к справочникам", log_content)
        self.assertIsNotNone(re.search(r"\d{4}-\d{2}-\d{2}", log_content))


if __name__ == "__main__":
    unittest.main()
