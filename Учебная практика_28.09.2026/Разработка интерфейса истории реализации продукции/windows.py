from __future__ import annotations

from html import escape

from database import HistoryRow, Partner


def render_layout(window_title: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(window_title)}</title>
  <link rel="icon" href="/resources/app_icon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <header class="app-header">
    <div class="app-header__inner">
      <img class="company-logo" src="/resources/company_logo.svg" alt="Логотип компании">
      <span class="section-label">CRM · РЕАЛИЗАЦИЯ</span>
    </div>
  </header>
  {content}
</body>
</html>
"""


class MainWindow:
    window_title = "CRM: Реестр партнёров"

    def render(self, partners: list[Partner], error: str = "") -> str:
        cards = "\n".join(self._render_partner(partner) for partner in partners)
        error_block = (
            f'<p class="error" role="alert">{escape(error)}</p>' if error else ""
        )
        content = f"""
  <main>
    <section class="page-heading">
      <div>
        <p class="eyebrow">ГЛАВНОЕ ОКНО</p>
        <h1>Партнёры</h1>
        <p>Выберите партнёра для просмотра истории реализации</p>
      </div>
    </section>
    {error_block}
    <form action="/partner/history" method="get">
      <section class="partner-list" aria-label="Список партнёров">
        {cards}
      </section>
      <div class="toolbar">
        <span>Сначала выберите партнёра в списке</span>
        <button type="submit">История продаж</button>
      </div>
    </form>
  </main>
"""
        return render_layout(self.window_title, content)

    @staticmethod
    def _render_partner(partner: Partner) -> str:
        return f"""
      <label class="partner-card">
        <input type="radio" name="partner_id" value="{partner.partner_id}" required>
        <span class="radio-mark" aria-hidden="true"></span>
        <span class="partner-card__content">
          <span class="partner-card__top">
            <strong>{escape(partner.partner_type)} · {escape(partner.name)}</strong>
            <b>{partner.rating}</b>
          </span>
          <span>{escape(partner.director)}</span>
          <small>{escape(partner.phone)} · {escape(partner.email)}</small>
        </span>
      </label>
"""


class PartnerHistoryWindow:
    def render(self, partner: Partner, history: list[HistoryRow]) -> str:
        window_title = f"CRM: История реализации продукции — {partner.name}"
        total_quantity = sum(row.quantity for row in history)
        formatted_total = f"{total_quantity:,}".replace(",", " ")
        rows = "\n".join(self._render_row(row) for row in history)
        table = f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Наименование продукции</th>
              <th class="number">Количество (шт.)</th>
              <th>Дата продажи</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
""" if history else """
      <div class="empty-state">
        <b>История пока пуста</b>
        <p>Для этого партнёра ещё не зарегистрированы продажи продукции.</p>
      </div>
"""
        content = f"""
  <main>
    <nav class="breadcrumbs" aria-label="Навигация">
      <a href="/">Партнёры</a><span>→</span><b>История реализации</b>
    </nav>
    <section class="history-heading">
      <div>
        <p class="eyebrow">ИСТОРИЯ РЕАЛИЗАЦИИ ПРОДУКЦИИ</p>
        <h1>{escape(partner.name)}</h1>
        <p>{escape(partner.partner_type)} · {escape(partner.director)}</p>
      </div>
      <div class="summary">
        <span>Всего реализовано</span>
        <strong>{formatted_total} шт.</strong>
      </div>
    </section>
    {table}
    <footer><a class="secondary-button" href="/">Назад к партнёрам</a></footer>
  </main>
"""
        return render_layout(window_title, content)

    @staticmethod
    def _render_row(row: HistoryRow) -> str:
        quantity = f"{row.quantity:,}".replace(",", " ")
        return f"""
            <tr>
              <td><strong>{escape(row.product_name)}</strong></td>
              <td class="number">{quantity}</td>
              <td><time>{escape(row.sale_date)}</time></td>
            </tr>
"""
