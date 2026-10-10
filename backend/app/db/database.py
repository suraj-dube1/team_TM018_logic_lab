"""SQLAlchemy engine and session configuration."""

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models added in later phases."""


settings = get_settings()
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

if settings.database_url.startswith("sqlite"):
    database_file = settings.database_url.removeprefix("sqlite:///")
    Path(database_file).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and always close it after the request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def check_database_connection() -> None:
    """Raise if the configured database cannot execute a trivial query."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
