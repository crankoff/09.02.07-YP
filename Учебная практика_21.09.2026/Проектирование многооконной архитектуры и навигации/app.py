from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, urlparse

from database import DATABASE_PATH, Partner, PartnerRepository
from windows import MainWindow, PartnerEditWindow


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
EDIT_PATH = re.compile(r"^/partner/(\d+)/edit$")


class ApplicationServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64


def create_request_handler(database_path: str | Path):
    repository = PartnerRepository(database_path)
    main_window = MainWindow()
    edit_window = PartnerEditWindow()

    class ApplicationHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self.send_html(main_window.render(repository.list_all()))
                return
            if path == "/partner/new":
                self.send_html(edit_window.render())
                return
            match = EDIT_PATH.fullmatch(path)
            if match:
                partner = repository.get(int(match.group(1)))
                if partner is None:
                    self.send_error(HTTPStatus.NOT_FOUND, "Партнёр не найден")
                    return
                self.send_html(edit_window.render(partner))
                return
            if path in STATIC_FILES:
                file_path, content_type = STATIC_FILES[path]
                self.send_content(file_path.read_bytes(), content_type)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/partner/save":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_length = int(self.headers.get("Content-Length", "0"))
            form = parse_qs(
                self.rfile.read(content_length).decode("utf-8"),
                keep_blank_values=True,
            )
            partner, validation_error = self.parse_partner(form)
            if validation_error:
                self.send_html(
                    edit_window.render(partner, validation_error),
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                )
                return
            try:
                repository.save(partner)
            except sqlite3.IntegrityError:
                self.send_html(
                    edit_window.render(partner, "Партнёр с таким email уже существует"),
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                )
                return
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", "/")
            self.end_headers()

        @staticmethod
        def parse_partner(form: dict[str, list[str]]) -> tuple[Partner, str]:
            def value(name: str) -> str:
                return form.get(name, [""])[0].strip()

            partner_id_text = value("partner_id")
            rating_text = value("rating")
            required_values = [
                value("partner_type"),
                value("name"),
                value("director"),
                value("phone"),
                value("email"),
                rating_text,
            ]
            rating = int(rating_text) if rating_text.isdigit() else -1
            partner = Partner(
                int(partner_id_text) if partner_id_text.isdigit() else None,
                required_values[0],
                required_values[1],
                required_values[2],
                required_values[3],
                required_values[4],
                rating,
            )
            if any(not field for field in required_values):
                return partner, "Заполните все обязательные поля"
            if rating not in range(0, 11):
                return partner, "Рейтинг должен быть от 0 до 10"
            return partner, ""

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
    parser = argparse.ArgumentParser(description="CRM: многооконная навигация")
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
