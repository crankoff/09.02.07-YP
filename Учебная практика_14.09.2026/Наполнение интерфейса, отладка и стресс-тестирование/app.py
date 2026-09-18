from __future__ import annotations

import argparse
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlparse

from core import DATABASE_PATH, PartnerCard, get_partner_cards


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
    request_queue_size = 128


def render_partner_card(partner: PartnerCard) -> str:
    formatted_quantity = f"{partner.total_quantity:,}".replace(",", " ")
    return f"""
        <article class="partner-card" data-partner-id="{partner.partner_id}">
          <div class="partner-card__top">
            <h2><span>{escape(partner.partner_type)} | </span>{escape(partner.name)}</h2>
            <strong class="discount" aria-label="Скидка {partner.discount} процентов">{partner.discount}%</strong>
          </div>
          <div class="partner-card__body">
            <dl class="details">
              <div><dt>Директор</dt><dd>{escape(partner.director)}</dd></div>
              <div><dt>Телефон</dt><dd>{escape(partner.phone)}</dd></div>
              <div><dt>Email</dt><dd>{escape(partner.email)}</dd></div>
              <div><dt>Рейтинг</dt><dd>{partner.rating} / 10</dd></div>
            </dl>
            <div class="quantity">
              <span>Общий объем продаж</span>
              <b>{formatted_quantity} ед.</b>
            </div>
          </div>
        </article>
    """


def render_page(partners: list[PartnerCard]) -> str:
    cards = "\n".join(render_partner_card(partner) for partner in partners)
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>CRM: Список партнёров и скидок</title>
  <link rel="icon" href="/resources/app_icon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <header class="app-header">
    <div class="app-header__inner">
      <img class="company-logo" src="/resources/company_logo.svg" alt="Логотип компании">
      <form action="/" method="get">
        <button type="submit">Обновить данные</button>
      </form>
    </div>
  </header>
  <main>
    <section class="page-heading" aria-labelledby="page-title">
      <div>
        <p class="eyebrow">ПАРТНЁРСКАЯ ПРОГРАММА</p>
        <h1 id="page-title">Партнёры и скидки</h1>
        <p>Актуальные данные из базы и автоматический расчёт скидки</p>
      </div>
      <div class="counter"><b>{len(partners)}</b><span>партнёров</span></div>
    </section>
    <section class="partner-list" aria-label="Список партнёров">
      {cards}
    </section>
    <footer>Источник: SQLite <span>•</span> Скидки рассчитаны по общему объёму продаж</footer>
  </main>
</body>
</html>
"""


def create_request_handler(database_path: str | Path):
    class ApplicationHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self.send_content(
                    render_page(get_partner_cards(database_path)).encode("utf-8"),
                    "text/html; charset=utf-8",
                )
                return
            if path == "/api/partners":
                payload = [card.to_dict() for card in get_partner_cards(database_path)]
                self.send_content(
                    json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8",
                )
                return
            if path == "/health":
                self.send_content(b'{"status":"ok"}', "application/json")
                return
            if path in STATIC_FILES:
                file_path, content_type = STATIC_FILES[path]
                self.send_content(file_path.read_bytes(), content_type)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

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
    return ApplicationServer(
        (host, port),
        create_request_handler(database_path),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="CRM: партнёры и скидки")
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
