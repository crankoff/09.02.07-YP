from __future__ import annotations

import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import logging
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs

from create_database import DEFAULT_DATABASE_PATH, initialize_database
from database import CatalogRepository
from logging_config import DEFAULT_LOG_PATH, create_logger
from material_calculator import MaterialCalculator
from views import render_page


BASE_DIR = Path(__file__).resolve().parent
STYLE_PATH = BASE_DIR / "styles.css"


class SecureCalculatorHandler(BaseHTTPRequestHandler):
    repository: CatalogRepository
    calculator: MaterialCalculator
    logger: logging.Logger

    def do_GET(self) -> None:
        if self.path == "/":
            self._show_form()
            return
        if self.path == "/styles.css":
            self._send_file(STYLE_PATH, "text/css; charset=utf-8")
            return
        self._send_error_page(404, "Страница не найдена", "Проверьте адрес.")

    def do_POST(self) -> None:
        if self.path != "/calculate":
            self._send_error_page(404, "Страница не найдена", "Проверьте адрес.")
            return

        form_data = self._read_form()
        try:
            product_type_id = int(form_data.get("product_type_id", ""))
            material_type_id = int(form_data.get("material_type_id", ""))
            quantity = int(form_data.get("quantity", ""))
            param_1 = float(form_data.get("param_1", ""))
            param_2 = float(form_data.get("param_2", ""))
        except (TypeError, ValueError) as error:
            self.logger.warning("Некорректный ввод в форме: %s", error)
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
                "типы — существовать в справочниках."
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
        except (OSError, sqlite3.Error, ValueError) as exception:
            self.logger.exception("Ошибка формирования страницы: %s", exception)
            self._send_error_page(
                500,
                "Внутренняя ошибка",
                "Не удалось получить данные справочников.",
            )

    def _read_form(self) -> dict[str, str]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            request_body = self.rfile.read(content_length).decode("utf-8")
            parsed_data = parse_qs(request_body, keep_blank_values=True)
            return {name: values[0] for name, values in parsed_data.items()}
        except (UnicodeDecodeError, ValueError) as error:
            self.logger.warning("Ошибка чтения формы: %s", error)
            return {}

    def _send_file(self, path: Path, content_type: str) -> None:
        try:
            content = path.read_bytes()
            self._send_bytes(content, content_type)
        except OSError as error:
            self.logger.warning("Файл интерфейса недоступен: %s", error)
            self._send_error_page(404, "Файл не найден", "Проверьте адрес.")

    def _send_error_page(self, status: int, title: str, message: str) -> None:
        page = f"""<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><title>{escape(title)}</title></head>
<body><h1>{escape(title)}</h1><p>{escape(message)}</p></body>
</html>"""
        self._send_bytes(
            page.encode("utf-8"),
            "text/html; charset=utf-8",
            status,
        )

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
    log_path: Path = DEFAULT_LOG_PATH,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> ThreadingHTTPServer:
    database_path = initialize_database(database_path)
    logger = create_logger(log_path)

    class ConfiguredHandler(SecureCalculatorHandler):
        repository = CatalogRepository(database_path)
        calculator = MaterialCalculator(database_path, logger)

    ConfiguredHandler.logger = logger
    return ThreadingHTTPServer((host, port), ConfiguredHandler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Безопасный расчёт материалов")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    arguments = parser.parse_args()
    server = create_server(
        arguments.database,
        arguments.log,
        arguments.host,
        arguments.port,
    )
    print(f"Приложение доступно по адресу http://{arguments.host}:{arguments.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
