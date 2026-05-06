"""
database/db.py
SQLAlchemy engine, session factory, and Base declaration.
All other modules that need DB access import from here.
"""

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _ensure_sqlite_schema_compatibility():
    """
    Lightweight compatibility migration for older local SQLite databases.
    create_all() creates missing tables, but it does not add new columns to
    existing tables, so we patch known historical gaps here.
    """
    if engine.dialect.name != "sqlite":
        return

    migrations = {
        "strategies": {
            "parameters_json": "ALTER TABLE strategies ADD COLUMN parameters_json TEXT",
        },
    }

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table_name, columns in migrations.items():
            if table_name not in existing_tables:
                continue

            existing_columns = {
                col["name"]
                for col in inspector.get_columns(table_name)
            }
            for column_name, ddl in columns.items():
                if column_name not in existing_columns:
                    conn.execute(text(ddl))


def get_db():
    """FastAPI dependency — yields a DB session and closes it on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables (called once at startup)."""
    import database.tables  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_schema_compatibility()
