from calendar import c
from typing import Optional

from pydantic import BaseModel, model_validator


class HoldingRequest(BaseModel):
    """
    {
      "ticker": "NVDA",
      "unit": 15,
      "buy": 120.50
    }
    """

    ticker: str
    unit: int
    buy: float


class CloseHoldingRequest(BaseModel):
    """
    {
      "sell": 130.25,
      "unit": 10,
      "date": "2026-07-11"
    }
    """

    sell: float
    unit: int
    date: str


class TickerData(BaseModel):
    ticker: str
    name: str


class HoldingData(BaseModel):
    ticker: str
    name: str
    weight: float
    unit: int
    buy: float
    eod: Optional[float] = None

    @model_validator(mode="after")
    def set_eod_default(self) -> "HoldingData":
        if self.eod is None:
            self.eod = self.buy
        return self


class ClosedHoldingData(BaseModel):
    ticker: str
    unit: int
    weight: float
    buy: float
    sell: float
    date: str


class PortfolioData(BaseModel):
    label: str
    owner: str
    editable: bool
    holdings: list[HoldingData]
    closed: list[ClosedHoldingData]
    total_unit: int


class UserData(BaseModel):
    username: str
    initials: str


class DashboardContext(BaseModel):
    app_name: str
    app_short: str
    api_base: str = "/api"
    user: UserData
    current_portfolio_key: str
    portfolios: dict[str, PortfolioData]
    ticker_universe: list[TickerData]
