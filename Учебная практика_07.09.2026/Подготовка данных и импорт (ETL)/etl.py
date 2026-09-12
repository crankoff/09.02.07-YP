"""Очистка входных файлов и импорт подготовленных данных в SQLite."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_PARTNERS_PATH = PROJECT_DIR / "input" / "import_partners.csv"
DEFAULT_SALES_PATH = PROJECT_DIR / "input" / "import_sales.txt"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "output"
DEFAULT_DATABASE_PATH = PROJECT_DIR / "etl.db"

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

DATABASE_SCHEMA = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS sales;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS partners;

CREATE TABLE partners (
    partner_id    INTEGER PRIMARY KEY,
    company_name  VARCHAR(200) NOT NULL,
    inn           VARCHAR(12) NOT NULL UNIQUE,
    contact_email VARCHAR(254) COLLATE NOCASE NOT NULL UNIQUE,
    phone         VARCHAR(18),
    rating        DECIMAL(2, 1),
    CONSTRAINT chk_partners_inn CHECK (
        length(inn) IN (10, 12) AND inn NOT GLOB '*[^0-9]*'
    ),
    CONSTRAINT chk_partners_rating CHECK (
        rating IS NULL OR rating BETWEEN 0 AND 5
    )
);

CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name  VARCHAR(200) NOT NULL UNIQUE
);

CREATE TABLE sales (
    sale_id       INTEGER PRIMARY KEY,
    partner_id    INT NOT NULL,
    product_id    INT NOT NULL,
    sale_date     DATE NOT NULL,
    quantity      INT NOT NULL CHECK (quantity > 0),
    total_amount  DECIMAL(12, 2) NOT NULL CHECK (total_amount >= 0),
    CONSTRAINT fk_sales_partner
        FOREIGN KEY (partner_id) REFERENCES partners(partner_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_sales_product
        FOREIGN KEY (product_id) REFERENCES products(product_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
);

CREATE INDEX idx_sales_partner_date ON sales(partner_id, sale_date);
CREATE INDEX idx_sales_product ON sales(product_id);
"""


@dataclass(frozen=True)
class Partner:
    partner_id: int
    company_name: str
    inn: str
    contact_email: str
    phone: str | None
    rating: str | None


@dataclass(frozen=True)
class Sale:
    sale_id: int
    partner_id: int
    product_name: str
    sale_date: str
    quantity: int
    total_amount: str


@dataclass(frozen=True)
class RejectedRow:
    source: str
    row_number: int
    record_id: str
    reason: str
    raw_data: str


@dataclass
class EtlResult:
    partners: list[Partner]
    sales: list[Sale]
    rejected_rows: list[RejectedRow]
    transformations: dict[str, int]
    database_counts: dict[str, int]


def normalize_text(value: str) -> str:
    """Удаляет внешние пробелы и сворачивает повторяющиеся пробелы."""
    return " ".join(value.strip().split())


def normalize_phone(value: str) -> str | None:
    """Приводит российский номер к формату +7 XXX XXX-XX-XX."""
    if not value.strip():
        return None

    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits

    if len(digits) != 11 or not digits.startswith("7"):
        raise ValueError("некорректный российский номер телефона")
    return f"+7 {digits[1:4]} {digits[4:7]}-{digits[7:9]}-{digits[9:11]}"


def parse_integer(value: str, field_name: str, *, positive: bool = False) -> int:
    try:
        number = int(value.strip())
    except ValueError as error:
        raise ValueError(f"поле {field_name} должно быть целым числом") from error
    if positive and number <= 0:
        raise ValueError(f"поле {field_name} должно быть больше нуля")
    return number


def parse_decimal(
    value: str,
    field_name: str,
    *,
    allow_empty: bool = False,
    minimum: Decimal | None = None,
    maximum: Decimal | None = None,
    places: str = "0.01",
) -> str | None:
    cleaned = value.strip().replace(",", ".")
    if not cleaned and allow_empty:
        return None
    try:
        number = Decimal(cleaned)
    except InvalidOperation as error:
        raise ValueError(f"поле {field_name} имеет некорректный числовой формат") from error
    if minimum is not None and number < minimum:
        raise ValueError(f"поле {field_name} меньше допустимого значения")
    if maximum is not None and number > maximum:
        raise ValueError(f"поле {field_name} больше допустимого значения")
    return format(number.quantize(Decimal(places)), "f")


def parse_date(value: str) -> str:
    """Принимает ISO и российский формат, возвращает YYYY-MM-DD."""
    cleaned = value.strip()
    for date_format in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(cleaned, date_format).date().isoformat()
        except ValueError:
            continue
    raise ValueError("дата должна иметь формат YYYY-MM-DD или DD.MM.YYYY")


def load_partners(path: Path) -> tuple[list[Partner], list[RejectedRow], dict[str, int]]:
    partners: list[Partner] = []
    rejected: list[RejectedRow] = []
    transformations = {"trimmed_names": 0, "normalized_phones": 0, "empty_to_null": 0}
    seen_ids: set[int] = set()
    seen_inn: set[str] = set()
    seen_emails: set[str] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        required = {"partner_id", "company_name", "inn", "contact_email", "phone", "rating"}
        if set(reader.fieldnames or []) != required:
            raise ValueError(f"Неверные столбцы в {path.name}: {reader.fieldnames}")

        for row_number, row in enumerate(reader, start=2):
            raw_data = json.dumps(row, ensure_ascii=False, sort_keys=True)
            record_id = row.get("partner_id", "")
            try:
                partner_id = parse_integer(row["partner_id"], "partner_id", positive=True)
                company_name = normalize_text(row["company_name"])
                if not company_name:
                    raise ValueError("название компании не заполнено")
                if company_name != row["company_name"]:
                    transformations["trimmed_names"] += 1

                inn = row["inn"].strip()
                if len(inn) not in (10, 12) or not inn.isdigit():
                    raise ValueError("ИНН должен содержать 10 или 12 цифр")

                email = row["contact_email"].strip().lower()
                if not EMAIL_PATTERN.fullmatch(email):
                    raise ValueError("некорректный Email")

                phone = normalize_phone(row["phone"])
                if phone is None:
                    transformations["empty_to_null"] += 1
                elif phone != row["phone"].strip():
                    transformations["normalized_phones"] += 1

                rating = parse_decimal(
                    row["rating"],
                    "rating",
                    allow_empty=True,
                    minimum=Decimal("0"),
                    maximum=Decimal("5"),
                    places="0.1",
                )
                if rating is None:
                    transformations["empty_to_null"] += 1

                if partner_id in seen_ids:
                    raise ValueError("дубликат partner_id")
                if inn in seen_inn:
                    raise ValueError("дубликат ИНН")
                if email in seen_emails:
                    raise ValueError("дубликат Email")

                seen_ids.add(partner_id)
                seen_inn.add(inn)
                seen_emails.add(email)
                partners.append(Partner(partner_id, company_name, inn, email, phone, rating))
            except ValueError as error:
                rejected.append(
                    RejectedRow(path.name, row_number, record_id.strip(), str(error), raw_data)
                )

    return partners, rejected, transformations


def load_sales(
    path: Path,
    valid_partner_ids: set[int],
) -> tuple[list[Sale], list[RejectedRow], dict[str, int]]:
    sales: list[Sale] = []
    rejected: list[RejectedRow] = []
    transformations = {"normalized_dates": 0, "trimmed_product_names": 0}
    seen_ids: set[int] = set()
    seen_rows: set[tuple[Any, ...]] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        required = {
            "sale_id",
            "partner_id",
            "product_name",
            "sale_date",
            "quantity",
            "total_amount",
        }
        if set(reader.fieldnames or []) != required:
            raise ValueError(f"Неверные столбцы в {path.name}: {reader.fieldnames}")

        for row_number, row in enumerate(reader, start=2):
            raw_data = json.dumps(row, ensure_ascii=False, sort_keys=True)
            record_id = row.get("sale_id", "")
            try:
                sale_id = parse_integer(row["sale_id"], "sale_id", positive=True)
                partner_id = parse_integer(row["partner_id"], "partner_id", positive=True)
                if partner_id not in valid_partner_ids:
                    raise ValueError(f"partner_id={partner_id} отсутствует в файле партнёров")

                product_name = normalize_text(row["product_name"])
                if not product_name:
                    raise ValueError("название товара не заполнено")
                if product_name != row["product_name"]:
                    transformations["trimmed_product_names"] += 1

                sale_date = parse_date(row["sale_date"])
                if sale_date != row["sale_date"].strip():
                    transformations["normalized_dates"] += 1

                quantity = parse_integer(row["quantity"], "quantity", positive=True)
                total_amount = parse_decimal(
                    row["total_amount"],
                    "total_amount",
                    minimum=Decimal("0"),
                    places="0.01",
                )
                assert total_amount is not None

                natural_key = (
                    partner_id,
                    product_name.casefold(),
                    sale_date,
                    quantity,
                    total_amount,
                )
                if sale_id in seen_ids:
                    raise ValueError("дубликат sale_id")
                if natural_key in seen_rows:
                    raise ValueError("дубликат продажи")

                seen_ids.add(sale_id)
                seen_rows.add(natural_key)
                sales.append(
                    Sale(sale_id, partner_id, product_name, sale_date, quantity, total_amount)
                )
            except ValueError as error:
                rejected.append(
                    RejectedRow(path.name, row_number, record_id.strip(), str(error), raw_data)
                )

    return sales, rejected, transformations


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_clean_files(
    output_dir: Path,
    partners: list[Partner],
    sales: list[Sale],
    rejected_rows: list[RejectedRow],
) -> None:
    write_csv(
        output_dir / "clean_partners.csv",
        ["partner_id", "company_name", "inn", "contact_email", "phone", "rating"],
        (asdict(partner) for partner in partners),
    )
    write_csv(
        output_dir / "clean_sales.csv",
        ["sale_id", "partner_id", "product_name", "sale_date", "quantity", "total_amount"],
        (asdict(sale) for sale in sales),
    )
    write_csv(
        output_dir / "rejected_rows.csv",
        ["source", "row_number", "record_id", "reason", "raw_data"],
        (asdict(row) for row in rejected_rows),
    )


def import_database(database_path: Path, partners: list[Partner], sales: list[Sale]) -> None:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(DATABASE_SCHEMA)

        connection.executemany(
            """
            INSERT INTO partners(
                partner_id, company_name, inn, contact_email, phone, rating
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    partner.partner_id,
                    partner.company_name,
                    partner.inn,
                    partner.contact_email,
                    partner.phone,
                    partner.rating,
                )
                for partner in partners
            ],
        )

        product_names = sorted({sale.product_name for sale in sales}, key=str.casefold)
        connection.executemany(
            "INSERT INTO products(product_name) VALUES (?)",
            [(name,) for name in product_names],
        )
        product_ids = {
            row[1]: row[0]
            for row in connection.execute("SELECT product_id, product_name FROM products")
        }

        connection.executemany(
            """
            INSERT INTO sales(
                sale_id, partner_id, product_id, sale_date, quantity, total_amount
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    sale.sale_id,
                    sale.partner_id,
                    product_ids[sale.product_name],
                    sale.sale_date,
                    sale.quantity,
                    sale.total_amount,
                )
                for sale in sales
            ],
        )


def verify_database(database_path: Path) -> dict[str, int]:
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_key_errors = connection.execute("PRAGMA foreign_key_check").fetchall()
        if integrity != "ok" or foreign_key_errors:
            raise AssertionError(
                f"Ошибка целостности: integrity={integrity}, foreign_keys={foreign_key_errors}"
            )
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("partners", "products", "sales")
        }


def write_report(
    output_dir: Path,
    partner_source_rows: int,
    sales_source_rows: int,
    result: EtlResult,
) -> None:
    report_lines = [
        "ОТЧЁТ ETL",
        "",
        f"Исходных строк партнёров: {partner_source_rows}",
        f"Импортировано партнёров: {len(result.partners)}",
        f"Исходных строк продаж: {sales_source_rows}",
        f"Импортировано продаж: {len(result.sales)}",
        f"Отклонено строк: {len(result.rejected_rows)}",
        "",
        "Преобразования:",
        *[
            f"- {name}: {count}"
            for name, count in sorted(result.transformations.items())
        ],
        "",
        "Проверка SELECT COUNT(*):",
        *[
            f"- {table}: {count}"
            for table, count in result.database_counts.items()
        ],
        "",
        "Отклонённые строки:",
    ]
    if result.rejected_rows:
        report_lines.extend(
            f"- {row.source}, строка {row.row_number}, id={row.record_id}: {row.reason}"
            for row in result.rejected_rows
        )
    else:
        report_lines.append("- нет")

    (output_dir / "etl_report.txt").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )


def count_data_rows(path: Path) -> int:
    with path.open("r", encoding="utf-8-sig") as source:
        return max(sum(1 for _ in source) - 1, 0)


def run_etl(
    partners_path: Path,
    sales_path: Path,
    output_dir: Path,
    database_path: Path,
) -> EtlResult:
    partners, rejected_partners, partner_stats = load_partners(partners_path)
    sales, rejected_sales, sales_stats = load_sales(
        sales_path, {partner.partner_id for partner in partners}
    )
    rejected_rows = [*rejected_partners, *rejected_sales]
    transformations = {**partner_stats, **sales_stats}

    write_clean_files(output_dir, partners, sales, rejected_rows)
    import_database(database_path, partners, sales)
    database_counts = verify_database(database_path)

    result = EtlResult(
        partners=partners,
        sales=sales,
        rejected_rows=rejected_rows,
        transformations=transformations,
        database_counts=database_counts,
    )
    write_report(
        output_dir,
        count_data_rows(partners_path),
        count_data_rows(sales_path),
        result,
    )
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Очистка и импорт данных партнёров и продаж")
    parser.add_argument("--partners", type=Path, default=DEFAULT_PARTNERS_PATH)
    parser.add_argument("--sales", type=Path, default=DEFAULT_SALES_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE_PATH)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = run_etl(args.partners, args.sales, args.output_dir, args.database)

    print("ETL завершён успешно.")
    print(f"Партнёры: {result.database_counts['partners']}")
    print(f"Товары: {result.database_counts['products']}")
    print(f"Продажи: {result.database_counts['sales']}")
    print(f"Отклонённые строки: {len(result.rejected_rows)}")
    print(f"База данных: {args.database}")
    print(f"Очищенные файлы и отчёт: {args.output_dir}")


if __name__ == "__main__":
    main()
