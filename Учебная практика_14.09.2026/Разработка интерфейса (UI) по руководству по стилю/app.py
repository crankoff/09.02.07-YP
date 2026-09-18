"""Веб-интерфейс CRM на стандартной библиотеке Python."""

from __future__ import annotations

import argparse
import html
import importlib.util
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable


PROJECT_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = PROJECT_DIR / "resources"
APP_ICON_PATH = RESOURCE_DIR / "app_icon.svg"
COMPANY_LOGO_PATH = RESOURCE_DIR / "company_logo.svg"
BACKEND_MODULE_PATH = (
    PROJECT_DIR.parent
    / "Интеграция с БД и агрегация данных (SQL + Backend)"
    / "backend.py"
)

APP_TITLE = "CRM: Список партнёров и скидок"

PARTNER_DETAILS = {
    1: {"director": "Марина Соколова", "phone": "+7 495 111-20-01", "rating": 7},
    2: {"director": "Илья Воронов", "phone": "+7 495 111-20-02", "rating": 8},
    3: {"director": "Ольга Лебедева", "phone": "+7 495 111-20-03", "rating": 9},
    4: {"director": "Алексей Орлов", "phone": "+7 495 111-20-04", "rating": 10},
    5: {"director": "Елена Крылова", "phone": "+7 495 111-20-05", "rating": 6},
}


@dataclass(frozen=True)
class PartnerCard:
    partner_id: int
    partner_type: str
    name: str
    director: str
    phone: str
    email: str
    rating: int
    total_quantity: int
    discount_percent: int


def load_backend_module():
    """Загружает модуль интеграции с БД из предыдущего задания."""
    module_spec = importlib.util.spec_from_file_location(
        "partner_backend_for_ui",
        BACKEND_MODULE_PATH,
    )
    if module_spec is None or module_spec.loader is None:
        raise ImportError("Не удалось загрузить модуль интеграции с БД")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def split_partner_name(full_name: str) -> tuple[str, str]:
    """Разделяет организационно-правовую форму и название партнёра."""
    parts = full_name.split(maxsplit=1)
    if len(parts) == 1:
        return "Партнёр", parts[0]
    return parts[0], parts[1]


def load_partner_cards() -> tuple[PartnerCard, ...]:
    """Получает партнёров из SQLite и дополняет данными для карточек UI."""
    backend = load_backend_module()
    cards = []
    for partner_id, details in PARTNER_DETAILS.items():
        partner = backend.get_partner_with_discount_from_database(partner_id)
        partner_type, name = split_partner_name(str(partner["name"]))
        cards.append(
            PartnerCard(
                partner_id=partner_id,
                partner_type=partner_type,
                name=name,
                director=str(details["director"]),
                phone=str(details["phone"]),
                email=str(partner["email"]),
                rating=int(details["rating"]),
                total_quantity=int(partner["total_quantity"]),
                discount_percent=int(partner["discount_percent"]),
            )
        )
    return tuple(cards)


def format_quantity(value: int) -> str:
    """Форматирует количество с пробелами между разрядами."""
    return f"{value:,}".replace(",", " ")


def render_partner_card(partner: PartnerCard) -> str:
    """Создаёт HTML одной карточки партнёра."""
    fields = {
        "partner_type": html.escape(partner.partner_type),
        "name": html.escape(partner.name),
        "director": html.escape(partner.director),
        "phone": html.escape(partner.phone),
        "email": html.escape(partner.email),
        "rating": partner.rating,
        "quantity": format_quantity(partner.total_quantity),
        "discount": partner.discount_percent,
    }
    return f"""
    <article class="partner-card">
      <div class="partner-card__top">
        <h2>{fields['partner_type']} <span>|</span> {fields['name']}</h2>
        <strong class="discount" aria-label="Скидка {fields['discount']} процентов">
          {fields['discount']}%
        </strong>
      </div>
      <div class="partner-card__body">
        <dl class="details">
          <div><dt>Руководитель</dt><dd>{fields['director']}</dd></div>
          <div><dt>Телефон</dt><dd>{fields['phone']}</dd></div>
          <div><dt>Email</dt><dd>{fields['email']}</dd></div>
          <div><dt>Рейтинг</dt><dd>{fields['rating']}</dd></div>
        </dl>
        <div class="quantity">
          <span>Объём покупок</span>
          <b>{fields['quantity']} ед.</b>
        </div>
      </div>
    </article>
    """


def render_page(partners: tuple[PartnerCard, ...]) -> str:
    """Создаёт готовую HTML-страницу со списком партнёров."""
    cards_html = "".join(render_partner_card(partner) for partner in partners)
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{APP_TITLE}</title>
  <link rel="icon" href="/resources/app_icon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <header class="app-header">
    <div class="app-header__inner">
      <img class="company-logo" src="/resources/company_logo.svg" alt="Partner Flow">
      <form method="get" action="/">
        <button type="submit">Обновить данные</button>
      </form>
    </div>
  </header>
  <main>
    <section class="page-heading">
      <div>
        <p class="eyebrow">УПРАВЛЕНИЕ ПАРТНЁРАМИ</p>
        <h1>{APP_TITLE}</h1>
        <p>Актуальные данные, объём продаж и индивидуальная скидка</p>
      </div>
      <div class="counter"><b>{len(partners)}</b><span>партнёров</span></div>
    </section>
    <section class="partner-list" aria-label="Список партнёров">
      {cards_html}
    </section>
    <footer>Источник: SQLite <span>•</span> Данные обновлены</footer>
  </main>
</body>
</html>
"""


class PartnerRequestHandler(SimpleHTTPRequestHandler):
    """Отдаёт динамическую главную страницу и статические ресурсы."""

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] in ("/", "/index.html"):
            page = render_page(load_partner_cards()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return
        super().do_GET()

    def log_message(self, message_format: str, *arguments: object) -> None:
        print(f"[HTTP] {message_format % arguments}")


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
) -> ThreadingHTTPServer:
    """Создаёт локальный HTTP-сервер приложения."""
    handler: Callable[..., PartnerRequestHandler]

    def handler(*args, **kwargs):
        return PartnerRequestHandler(*args, directory=str(PROJECT_DIR), **kwargs)

    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description=APP_TITLE)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    arguments = parser.parse_args()
    server = create_server(arguments.host, arguments.port)
    print(f"{APP_TITLE}: http://{arguments.host}:{arguments.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
