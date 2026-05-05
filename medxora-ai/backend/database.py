"""
Legacy compatibility wrapper.

The active database implementation lives in:
  - database/db.py
  - database/tables.py

This module re-exports the current objects so any older import paths keep
working without redefining models or metadata.
"""

from database import Base, engine, SessionLocal, get_db, init_db

__all__ = ["Base", "engine", "SessionLocal", "get_db", "init_db"]
