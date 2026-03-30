"""Helper: drop all tables including alembic_version."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from apps.api.app.dependencies.database import engine
from storage.models import Base

with engine.begin() as conn:
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

Base.metadata.drop_all(engine)

with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))

print("All tables dropped.")
