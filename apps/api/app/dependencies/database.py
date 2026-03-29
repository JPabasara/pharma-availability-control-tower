"""SQLAlchemy engine, session factory, and FastAPI dependency."""

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.app.dependencies.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db():
    """FastAPI dependency that yields a database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
