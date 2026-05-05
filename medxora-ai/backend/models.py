"""
Legacy compatibility wrapper.

The canonical ORM models live in database/tables.py. Re-exporting them here
avoids duplicate table registration when older code imports backend.models.
"""

from database.tables import BacktestResult, Strategy

__all__ = ["Strategy", "BacktestResult"]
