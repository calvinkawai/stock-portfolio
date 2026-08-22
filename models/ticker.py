from datetime import date
from typing import Optional

from sqlmodel import Field, SQLModel


class Ticker(SQLModel, table=True):
    symbol: str = Field(primary_key=True, index=True)  # e.g., "AAPL"
    name: str = Field(index=True, nullable=False)  # e.g., "Apple Inc."


class EODPrice(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, nullable=False)
    close_price: float = Field(nullable=False)
    price_date: date = Field(default_factory=date.today, index=True)
