from __future__ import annotations

import argparse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, urlparse

from database import (
    DATABASE_PATH,
    Partner,
    PartnerRepository,
    ReferentialIntegrityError,
)
from windows import MainWindow, PARTNER_TYPES, PartnerEditWindow


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
PHONE_PATTERN = re.compile(r"^\+7 \d{3} \d{3}-\d{2}-\d{2}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ApplicationServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 64


def create_request_handler(database_path: str | Path):
    repository = PartnerRepository(database_path)
    main_window = MainWindow()
    edit_window = PartnerEditWindow()

    class ApplicationHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            try:
                self.handle_get()
            except sqlite3.Error:
                self.send_database_error()

        def handle_get(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                query = parse_qs(urlparse(self.path).query)
                notices = {
                    "created": "Партнёр добавлен. Список автоматически обновлён.",
                    "updated": "Данные партнёра обновлены.",
                    "deleted": "Партнёр удалён. Список автоматически обновлён.",
                }
                self.send_html(
                    main_window.render(
                        repository.list_all(),
                        notice=notices.get(query.get("status", [""])[0], ""),
                    )
                )
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
            try:
                self.handle_post()
            except sqlite3.Error:
                self.send_database_error()

        def handle_post(self) -> None:
            path = urlparse(self.path).path
            if path == "/partner/delete":
                self.delete_partner()
                return
            if path == "/partner/cancel":
                self.cancel_edit()
                return
            if path != "/partner/save":
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
                is_editing = partner.partner_id is not None
                repository.save(partner)
            except sqlite3.IntegrityError:
                self.send_html(
                    edit_window.render(partner, "Партнёр с таким email уже существует"),
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                )
                return
            status = "updated" if is_editing else "created"
            self.redirect(f"/?status={status}")

        def cancel_edit(self) -> None:
            content_length = int(self.headers.get("Content-Length", "0"))
            form = parse_qs(
                self.rfile.read(content_length).decode("utf-8"),
                keep_blank_values=True,
            )
            draft, _ = self.parse_partner(form)
            baseline = (
                repository.get(draft.partner_id)
                if draft.partner_id is not None
                else Partner(None, "ООО", "", "", "", "", "", 0)
            )
            if baseline is None:
                self.send_error(HTTPStatus.NOT_FOUND, "Партнёр не найден")
                return
            if self.form_state(draft) != self.form_state(baseline):
                self.send_html(
                    edit_window.render(
                        draft,
                        warning=(
                            "Есть несохранённые изменения. При выходе они будут "
                            "потеряны. Продолжить редактирование или выйти без сохранения?"
                        ),
                    )
                )
                return
            self.redirect("/")

        def delete_partner(self) -> None:
            content_length = int(self.headers.get("Content-Length", "0"))
            form = parse_qs(self.rfile.read(content_length).decode("utf-8"))
            partner_id_text = form.get("partner_id", [""])[0]
            if not partner_id_text.isdigit():
                self.send_error(HTTPStatus.BAD_REQUEST, "Некорректный ID партнёра")
                return
            try:
                repository.delete(int(partner_id_text))
            except ReferentialIntegrityError as error:
                self.send_html(
                    main_window.render(repository.list_all(), error=str(error)),
                    HTTPStatus.CONFLICT,
                )
                return
            except KeyError:
                self.send_error(HTTPStatus.NOT_FOUND, "Партнёр не найден")
                return
            self.redirect("/?status=deleted")

        def redirect(self, location: str) -> None:
            self.send_response(HTTPStatus.SEE_OTHER)
            self.send_header("Location", location)
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
                value("address"),
                value("director"),
                value("phone"),
                value("email"),
                rating_text,
            ]
            rating_error = ""
            try:
                rating: int | str = int(rating_text)
            except (TypeError, ValueError):
                rating = rating_text
                rating_error = (
                    "Рейтинг должен быть целым числом от 0. "
                    "Удалите буквы и знаки препинания, затем повторите попытку."
                )
            partner = Partner(
                # ID из скрытого поля определяет режим INSERT или UPDATE.
                int(partner_id_text) if partner_id_text.isdigit() else None,
                required_values[0],
                required_values[1],
                required_values[2],
                required_values[3],
                required_values[4],
                required_values[5],
                rating,
            )
            if any(not field for field in required_values):
                return partner, "Наименование, email и остальные обязательные поля не должны быть пустыми"
            if partner.partner_type not in PARTNER_TYPES:
                return partner, "Выберите тип партнёра из списка"
            if rating_error:
                return partner, rating_error
            if rating < 0:
                return partner, "Рейтинг должен быть целым числом от 0. Введите неотрицательное значение"
            if not PHONE_PATTERN.fullmatch(partner.phone):
                return partner, "Телефон должен соответствовать формату +7 900 000-00-00"
            if not EMAIL_PATTERN.fullmatch(partner.email):
                return partner, "Введите корректный email"
            return partner, ""

        @staticmethod
        def form_state(partner: Partner) -> tuple[str, ...]:
            return (
                partner.partner_type,
                partner.name,
                partner.address,
                partner.director,
                partner.phone,
                partner.email,
                str(partner.rating),
            )

        def send_database_error(self) -> None:
            self.send_html(
                main_window.render(
                    [],
                    error=(
                        "База данных недоступна. Проверьте файл БД и права доступа, "
                        "затем обновите страницу."
                    ),
                ),
                HTTPStatus.SERVICE_UNAVAILABLE,
            )

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
