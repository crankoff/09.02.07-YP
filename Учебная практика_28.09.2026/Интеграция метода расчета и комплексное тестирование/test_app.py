from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from app import create_server
from create_database import initialize_database
from material_calculator import MaterialCalculator


class IntegratedCalculatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temporary_directory.name) / "test.db"
        initialize_database(self.database_path)
        self.calculator = MaterialCalculator(self.database_path)
        self.server = create_server(self.database_path, port=0)
        self.server_thread = Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=3)
        self.temporary_directory.cleanup()

    def _request(
        self,
        path: str,
        form_data: dict[str, object] | None = None,
    ) -> tuple[int, str]:
        data = None
        if form_data is not None:
            data = urlencode(form_data).encode("utf-8")
        request = Request(self.base_url + path, data=data)
        try:
            with urlopen(request, timeout=3) as response:
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

    def test_main_page_contains_all_fields_and_catalogs(self) -> None:
        status, page = self._request("/")
        self.assertEqual(status, 200)
        self.assertIn("Калькулятор материалов", page)
        self.assertIn('name="product_type_id"', page)
        self.assertIn('name="material_type_id"', page)
        self.assertIn('name="quantity"', page)
        self.assertIn('name="param_1"', page)
        self.assertIn('name="param_2"', page)
        self.assertIn("Ламинированная панель", page)
        self.assertIn("Древесная плита", page)

    def test_successful_calculation_is_shown_in_interface(self) -> None:
        status, page = self._request("/calculate", self._valid_form())
        self.assertEqual(status, 200)
        self.assertIn('data-testid="result">111</p>', page)
        self.assertIn("Расчёт завершён", page)

    def test_unknown_product_id_shows_error_without_crash(self) -> None:
        form_data = self._valid_form()
        form_data["product_type_id"] = 999
        status, page = self._request("/calculate", form_data)
        self.assertEqual(status, 422)
        self.assertIn("Расчёт не выполнен", page)
        self.assertIn("существовать в справочниках", page)

    def test_unknown_material_id_shows_error_without_crash(self) -> None:
        form_data = self._valid_form()
        form_data["material_type_id"] = 999
        status, page = self._request("/calculate", form_data)
        self.assertEqual(status, 422)
        self.assertIn("Расчёт не выполнен", page)

    def test_negative_parameter_shows_error_without_crash(self) -> None:
        form_data = self._valid_form()
        form_data["param_1"] = -2
        status, page = self._request("/calculate", form_data)
        self.assertEqual(status, 422)
        self.assertIn("больше нуля", page)

    def test_zero_quantity_shows_error_without_crash(self) -> None:
        form_data = self._valid_form()
        form_data["quantity"] = 0
        status, page = self._request("/calculate", form_data)
        self.assertEqual(status, 422)
        self.assertIn("Проверьте введённые данные", page)

    def test_non_numeric_value_shows_informative_error(self) -> None:
        form_data = self._valid_form()
        form_data["param_2"] = "не число"
        status, page = self._request("/calculate", form_data)
        self.assertEqual(status, 400)
        self.assertIn("числовые значения", page)

    def test_missing_value_shows_informative_error(self) -> None:
        form_data = self._valid_form()
        del form_data["quantity"]
        status, page = self._request("/calculate", form_data)
        self.assertEqual(status, 400)
        self.assertIn("числовые значения", page)

    def test_calculator_handles_repeated_calls(self) -> None:
        results = [
            self.calculator.calculate_material_amount(1, 1, 10, 2.5, 4.0)
            for _ in range(250)
        ]
        self.assertEqual(set(results), {111})

    def test_server_handles_parallel_requests(self) -> None:
        def calculate() -> tuple[int, str]:
            return self._request("/calculate", self._valid_form())

        with ThreadPoolExecutor(max_workers=8) as executor:
            responses = list(executor.map(lambda _: calculate(), range(40)))
        self.assertTrue(all(status == 200 for status, _ in responses))
        self.assertTrue(all('data-testid="result">111</p>' in page for _, page in responses))

    def test_exact_integer_is_not_rounded_to_next_number(self) -> None:
        result = self.calculator.calculate_material_amount(4, 4, 2, 1.5, 2.0)
        self.assertEqual(result, 6)

    def test_missing_database_table_returns_minus_one(self) -> None:
        broken_database = Path(self.temporary_directory.name) / "broken.db"
        calculator = MaterialCalculator(broken_database)
        result = calculator.calculate_material_amount(1, 1, 10, 2.5, 4.0)
        self.assertEqual(result, -1)


if __name__ == "__main__":
    unittest.main()
