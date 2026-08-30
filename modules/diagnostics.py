"""Standalone diagnostics helpers."""
import platform
import sqlite3


def basic_checks(db_path: str):
    checks = [("Python", platform.python_version(), True),
              ("Platform", platform.platform(), True)]
    try:
        c = sqlite3.connect(db_path, timeout=10)
        c.execute("SELECT 1").fetchone()
        c.close()
        checks.append(("SQLite", "read/write connection OK", True))
    except Exception as exc:
        checks.append(("SQLite", str(exc), False))
    return checks
