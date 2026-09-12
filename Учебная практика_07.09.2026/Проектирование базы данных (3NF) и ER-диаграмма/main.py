"""Учебное задание: база данных партнёров и истории отгрузок в 3НФ."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Sequence


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_DB_PATH = PROJECT_DIR / "practice.db"
DEFAULT_PDF_PATH = PROJECT_DIR / "output" / "pdf" / "er_diagram.pdf"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS partners (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL CHECK (length(trim(name)) > 0),
    inn         TEXT NOT NULL UNIQUE
                    CHECK (length(inn) IN (10, 12) AND inn NOT GLOB '*[^0-9]*'),
    email       TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK (instr(email, '@') > 1),
    phone       TEXT,
    address     TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sku         TEXT NOT NULL UNIQUE CHECK (length(trim(sku)) > 0),
    name        TEXT NOT NULL CHECK (length(trim(name)) > 0),
    unit        TEXT NOT NULL CHECK (length(trim(unit)) > 0),
    price       NUMERIC NOT NULL CHECK (price >= 0)
);

CREATE TABLE IF NOT EXISTS deliveries (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id       INTEGER NOT NULL,
    delivery_number  TEXT NOT NULL UNIQUE,
    delivery_date    TEXT NOT NULL,
    status           TEXT NOT NULL DEFAULT 'planned'
                         CHECK (status IN ('planned', 'shipped', 'delivered', 'cancelled')),
    created_at       TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (partner_id) REFERENCES partners(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS delivery_items (
    delivery_id  INTEGER NOT NULL,
    product_id   INTEGER NOT NULL,
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    unit_price   NUMERIC NOT NULL CHECK (unit_price >= 0),
    PRIMARY KEY (delivery_id, product_id),
    FOREIGN KEY (delivery_id) REFERENCES deliveries(id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_deliveries_partner_date
    ON deliveries(partner_id, delivery_date);

CREATE INDEX IF NOT EXISTS idx_delivery_items_product
    ON delivery_items(product_id);

CREATE VIEW IF NOT EXISTS partner_delivery_history AS
SELECT
    p.id AS partner_id,
    p.name AS partner_name,
    d.id AS delivery_id,
    d.delivery_number,
    d.delivery_date,
    d.status,
    pr.sku,
    pr.name AS product_name,
    di.quantity,
    di.unit_price,
    ROUND(di.quantity * di.unit_price, 2) AS line_total
FROM partners AS p
JOIN deliveries AS d ON d.partner_id = p.id
JOIN delivery_items AS di ON di.delivery_id = d.id
JOIN products AS pr ON pr.id = di.product_id;
"""


def connect_database(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Открывает SQLite и обязательно включает проверку внешних ключей."""
    connection = sqlite3.connect(Path(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database(connection: sqlite3.Connection) -> None:
    """Создаёт таблицы, индексы и представление."""
    connection.executescript(SCHEMA_SQL)
    connection.commit()


def seed_demo_data(connection: sqlite3.Connection) -> None:
    """Идемпотентно добавляет небольшой набор демонстрационных данных."""
    partners = [
        (
            "ООО Альфа Логистика",
            "7701234567",
            "orders@alpha-logistics.example",
            "+7 495 100-10-10",
            "Москва, ул. Складская, д. 12",
        ),
        (
            "ИП Вектор",
            "500123456789",
            "order@vector.example",
            "+7 495 200-20-20",
            "Химки, Ленинградское ш., д. 7",
        ),
        (
            "АО СеверТорг",
            "7802345678",
            "supply@severtorg.example",
            "+7 812 300-30-30",
            "Санкт-Петербург, пр. Энергетиков, д. 18",
        ),
        (
            "ООО ТехноСнаб",
            "6673456789",
            "sales@technosnab.example",
            "+7 343 400-40-40",
            "Екатеринбург, ул. Промышленная, д. 5",
        ),
        (
            "ООО РегионПоставка",
            "5404567890",
            "info@region-postavka.example",
            "+7 383 500-50-50",
            "Новосибирск, ул. Станционная, д. 21",
        ),
        (
            "ИП Орлова Мария Сергеевна",
            "230567890123",
            "orlovams@partner.example",
            "+7 861 600-60-60",
            "Краснодар, ул. Российская, д. 44",
        ),
    ]
    products = [
        ("PRD-001", "Кабель сетевой", "шт.", 420.00),
        ("PRD-002", "Коммутатор 8-портовый", "шт.", 3650.00),
        ("PRD-003", "Монтажный комплект", "компл.", 890.00),
        ("PRD-004", "Маршрутизатор", "шт.", 5740.00),
        ("PRD-005", "Точка доступа Wi-Fi", "шт.", 6250.00),
        ("PRD-006", "Шкаф серверный 18U", "шт.", 28900.00),
        ("PRD-007", "Патч-панель 24 порта", "шт.", 3150.00),
        ("PRD-008", "Источник бесперебойного питания", "шт.", 12400.00),
    ]

    connection.executemany(
        """
        INSERT OR IGNORE INTO partners(name, inn, email, phone, address)
        VALUES (?, ?, ?, ?, ?)
        """,
        partners,
    )
    connection.executemany(
        """
        INSERT OR IGNORE INTO products(sku, name, unit, price)
        VALUES (?, ?, ?, ?)
        """,
        products,
    )

    partner_ids = {
        row["inn"]: row["id"]
        for row in connection.execute("SELECT id, inn FROM partners")
    }

    deliveries = [
        (partner_ids["7701234567"], "DEL-2026-001", "2026-08-15", "delivered"),
        (partner_ids["7701234567"], "DEL-2026-002", "2026-09-10", "shipped"),
        (partner_ids["500123456789"], "DEL-2026-003", "2026-09-11", "planned"),
        (partner_ids["500123456789"], "DEL-2026-004", "2026-07-22", "delivered"),
        (partner_ids["7802345678"], "DEL-2026-005", "2026-08-03", "delivered"),
        (partner_ids["7802345678"], "DEL-2026-006", "2026-09-12", "planned"),
        (partner_ids["6673456789"], "DEL-2026-007", "2026-08-28", "delivered"),
        (partner_ids["6673456789"], "DEL-2026-008", "2026-09-06", "cancelled"),
        (partner_ids["5404567890"], "DEL-2026-009", "2026-09-09", "shipped"),
        (partner_ids["230567890123"], "DEL-2026-010", "2026-09-12", "planned"),
    ]
    connection.executemany(
        """
        INSERT OR IGNORE INTO deliveries(
            partner_id, delivery_number, delivery_date, status
        ) VALUES (?, ?, ?, ?)
        """,
        deliveries,
    )

    product_ids = {
        row["sku"]: row["id"]
        for row in connection.execute("SELECT id, sku FROM products")
    }
    delivery_ids = {
        row["delivery_number"]: row["id"]
        for row in connection.execute("SELECT id, delivery_number FROM deliveries")
    }
    item_data = [
        ("DEL-2026-001", "PRD-001", 20, 410.00),
        ("DEL-2026-001", "PRD-002", 2, 3500.00),
        ("DEL-2026-001", "PRD-007", 2, 3000.00),
        ("DEL-2026-002", "PRD-003", 5, 870.00),
        ("DEL-2026-002", "PRD-004", 3, 5600.00),
        ("DEL-2026-003", "PRD-001", 10, 420.00),
        ("DEL-2026-003", "PRD-005", 2, 6250.00),
        ("DEL-2026-004", "PRD-002", 4, 3550.00),
        ("DEL-2026-005", "PRD-006", 1, 27500.00),
        ("DEL-2026-005", "PRD-008", 2, 11900.00),
        ("DEL-2026-006", "PRD-007", 6, 3150.00),
        ("DEL-2026-007", "PRD-001", 50, 400.00),
        ("DEL-2026-007", "PRD-003", 10, 850.00),
        ("DEL-2026-008", "PRD-004", 2, 5740.00),
        ("DEL-2026-009", "PRD-005", 5, 6100.00),
        ("DEL-2026-009", "PRD-008", 1, 12400.00),
        ("DEL-2026-010", "PRD-002", 1, 3650.00),
        ("DEL-2026-010", "PRD-003", 2, 890.00),
    ]
    items = [
        (delivery_ids[delivery_number], product_ids[sku], quantity, unit_price)
        for delivery_number, sku, quantity, unit_price in item_data
    ]
    connection.executemany(
        """
        INSERT OR IGNORE INTO delivery_items(
            delivery_id, product_id, quantity, unit_price
        ) VALUES (?, ?, ?, ?)
        """,
        items,
    )
    connection.commit()


def list_partners(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Возвращает партнёров для просмотра."""
    return connection.execute(
        """
        SELECT id, name, inn, email, phone, address, created_at, updated_at
        FROM partners
        ORDER BY name
        """
    ).fetchall()


def update_partner(
    connection: sqlite3.Connection,
    partner_id: int,
    **changes: Any,
) -> bool:
    """Обновляет разрешённые поля партнёра и возвращает признак успеха."""
    allowed_fields = {"name", "inn", "email", "phone", "address"}
    updates = {key: value for key, value in changes.items() if key in allowed_fields and value is not None}
    if not updates:
        raise ValueError("Не указано ни одного поля для обновления")

    set_clause = ", ".join(f"{field} = ?" for field in updates)
    values = [*updates.values(), partner_id]
    cursor = connection.execute(
        f"UPDATE partners SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        values,
    )
    connection.commit()
    return cursor.rowcount == 1


def get_delivery_history(
    connection: sqlite3.Connection,
    partner_id: int,
) -> list[sqlite3.Row]:
    """Возвращает историю отгрузок выбранного партнёра."""
    return connection.execute(
        """
        SELECT
            delivery_number,
            delivery_date,
            status,
            sku,
            product_name,
            quantity,
            unit_price,
            line_total
        FROM partner_delivery_history
        WHERE partner_id = ?
        ORDER BY delivery_date DESC, delivery_number, sku
        """,
        (partner_id,),
    ).fetchall()


def _find_fonts() -> tuple[str, str]:
    """Находит шрифты с поддержкой кириллицы для PDF."""
    regular_candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    bold_candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]

    regular = next((path for path in regular_candidates if Path(path).exists()), None)
    bold = next((path for path in bold_candidates if Path(path).exists()), None)
    if not regular or not bold:
        raise FileNotFoundError("Не найдены шрифты с поддержкой кириллицы")
    return regular, bold


def generate_er_diagram(output_path: Path | str = DEFAULT_PDF_PATH) -> Path:
    """Строит логическую ER-диаграмму и сохраняет её в PDF."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    regular_font, bold_font = _find_fonts()
    pdfmetrics.registerFont(TTFont("ER-Regular", regular_font))
    pdfmetrics.registerFont(TTFont("ER-Bold", bold_font))

    page_width, page_height = landscape(A4)
    document = canvas.Canvas(str(output), pagesize=(page_width, page_height))
    document.setTitle("ER-диаграмма базы данных партнёров и отгрузок")

    navy = colors.HexColor("#17324D")
    blue = colors.HexColor("#2878B5")
    pale_blue = colors.HexColor("#EAF3FA")
    border = colors.HexColor("#AAB8C5")
    text = colors.HexColor("#1F2933")
    muted = colors.HexColor("#5B6770")
    relation = colors.HexColor("#D97706")

    document.setFillColor(navy)
    document.setFont("ER-Bold", 20)
    document.drawString(36, page_height - 38, "ER-диаграмма: партнёры и история отгрузок")
    document.setFillColor(muted)
    document.setFont("ER-Regular", 9)
    document.drawString(36, page_height - 55, "Логическая модель в третьей нормальной форме (3НФ)")

    boxes = {
        "partners": (42, 320, 280, 205),
        "deliveries": (520, 335, 280, 190),
        "products": (42, 74, 280, 170),
        "delivery_items": (520, 89, 280, 155),
    }

    def relationship(
        start: tuple[float, float],
        end: tuple[float, float],
        start_cardinality: str,
        end_cardinality: str,
        label: str,
        label_position: tuple[float, float],
    ) -> None:
        document.setStrokeColor(relation)
        document.setLineWidth(2)
        document.line(start[0], start[1], end[0], end[1])
        document.setFillColor(relation)
        document.setFont("ER-Bold", 10)
        if start[0] == end[0]:
            document.drawRightString(start[0] - 8, start[1] - 18, start_cardinality)
            document.drawRightString(end[0] - 8, end[1] + 8, end_cardinality)
        else:
            document.drawString(start[0] + 6, start[1] + 6, start_cardinality)
            document.drawRightString(end[0] - 6, end[1] + 6, end_cardinality)
        document.setFillColor(muted)
        document.setFont("ER-Regular", 8)
        document.drawCentredString(label_position[0], label_position[1], label)

    relationship((322, 423), (520, 423), "1", "N", "partner_id", (421, 433))
    relationship((660, 335), (660, 244), "1", "N", "delivery_id", (705, 286))
    relationship((322, 164), (520, 164), "1", "N", "product_id", (421, 174))

    def entity_box(
        name: str,
        fields: Sequence[tuple[str, str, str]],
    ) -> None:
        x, y, width, height = boxes[name]
        document.setFillColor(colors.white)
        document.setStrokeColor(border)
        document.setLineWidth(1)
        document.roundRect(x, y, width, height, 7, fill=1, stroke=1)

        document.setFillColor(blue)
        document.roundRect(x, y + height - 31, width, 31, 7, fill=1, stroke=0)
        document.rect(x, y + height - 31, width, 12, fill=1, stroke=0)
        document.setFillColor(colors.white)
        document.setFont("ER-Bold", 12)
        document.drawString(x + 12, y + height - 20, name)

        row_height = (height - 35) / len(fields)
        row_y = y + height - 35
        for index, (key, field_name, data_type) in enumerate(fields):
            row_y -= row_height
            if index % 2 == 0:
                document.setFillColor(pale_blue)
                document.rect(x + 1, row_y, width - 2, row_height, fill=1, stroke=0)

            document.setFillColor(relation if key else muted)
            document.setFont("ER-Bold" if key else "ER-Regular", 7.4)
            document.drawString(x + 9, row_y + row_height / 2 - 2.5, key or "-")

            document.setFillColor(text)
            document.setFont("ER-Regular", 8.2)
            document.drawString(x + 58, row_y + row_height / 2 - 2.7, field_name)
            document.setFillColor(muted)
            document.drawRightString(x + width - 10, row_y + row_height / 2 - 2.7, data_type)

    entity_box(
        "partners",
        [
            ("PK", "id", "INTEGER"),
            ("NN", "name", "TEXT"),
            ("UQ NN", "inn", "TEXT"),
            ("UQ NN", "email", "TEXT"),
            ("", "phone", "TEXT"),
            ("", "address", "TEXT"),
            ("NN", "created_at", "TEXT"),
            ("NN", "updated_at", "TEXT"),
        ],
    )
    entity_box(
        "deliveries",
        [
            ("PK", "id", "INTEGER"),
            ("FK NN", "partner_id", "INTEGER"),
            ("UQ NN", "delivery_number", "TEXT"),
            ("NN", "delivery_date", "TEXT"),
            ("NN", "status", "TEXT"),
            ("NN", "created_at", "TEXT"),
        ],
    )
    entity_box(
        "products",
        [
            ("PK", "id", "INTEGER"),
            ("UQ NN", "sku", "TEXT"),
            ("NN", "name", "TEXT"),
            ("NN", "unit", "TEXT"),
            ("NN", "price", "NUMERIC"),
        ],
    )
    entity_box(
        "delivery_items",
        [
            ("PK FK", "delivery_id", "INTEGER"),
            ("PK FK", "product_id", "INTEGER"),
            ("NN", "quantity", "INTEGER"),
            ("NN", "unit_price", "NUMERIC"),
        ],
    )

    document.setFillColor(text)
    document.setFont("ER-Bold", 8)
    document.drawString(42, 49, "Обозначения:")
    document.setFont("ER-Regular", 8)
    document.drawString(115, 49, "PK - первичный ключ   FK - внешний ключ   NN - NOT NULL   UQ - UNIQUE")
    document.setFillColor(muted)
    document.drawRightString(page_width - 42, 30, "Учебная практика, 07.09.2026")

    document.showPage()
    document.save()
    return output


def print_rows(rows: Iterable[sqlite3.Row]) -> None:
    """Печатает результат запроса простой таблицей без внешних библиотек."""
    data = [dict(row) for row in rows]
    if not data:
        print("Данные не найдены.")
        return

    columns = list(data[0])
    widths = {
        column: max(len(column), *(len(str(row[column])) for row in data))
        for column in columns
    }
    separator = "+-" + "-+-".join("-" * widths[column] for column in columns) + "-+"
    print(separator)
    print("| " + " | ".join(column.ljust(widths[column]) for column in columns) + " |")
    print(separator)
    for row in data:
        print("| " + " | ".join(str(row[column]).ljust(widths[column]) for column in columns) + " |")
    print(separator)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Управление партнёрами, отгрузками и ER-диаграммой"
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="путь к SQLite БД")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="создать структуру БД")
    init_parser.add_argument("--seed", action="store_true", help="добавить демоданные")

    subparsers.add_parser("partners", help="показать список партнёров")

    update_parser = subparsers.add_parser("update-partner", help="изменить данные партнёра")
    update_parser.add_argument("partner_id", type=int)
    update_parser.add_argument("--name")
    update_parser.add_argument("--inn")
    update_parser.add_argument("--email")
    update_parser.add_argument("--phone")
    update_parser.add_argument("--address")

    history_parser = subparsers.add_parser("history", help="показать историю отгрузок")
    history_parser.add_argument("partner_id", type=int)

    diagram_parser = subparsers.add_parser("diagram", help="сформировать ER-диаграмму PDF")
    diagram_parser.add_argument("--output", type=Path, default=DEFAULT_PDF_PATH)

    subparsers.add_parser("demo", help="создать БД, демоданные и диаграмму")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "diagram":
        result = generate_er_diagram(args.output)
        print(f"ER-диаграмма создана: {result}")
        return

    try:
        with connect_database(args.db) as connection:
            if args.command == "init":
                init_database(connection)
                if args.seed:
                    seed_demo_data(connection)
                print(f"База данных создана: {args.db}")
            elif args.command == "partners":
                init_database(connection)
                print_rows(list_partners(connection))
            elif args.command == "update-partner":
                init_database(connection)
                updated = update_partner(
                    connection,
                    args.partner_id,
                    name=args.name,
                    inn=args.inn,
                    email=args.email,
                    phone=args.phone,
                    address=args.address,
                )
                print("Данные партнёра обновлены." if updated else "Партнёр не найден.")
            elif args.command == "history":
                init_database(connection)
                print_rows(get_delivery_history(connection, args.partner_id))
            elif args.command == "demo":
                init_database(connection)
                seed_demo_data(connection)
                diagram_path = generate_er_diagram()
                print("\nПартнёры:")
                print_rows(list_partners(connection))
                print("\nИстория отгрузок партнёра с id=1:")
                print_rows(get_delivery_history(connection, 1))
                print(f"\nER-диаграмма создана: {diagram_path}")
    except (sqlite3.IntegrityError, ValueError) as error:
        raise SystemExit(f"Ошибка: {error}") from error


if __name__ == "__main__":
    main()
