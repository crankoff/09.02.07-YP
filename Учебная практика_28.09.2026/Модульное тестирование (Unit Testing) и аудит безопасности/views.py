from __future__ import annotations

from html import escape

from database import CatalogItem


DEFAULT_FORM_DATA = {
    "product_type_id": "1",
    "material_type_id": "1",
    "quantity": "10",
    "param_1": "2.5",
    "param_2": "4.0",
}


def render_page(
    product_types: list[CatalogItem],
    material_types: list[CatalogItem],
    form_data: dict[str, str] | None = None,
    result: int | None = None,
    error: str | None = None,
) -> str:
    values = DEFAULT_FORM_DATA.copy()
    if form_data is not None:
        values.update(form_data)

    product_options = _render_options(
        product_types,
        values["product_type_id"],
        "коэффициент",
    )
    material_options = _render_options(
        material_types,
        values["material_type_id"],
        "брак",
        "%",
    )
    notification = _render_notification(result, error)

    return f"""<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>CRM: Безопасный расчёт материалов</title>
    <link rel="stylesheet" href="/styles.css">
</head>
<body>
    <main>
        <header>
            <p class="eyebrow">Производственная CRM</p>
            <h1>Безопасный расчёт материалов</h1>
            <p class="subtitle">
                Параметризованные SQL-запросы, проверка ввода и журналирование ошибок.
            </p>
        </header>
        <div class="layout">
            <form method="post" action="/calculate">
                <h2>Параметры заказа</h2>
                <label>
                    <span>Тип продукции</span>
                    <select name="product_type_id" required>{product_options}</select>
                </label>
                <label>
                    <span>Тип материала</span>
                    <select name="material_type_id" required>{material_options}</select>
                </label>
                <div class="fields">
                    <label>
                        <span>Количество</span>
                        <input name="quantity" type="number" min="1" step="1"
                               value="{escape(values['quantity'])}" required>
                    </label>
                    <label>
                        <span>Параметр 1</span>
                        <input name="param_1" type="number" min="0.01" step="any"
                               value="{escape(values['param_1'])}" required>
                    </label>
                    <label>
                        <span>Параметр 2</span>
                        <input name="param_2" type="number" min="0.01" step="any"
                               value="{escape(values['param_2'])}" required>
                    </label>
                </div>
                <button type="submit">Выполнить расчёт</button>
            </form>
            <aside>
                {notification}
                <section class="security-card">
                    <p class="eyebrow">Контроль безопасности</p>
                    <ul>
                        <li>Входные значения проверяются до обращения к БД.</li>
                        <li>SQL-параметры передаются отдельно от текста запроса.</li>
                        <li>Ошибки записываются в журнал с датой и временем.</li>
                    </ul>
                </section>
            </aside>
        </div>
    </main>
</body>
</html>"""


def _render_options(
    items: list[CatalogItem],
    selected_id: str,
    value_name: str,
    suffix: str = "",
) -> str:
    options = []
    for item in items:
        selected = " selected" if str(item.item_id) == selected_id else ""
        label = f"{item.name} — {value_name} {item.value:g}{suffix}"
        options.append(
            f'<option value="{item.item_id}"{selected}>{escape(label)}</option>'
        )
    return "".join(options)


def _render_notification(result: int | None, error: str | None) -> str:
    if error is not None:
        return f"""
            <section class="notification error" role="alert">
                <p class="eyebrow">Ошибка ввода</p>
                <h2>Расчёт не выполнен</h2>
                <p>{escape(error)}</p>
            </section>
        """
    if result is not None:
        return f"""
            <section class="notification success" role="status">
                <p class="eyebrow">Готово</p>
                <h2>Требуется материала</h2>
                <strong data-testid="result">{result}</strong>
                <p>условных единиц с учётом брака</p>
            </section>
        """
    return """
        <section class="notification">
            <p class="eyebrow">Результат</p>
            <h2>Ожидание расчёта</h2>
            <p>Заполните форму и нажмите кнопку.</p>
        </section>
    """
