from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = BASE_DIR / "materials.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


def initialize_database(database_path: Path = DEFAULT_DATABASE_PATH) -> Path:
    database_path = Path(database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")

    with sqlite3.connect(database_path) as connection:
        connection.executescript(schema)

    return database_path


if __name__ == "__main__":
    created_path = initialize_database()
    print(f"База данных готова: {created_path}")
