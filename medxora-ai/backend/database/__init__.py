"""
database package — re-exports everything for backward compatibility.
Import from sub-modules for clarity:
  from database.db     import get_db, init_db, Base
  from database.tables import Strategy, BacktestResult
"""

from database.db     import Base, engine, SessionLocal, get_db, init_db
from database.tables import Strategy, BacktestResult

__all__ = [
    "Base", "engine", "SessionLocal", "get_db", "init_db",
    "Strategy", "BacktestResult",
]
