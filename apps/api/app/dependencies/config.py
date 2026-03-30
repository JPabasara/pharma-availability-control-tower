"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).resolve().parents[4]
load_dotenv(_project_root / ".env")


class Settings:
    """Application settings loaded from environment."""

    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3307"))
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "control_tower_mvp")
    MYSQL_USER: str = os.getenv("MYSQL_USER", "ct_user")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "ct_pass")
    MYSQL_ROOT_PASSWORD: str = os.getenv("MYSQL_ROOT_PASSWORD", "rootpass")

    @property
    def DATABASE_URL(self) -> str:
        """Build SQLAlchemy DSN from env or construct from parts."""
        url = os.getenv("DATABASE_URL")
        if url:
            return url
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )


settings = Settings()
