from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from create_database import DEFAULT_DATABASE_PATH, initialize_database
from database import CatalogRepository
from material_calculator import MaterialCalculator
from views import render_page


BASE_DIR = Path(__file__).resolve().parent
STYLE_PATH = BASE_DIR / "styles.css"
RESOURCE_DIR = BASE_DIR / "resources"


class CalculatorRequestHandler(BaseHTTPRequestHandler):
    repository: CatalogRepository
    calculator: MaterialCalculator

    def do_GET(self) -> None:
        if self.path == "/":
            self._show_form()
            return
        if self.path == "/styles.css":
            self._send_file(STYLE_PATH, "text/css; charset=utf-8")
            return
        if self.path == "/app_icon.svg":
            self._send_file(RESOURCE_DIR / "app_icon.svg", "image/svg+xml")
            return
        if self.path == "/company_logo.svg":
            self._send_file(RESOURCE_DIR / "company_logo.svg", "image/svg+xml")
            return
        self.send_error(404, "Страница не найдена")

    def do_POST(self) -> None:
        if self.path != "/calculate":
            self.send_error(404, "Страница не найдена")
            return
        form_data = self._read_form()
        try:
            product_type_id = int(form_data.get("product_type_id", ""))
            material_type_id = int(form_data.get("material_type_id", ""))
            quantity = int(form_data.get("quantity", ""))
            param_1 = float(form_data.get("param_1", ""))
            param_2 = float(form_data.get("param_2", ""))
        except (TypeError, ValueError):
            message = "Все поля должны содержать корректные числовые значения."
            self._show_form(form_data=form_data, error=message, status=400)
            return

        result = self.calculator.calculate_material_amount(
            product_type_id,
            material_type_id,
            quantity,
            param_1,
            param_2,
        )
        if result == -1:
            message = (
                "Количество и размеры должны быть больше нуля, а выбранные "
                "типы продукции и материала — существовать в справочниках."
            )
            self._show_form(form_data=form_data, error=message, status=422)
            return
        self._show_form(form_data=form_data, result=result)

    def _show_form(
        self,
        form_data: dict[str, str] | None = None,
        result: int | None = None,
        error: str | None = None,
        status: int = 200,
    ) -> None:
        try:
            product_types = self.repository.get_product_types()
            material_types = self.repository.get_material_types()
            page = render_page(
                product_types,
                material_types,
                form_data,
                result,
                error,
            )
            self._send_bytes(
                page.encode("utf-8"),
                "text/html; charset=utf-8",
                status,
            )
        except (OSError, ValueError):
            self.send_error(500, "Не удалось получить данные справочников")

    def _read_form(self) -> dict[str, str]:
        content_length = int(self.headers.get("Content-Length", "0"))
        request_body = self.rfile.read(content_length).decode("utf-8")
        parsed_data = parse_qs(request_body, keep_blank_values=True)
        return {name: values[0] for name, values in parsed_data.items()}

    def _send_file(self, path: Path, content_type: str) -> None:
        try:
            content = path.read_bytes()
            self._send_bytes(content, content_type)
        except OSError:
            self.send_error(404, "Файл не найден")

    def _send_bytes(
        self,
        content: bytes,
        content_type: str,
        status: int = 200,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format_string: str, *args: object) -> None:
        return


def create_server(
    database_path: Path = DEFAULT_DATABASE_PATH,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> ThreadingHTTPServer:
    database_path = initialize_database(database_path)

    class ConfiguredHandler(CalculatorRequestHandler):
        repository = CatalogRepository(database_path)
        calculator = MaterialCalculator(database_path)

    return ThreadingHTTPServer((host, port), ConfiguredHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Калькулятор материалов")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    arguments = parser.parse_args()
    server = create_server(arguments.database, arguments.host, arguments.port)
    print(f"Калькулятор доступен по адресу http://{arguments.host}:{arguments.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
