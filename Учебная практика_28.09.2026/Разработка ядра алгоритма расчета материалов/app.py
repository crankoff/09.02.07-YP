import argparse
from pathlib import Path

from create_database import DEFAULT_DATABASE_PATH, initialize_database
from material_calculator import MaterialCalculator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Расчёт количества материала с учётом технологического брака."
    )
    parser.add_argument("product_type_id", type=int)
    parser.add_argument("material_type_id", type=int)
    parser.add_argument("quantity", type=int)
    parser.add_argument("param_1", type=float)
    parser.add_argument("param_2", type=float)
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE_PATH,
        help="Путь к базе данных SQLite.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.database.exists():
        initialize_database(args.database)

    calculator = MaterialCalculator(args.database)
    result = calculator.calculate_material_amount(
        args.product_type_id,
        args.material_type_id,
        args.quantity,
        args.param_1,
        args.param_2,
    )
    if result == -1:
        print("Ошибка: проверьте идентификаторы и входные параметры.")
        return 1

    print(f"Требуемое количество материала: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
