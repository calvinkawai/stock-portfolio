from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel


class Portfolio(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(nullable=False)  # e.g., "Growth Strategy", "Dividend Picks"
    description: str | None = Field(default=None)
    user_id: int = Field(foreign_key="user.id", nullable=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    owner: Optional["User"] = Relationship(
        back_populates="portfolios"
    )  # Requires User model import or string ref
    holdings: list["Holding"] = Relationship(
        back_populates="portfolio",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Holding(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    portfolio_id: int = Field(foreign_key="portfolio.id", nullable=False)
    symbol: str = Field(index=True, nullable=False)  # e.g., "AAPL", "NVDA"

    # User's Custom Execution Prices
    buy_price: float = Field(
        nullable=False
    )  # Price paid per share when position was opened
    sell_price: float | None = Field(
        default=None
    )  # Execution price when position is closed
    eod_price: float = Field(nullable=False)  # Latest end-of-day price for the position

    # Position Lifecycle: "OPEN" or "CLOSED"
    status: str = Field(default="OPEN", index=True)

    # Unit represents an abstract, proportional slice of your total portfolio.
    unit: int = Field(nullable=False)

    notes: str | None = Field(
        default=None
    )  # Optional trade thesis or notes for friends
    created_at: datetime = Field(default_factory=datetime.utcnow)
    closed_at: datetime | None = Field(default=None)

    # Relationships
    portfolio: Portfolio | None = Relationship(back_populates="holdings")
