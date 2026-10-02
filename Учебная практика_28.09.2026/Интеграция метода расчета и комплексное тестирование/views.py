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

    product_options = _render_product_options(
        product_types,
        values["product_type_id"],
    )
    material_options = _render_material_options(
        material_types,
        values["material_type_id"],
    )
    notification = _render_notification(result, error)

    return f"""<!doctype html>
<html lang="ru">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>CRM: Калькулятор материалов</title>
    <link rel="icon" href="/app_icon.svg" type="image/svg+xml">
    <link rel="stylesheet" href="/styles.css">
</head>
<body>
    <header class="site-header">
        <div class="header-content">
            <img class="company-logo" src="/company_logo.svg" alt="Логотип компании">
            <div>
                <p class="eyebrow">Производственная CRM</p>
                <h1>Калькулятор материалов</h1>
            </div>
        </div>
    </header>
    <main>
        <section class="intro-card">
            <p class="eyebrow">Расчёт заказа</p>
            <h2>Определите объём сырья без ручных вычислений</h2>
            <p class="intro-text">
                Укажите параметры изделия. Система применит коэффициент типа
                продукции, добавит технологические потери и округлит результат вверх.
            </p>
        </section>
        <div class="workspace">
            <form class="calculator-card" method="post" action="/calculate">
                <div class="card-heading">
                    <div>
                        <p class="step">Параметры производства</p>
                        <h2>Данные для расчёта</h2>
                    </div>
                    <span class="badge">5 параметров</span>
                </div>
                <div class="form-grid">
                    <label class="field field-wide">
                        <span>Тип продукции</span>
                        <select name="product_type_id" required>
                            {product_options}
                        </select>
                    </label>
                    <label class="field field-wide">
                        <span>Тип материала</span>
                        <select name="material_type_id" required>
                            {material_options}
                        </select>
                    </label>
                    <label class="field">
                        <span>Количество изделий</span>
                        <input name="quantity" type="number" min="1" step="1"
                               value="{escape(values['quantity'])}" required>
                    </label>
                    <label class="field">
                        <span>Параметр 1</span>
                        <input name="param_1" type="number" min="0.01" step="any"
                               value="{escape(values['param_1'])}" required>
                    </label>
                    <label class="field">
                        <span>Параметр 2</span>
                        <input name="param_2" type="number" min="0.01" step="any"
                               value="{escape(values['param_2'])}" required>
                    </label>
                </div>
                <button type="submit">Рассчитать материал</button>
            </form>
            <aside class="result-column" aria-live="polite">
                {notification}
                <section class="formula-card">
                    <p class="step">Как считается результат</p>
                    <ol>
                        <li>Площадь умножается на коэффициент продукции.</li>
                        <li>Расход умножается на количество изделий.</li>
                        <li>Добавляется процент технологических потерь.</li>
                        <li>Значение округляется вверх до целого.</li>
                    </ol>
                </section>
            </aside>
        </div>
    </main>
</body>
</html>"""


def _render_product_options(items: list[CatalogItem], selected_id: str) -> str:
    options = []
    for item in items:
        selected = " selected" if str(item.item_id) == selected_id else ""
        label = f"{item.name} — коэффициент {item.value:g}"
        options.append(
            f'<option value="{item.item_id}"{selected}>{escape(label)}</option>'
        )
    return "".join(options)


def _render_material_options(items: list[CatalogItem], selected_id: str) -> str:
    options = []
    for item in items:
        selected = " selected" if str(item.item_id) == selected_id else ""
        label = f"{item.name} — брак {item.value:g}%"
        options.append(
            f'<option value="{item.item_id}"{selected}>{escape(label)}</option>'
        )
    return "".join(options)


def _render_notification(result: int | None, error: str | None) -> str:
    if error is not None:
        return f"""
            <section class="notification error" role="alert">
                <span class="notification-icon">!</span>
                <div>
                    <p class="step">Расчёт не выполнен</p>
                    <h2>Проверьте введённые данные</h2>
                    <p>{escape(error)}</p>
                </div>
            </section>
        """
    if result is not None:
        return f"""
            <section class="notification success" role="status">
                <span class="notification-icon">✓</span>
                <div>
                    <p class="step">Расчёт завершён</p>
                    <h2>Требуется материала</h2>
                    <p class="result-value" data-testid="result">{result}</p>
                    <p>условных единиц с учётом брака</p>
                </div>
            </section>
        """
    return """
        <section class="notification waiting">
            <span class="notification-icon">→</span>
            <div>
                <p class="step">Результат</p>
                <h2>Заполните форму</h2>
                <p>Итоговое количество появится здесь после расчёта.</p>
            </div>
        </section>
    """
