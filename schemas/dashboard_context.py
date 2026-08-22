from datetime import date
from pydantic import BaseModel, field_validator, model_validator


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

    @field_validator('ticker')
    @classmethod
    def ticker_non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError('Ticker is required.')
        return v.upper()

    @field_validator('unit')
    @classmethod
    def unit_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('Unit must be greater than 0.')
        return v

    @field_validator('buy')
    @classmethod
    def buy_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError('Buy price must be greater than 0.')
        return v


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

    @field_validator('sell')
    @classmethod
    def sell_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError('Sell price must be greater than 0.')
        return v

    @field_validator('unit')
    @classmethod
    def unit_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('Unit must be a positive integer.')
        return v

    @field_validator('date')
    @classmethod
    def date_valid(cls, v: str) -> str:
        try:
            d = date.fromisoformat(v)
        except ValueError:
            raise ValueError('Date must be in YYYY-MM-DD format.')
        if d > date.today():
            raise ValueError('Date cannot be in the future.')
        return v


class TickerData(BaseModel):
    ticker: str
    name: str


class HoldingData(BaseModel):
    ticker: str
    name: str
    weight: float
    unit: int
    buy: float
    eod: float | None = None

    @model_validator(mode="after")
    def set_eod_default(self) -> "HoldingData":
        if self.eod is None:
            self.eod = self.buy
        return self


class ClosedHoldingData(BaseModel):
    ticker: str
    unit: int
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
    api_base: str = ""
    user: UserData
    current_portfolio_key: str
    portfolios: dict[str, PortfolioData]
    ticker_universe: list[TickerData]
