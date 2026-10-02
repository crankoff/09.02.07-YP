from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs, urlparse

from database import DATABASE_PATH, SalesRepository
from windows import MainWindow, PartnerHistoryWindow


BASE_DIR = Path(__file__).resolve().parent
STATIC_FILES = {
    "/styles.css": (BASE_DIR / "styles.css", "text/css; charset=utf-8"),
    "/resources/app_icon.svg": (
        BASE_DIR / "resources" / "app_icon.svg",
        "image/svg+xml",
    ),
    "/resources/company_logo.svg": (
        BASE_DIR / "resources" / "company_logo.svg",
        "image/svg+xml",
    ),
}


class ApplicationServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64


def create_request_handler(database_path: str | Path):
    repository = SalesRepository(database_path)
    main_window = MainWindow()
    history_window = PartnerHistoryWindow()

    class ApplicationHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            try:
                self.handle_get()
            except sqlite3.Error:
                self.send_html(
                    main_window.render(
                        [],
                        "База данных недоступна. Проверьте файл БД и повторите попытку.",
                    ),
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )

        def handle_get(self) -> None:
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            if path == "/":
                self.send_html(main_window.render(repository.list_partners()))
                return
            if path == "/partner/history":
                partner_id_text = parse_qs(parsed_url.query).get("partner_id", [""])[0]
                if not partner_id_text.isdigit():
                    self.send_html(
                        main_window.render(
                            repository.list_partners(),
                            "Выберите партнёра и повторите попытку.",
                        ),
                        HTTPStatus.BAD_REQUEST,
                    )
                    return
                partner = repository.get_partner(int(partner_id_text))
                if partner is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                history = repository.get_partner_history(partner.partner_id)
                self.send_html(history_window.render(partner, history))
                return
            if path in STATIC_FILES:
                file_path, content_type = STATIC_FILES[path]
                self.send_content(file_path.read_bytes(), content_type)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def send_html(
            self,
            html: str,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            self.send_content(html.encode("utf-8"), "text/html; charset=utf-8", status)

        def send_content(
            self,
            content: bytes,
            content_type: str,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format_string: str, *args: object) -> None:
            return

    return ApplicationHandler


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    database_path: str | Path = DATABASE_PATH,
) -> ApplicationServer:
    return ApplicationServer((host, port), create_request_handler(database_path))


def main() -> None:
    parser = argparse.ArgumentParser(description="CRM: история реализации")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--database", type=Path, default=DATABASE_PATH)
    arguments = parser.parse_args()
    server = create_server(arguments.host, arguments.port, arguments.database)
    print(f"Приложение запущено: http://{arguments.host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
