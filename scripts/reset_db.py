"""Full database reset: drop all tables, run migrations, reseed.

Usage:
    python scripts/reset_db.py

WARNING: This destroys all data and recreates from scratch.
"""

import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
venv_python = project_root / ".venv" / "Scripts" / "python.exe"
venv_alembic = project_root / ".venv" / "Scripts" / "alembic.exe"


def run(cmd: list[str], label: str):
    """Run a command and print its result."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    result = subprocess.run(
        cmd,
        cwd=str(project_root),
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"\nFAILED: {label}")
        sys.exit(1)


def main():
    print()
    print("+" + "="*58 + "+")
    print("|     PHARMA CONTROL TOWER - FULL DATABASE RESET          |")
    print("+" + "="*58 + "+")

    # Step 1: Drop all tables
    run(
        [str(venv_python), "scripts/drop_tables.py"],
        "Step 1/3: Drop all tables",
    )

    # Step 2: Run Alembic migrations from scratch
    run(
        [str(venv_alembic), "upgrade", "head"],
        "Step 2/3: Run migrations (alembic upgrade head)",
    )

    # Step 3: Seed data
    run(
        [str(venv_python), "db/seeds/seed_all.py"],
        "Step 3/3: Seed demo data",
    )

    print()
    print("+" + "="*58 + "+")
    print("|                  RESET COMPLETE                         |")
    print("+" + "="*58 + "+")
    print()


if __name__ == "__main__":
    main()
