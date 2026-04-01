"""Helper: drop all tables including alembic_version."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from apps.api.app.dependencies.database import engine
from storage.models import Base

Base.metadata.drop_all(engine)

with engine.begin() as conn:
    conn.execute(text("DROP TABLE IF EXISTS alembic_version"))

print("All tables dropped.")
