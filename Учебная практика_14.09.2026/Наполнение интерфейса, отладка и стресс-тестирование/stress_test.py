from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
from threading import Thread
from time import perf_counter
from urllib.request import urlopen

from app import create_server
from core import connect_database, get_partner_cards, initialize_database


def create_stress_database(
    database_path: str | Path,
    partner_count: int,
    sales_per_partner: int,
) -> None:
    initialize_database(database_path, reset=True)
    partners = [
        (
            "ООО" if number % 2 else "ИП",
            f"Тестовый партнёр {number:04d}",
            f"Директор {number:04d}",
            f"+7 900 {number % 1000:03d}-{number % 100:02d}-{number % 100:02d}",
            f"partner-{number:04d}@stress.example",
            number % 11,
        )
        for number in range(1, partner_count + 1)
    ]
    sales = [
        (
            partner_id,
            f"2026-{sale_number % 12 + 1:02d}-{sale_number % 28 + 1:02d}",
            partner_id * 100 + sale_number + 1,
        )
        for partner_id in range(1, partner_count + 1)
        for sale_number in range(sales_per_partner)
    ]
    with connect_database(database_path) as connection:
        connection.executemany(
            """
            INSERT INTO partners (
                partner_type, name, director, phone, email, rating
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            partners,
        )
        connection.executemany(
            """
            INSERT INTO sales_history (partner_id, sale_date, quantity)
            VALUES (?, ?, ?)
            """,
            sales,
        )


def run_stress_test(
    partner_count: int = 300,
    sales_per_partner: int = 12,
    request_count: int = 40,
    workers: int = 8,
) -> dict[str, float | int]:
    with tempfile.TemporaryDirectory() as temporary_directory:
        database_path = Path(temporary_directory) / "stress.db"
        creation_started = perf_counter()
        create_stress_database(database_path, partner_count, sales_per_partner)
        creation_seconds = perf_counter() - creation_started

        query_started = perf_counter()
        cards = get_partner_cards(database_path)
        query_seconds = perf_counter() - query_started
        if len(cards) != partner_count:
            raise AssertionError("Агрегация вернула неверное число партнёров")

        server = create_server(port=0, database_path=database_path)
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        address = f"http://127.0.0.1:{server.server_port}/api/partners"

        def request_partners() -> int:
            with urlopen(address, timeout=30) as response:
                if response.status != 200:
                    raise AssertionError(f"HTTP {response.status}")
                return len(json.loads(response.read().decode("utf-8")))

        requests_started = perf_counter()
        try:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                results = list(executor.map(lambda _: request_partners(), range(request_count)))
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)
        requests_seconds = perf_counter() - requests_started

        if any(result != partner_count for result in results):
            raise AssertionError("API вернул неполный список партнёров")

    return {
        "partners": partner_count,
        "sales": partner_count * sales_per_partner,
        "requests": request_count,
        "workers": workers,
        "database_creation_seconds": round(creation_seconds, 4),
        "aggregation_seconds": round(query_seconds, 4),
        "parallel_requests_seconds": round(requests_seconds, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Стресс-тест CRM")
    parser.add_argument("--partners", type=int, default=300)
    parser.add_argument("--sales-per-partner", type=int, default=12)
    parser.add_argument("--requests", type=int, default=40)
    parser.add_argument("--workers", type=int, default=8)
    arguments = parser.parse_args()
    result = run_stress_test(
        arguments.partners,
        arguments.sales_per_partner,
        arguments.requests,
        arguments.workers,
    )
    print("Стресс-тест успешно завершён")
    for name, value in result.items():
        print(f"{name}: {value}")


if __name__ == "__main__":
    main()
