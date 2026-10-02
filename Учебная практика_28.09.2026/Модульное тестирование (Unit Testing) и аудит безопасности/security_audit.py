from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
AUDITED_FILES = (
    BASE_DIR / "app.py",
    BASE_DIR / "database.py",
    BASE_DIR / "material_calculator.py",
)


@dataclass(frozen=True)
class AuditFinding:
    path: Path
    line: int
    message: str


def audit_sql_calls(paths: tuple[Path, ...] = AUDITED_FILES) -> list[AuditFinding]:
    findings = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not _is_execute_call(node):
                continue
            query_expression = node.args[0] if node.args else None
            if _contains_string_interpolation(query_expression):
                findings.append(
                    AuditFinding(
                        path,
                        node.lineno,
                        "SQL-запрос формируется конкатенацией или интерполяцией",
                    )
                )
    return findings


def _is_execute_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    )


def _contains_string_interpolation(node: ast.AST | None) -> bool:
    if isinstance(node, ast.JoinedStr):
        return True
    if isinstance(node, ast.BinOp):
        return isinstance(node.op, (ast.Add, ast.Mod))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return node.func.attr == "format"
    return False


def main() -> int:
    findings = audit_sql_calls()
    if findings:
        for finding in findings:
            print(f"{finding.path.name}:{finding.line}: {finding.message}")
        return 1
    print("Аудит пройден: небезопасная сборка SQL-запросов не обнаружена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
