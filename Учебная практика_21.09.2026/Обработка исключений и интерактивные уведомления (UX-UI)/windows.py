from __future__ import annotations

from html import escape

from database import Partner


PARTNER_TYPES = ("ЗАО", "ООО", "ИП", "АО", "ПАО")


def render_dialog(kind: str, title: str, message: str) -> str:
    icons = {"error": "×", "warning": "!", "information": "i"}
    primary_action = ""
    if kind == "warning":
        primary_action = """
        <a class="danger-link" href="/">Выйти без сохранения</a>
        <form method="dialog"><button type="submit">Продолжить редактирование</button></form>
"""
    else:
        primary_action = """
        <form method="dialog"><button type="submit">Понятно</button></form>
"""
    return f"""
    <dialog class="system-dialog system-dialog--{kind}" open aria-labelledby="dialog-title">
      <div class="dialog-icon" aria-hidden="true">{icons[kind]}</div>
      <div class="dialog-content">
        <h2 id="dialog-title">{escape(title)}</h2>
        <p>{escape(message)}</p>
        <div class="dialog-actions">{primary_action}</div>
      </div>
    </dialog>
"""


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
      <span class="section-label">CRM · ПАРТНЁРЫ</span>
    </div>
  </header>
  {content}
</body>
</html>
"""


class MainWindow:
    window_title = "CRM: Реестр партнёров"

    def render(
        self,
        partners: list[Partner],
        notice: str = "",
        error: str = "",
    ) -> str:
        partner_cards = "\n".join(self._render_partner(partner) for partner in partners)
        message = ""
        if notice:
            message = render_dialog("information", "Информация", notice)
        if error:
            message = render_dialog("error", "Ошибка", error)
        content = f"""
  <main>
    <section class="page-heading">
      <div>
        <p class="eyebrow">ГЛАВНОЕ ОКНО</p>
        <h1>Реестр партнёров</h1>
        <p>Просмотр и редактирование карточек партнёров</p>
      </div>
      <a class="button" href="/partner/new">Добавить партнёра</a>
    </section>
    {message}
    <section class="partner-list" aria-label="Список партнёров">
      {partner_cards}
    </section>
    <footer>Всего партнёров: <b>{len(partners)}</b></footer>
  </main>
"""
        return render_layout(self.window_title, content)

    @staticmethod
    def _render_partner(partner: Partner) -> str:
        return f"""
      <article class="partner-card">
        <div>
          <p class="partner-type">{escape(partner.partner_type)}</p>
          <h2><a class="partner-name-link" href="/partner/{partner.partner_id}/edit">{escape(partner.name)}</a></h2>
          <dl>
            <div><dt>Директор</dt><dd>{escape(partner.director)}</dd></div>
            <div><dt>Телефон</dt><dd>{escape(partner.phone)}</dd></div>
            <div><dt>Email</dt><dd>{escape(partner.email)}</dd></div>
            <div class="address"><dt>Адрес</dt><dd>{escape(partner.address)}</dd></div>
          </dl>
        </div>
        <div class="partner-card__aside">
          <span>Рейтинг</span>
          <strong>{partner.rating} / 10</strong>
          <small>Продаж в истории: {partner.sales_count}</small>
          <a class="secondary-button" href="/partner/{partner.partner_id}/edit">Редактировать</a>
        </div>
      </article>
"""


class PartnerEditWindow:
    add_window_title = "CRM: Карточка партнёра [Добавление]"
    edit_window_title = "CRM: Карточка партнёра [Редактирование]"

    def render(
        self,
        partner: Partner | None = None,
        error: str = "",
        warning: str = "",
    ) -> str:
        is_editing = partner is not None and partner.partner_id is not None
        current = partner or Partner(None, "ООО", "", "", "", "", "", 0)
        title = self.edit_window_title if is_editing else self.add_window_title
        action_name = "Редактирование" if is_editing else "Добавление"
        dialog = ""
        if error:
            dialog = render_dialog("error", "Ошибка", error)
        if warning:
            dialog = render_dialog("warning", "Предупреждение", warning)
        # Скрытое поле переносит ID карточки между окнами добавления и редактирования.
        partner_id_value = current.partner_id or ""
        delete_form = ""
        if is_editing:
            delete_form = f"""
      <form class="delete-form" action="/partner/delete" method="post">
        <input type="hidden" name="partner_id" value="{partner_id_value}">
        <button class="danger-button" type="submit">Удалить партнёра</button>
        <small>Удаление недоступно при наличии истории продаж</small>
      </form>
"""
        content = f"""
  <main class="form-page">
    <nav class="breadcrumbs" aria-label="Навигация">
      <a href="/">Реестр партнёров</a><span>→</span><b>{action_name}</b>
    </nav>
    <section class="form-panel">
      <div class="form-panel__heading">
        <div>
          <p class="eyebrow">КАРТОЧКА ПАРТНЁРА</p>
          <h1>{action_name} партнёра</h1>
          <p>Заполните контактные данные и рейтинг компании</p>
        </div>
        <span class="mode-badge">{action_name}</span>
      </div>
      {dialog}
      <form action="/partner/save" method="post">
        <input type="hidden" name="partner_id" value="{partner_id_value}">
        <div class="form-grid">
          <label>Тип партнёра
            <select name="partner_type" required>
              {self._type_options(current.partner_type)}
            </select>
          </label>
          <label>Наименование
            <input name="name" value="{escape(current.name)}" required maxlength="150">
          </label>
          <label class="wide">Директор
            <input name="director" value="{escape(current.director)}" required maxlength="150">
          </label>
          <label class="wide">Адрес
            <input name="address" value="{escape(current.address)}" placeholder="г. Москва, ул. Примерная, д. 1" required maxlength="250">
          </label>
          <label>Телефон
            <input name="phone" value="{escape(current.phone)}" placeholder="+7 900 000-00-00" pattern="\+7\s[0-9]{{3}}\s[0-9]{{3}}-[0-9]{{2}}-[0-9]{{2}}" title="Формат: +7 900 000-00-00" required maxlength="30">
            <small>Формат: +7 900 000-00-00</small>
          </label>
          <label>Email
            <input name="email" type="email" value="{escape(current.email)}" placeholder="name@company.ru" title="Введите корпоративный email" required maxlength="150">
            <small>Например: name@company.ru</small>
          </label>
          <label>Рейтинг
            <input name="rating" type="number" min="0" step="1" value="{current.rating}" required>
          </label>
        </div>
        <div class="form-actions">
          <button class="secondary-button" type="submit" formaction="/partner/cancel" formmethod="post" formnovalidate>Назад</button>
          <button type="submit">Сохранить</button>
        </div>
      </form>
      {delete_form}
    </section>
  </main>
"""
        return render_layout(title, content)

    @staticmethod
    def _type_options(selected_type: str) -> str:
        # Фиксированный набор не позволяет сохранить произвольный тип партнёра.
        options = []
        for partner_type in PARTNER_TYPES:
            selected = " selected" if partner_type == selected_type else ""
            options.append(
                f'<option value="{partner_type}"{selected}>{partner_type}</option>'
            )
        return "".join(options)
