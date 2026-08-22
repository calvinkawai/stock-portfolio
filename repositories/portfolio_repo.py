from datetime import date, datetime
from typing import Optional

from sqlmodel import Session, select

from models.portfolio import Holding, Portfolio
from models.ticker import EODPrice, Ticker
from models.user import User


class HoldingNotFound(Exception):
    pass


class HoldingAlreadyClosed(Exception):
    pass


def create_portfolio(db: Session, user: User) -> Portfolio:
    portfolio = Portfolio(name=f"{user.username}'s Postions", user_id=user.id)
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


def _latest_eod_map(db: Session, symbols: list[str]) -> dict[str, float]:
    """Returns {symbol: latest close_price} for the given symbols."""
    if not symbols:
        return {}
    rows = db.exec(
        select(EODPrice)
        .where(EODPrice.symbol.in_(symbols))
        .order_by(EODPrice.price_date.desc())
    ).all()
    latest: dict[str, float] = {}
    for row in rows:  # descending date order -> first hit per symbol is latest
        latest.setdefault(row.symbol, row.close_price)
    return latest


def _ticker_name_map(db: Session, symbols: list[str]) -> dict[str, str]:
    if not symbols:
        return {}
    rows = db.exec(select(Ticker).where(Ticker.symbol.in_(symbols))).all()
    return {t.symbol: t.name for t in rows}


def _build_portfolio_payload(
    portfolio: Portfolio,
    owner_username: str,
    holdings: list[Holding],
    eod_map: dict[str, float],
    name_map: dict[str, str],
    current_user_id: int | None = None,
) -> dict:
    """Builds the dashboard payload (weights, totals, split open/closed) for one portfolio."""
    open_holdings = [h for h in holdings if h.status == "OPEN"]
    total_unit = sum(h.unit for h in open_holdings)

    def weight(h: Holding) -> float:
        return (h.unit / total_unit * 100) if total_unit else 0.0

    holdings_data = [
        {
            "ticker": h.symbol,
            "name": name_map.get(h.symbol, h.symbol),
            "weight": weight(h),
            "unit": h.unit,
            "buy": h.buy_price,
            "eod": eod_map.get(h.symbol, h.eod_price),
        }
        for h in open_holdings
    ]

    closed_holdings = sorted(
        (h for h in holdings if h.status == "CLOSED"),
        key=lambda h: h.closed_at or datetime.min,
        reverse=True,  # latest closed position on top
    )

    closed_data = [
        {
            "ticker": h.symbol,
            "buy": h.buy_price,
            "sell": h.sell_price if h.sell_price is not None else 0.0,
            "date": h.closed_at.strftime("%Y-%m-%d") if h.closed_at else "N/A",
            "unit": h.unit,
        }
        for h in closed_holdings
    ]

    return {
        "id": portfolio.id,
        "name": portfolio.name,
        "description": portfolio.description,
        "user_id": portfolio.user_id,
        "owner_username": owner_username,
        "editable": current_user_id is not None
        and portfolio.user_id == current_user_id,
        "owner": "you"
        if (current_user_id is not None and portfolio.user_id == current_user_id)
        else owner_username,
        "holdings": holdings_data,
        "closed": closed_data,
        "total_unit": total_unit,
    }


def get_all_portfolios_with_holdings_and_tickers(db: Session) -> list[dict]:
    """
    Fetches all portfolios along with their holdings, ticker names, and latest EOD prices.
    Weights are computed per-portfolio (unit / sum of that portfolio's open units).
    Returns a list of dictionaries structured for the DashboardContext.
    """
    # 1. Fetch all portfolios with owner information
    statement = select(Portfolio, User.username).join(
        User, Portfolio.user_id == User.id
    )
    portfolios_raw = db.exec(statement).all()

    # 2. Fetch all holdings with ticker names
    holdings_rows = db.exec(
        select(Holding, Ticker.name).join(Ticker, Holding.symbol == Ticker.symbol)
    ).all()

    # 3. Group holdings by portfolio_id
    holdings_map: dict[int, list[Holding]] = {}
    for holding, _ticker_name in holdings_rows:
        holdings_map.setdefault(holding.portfolio_id, []).append(holding)

    # 4. Latest EOD price per symbol (single query)
    all_symbols = [h.symbol for hs in holdings_map.values() for h in hs]
    eod_map = _latest_eod_map(db, all_symbols)
    name_map = _ticker_name_map(db, all_symbols)

    # 5. Construct the final structured list
    return [
        _build_portfolio_payload(
            portfolio,
            owner_username,
            holdings_map.get(portfolio.id, []),
            eod_map,
            name_map,
        )
        for portfolio, owner_username in portfolios_raw
    ]


def get_single_portfolio_data(
    db: Session, portfolio_id: int, current_user_id: int
) -> dict | None:
    """
    Fetches data for a single portfolio and calculates its specific weights/totals.
    Returns a structure compatible with PortfolioData, or None if not found.
    """
    row = db.exec(
        select(Portfolio, User.username)
        .join(User, Portfolio.user_id == User.id)
        .where(Portfolio.id == portfolio_id)
    ).first()
    if not row:
        return None
    portfolio, owner_username = row

    holdings = db.exec(
        select(Holding).where(Holding.portfolio_id == portfolio_id)
    ).all()

    symbols = [h.symbol for h in holdings]
    eod_map = _latest_eod_map(db, symbols)
    name_map = _ticker_name_map(db, symbols)

    return _build_portfolio_payload(
        portfolio, owner_username, holdings, eod_map, name_map, current_user_id
    )


def add_holding(
    db: Session,
    portfolio_id: int,
    ticker_symbol: str,
    unit: int,
    buy_price: float,
) -> Holding:
    """
    Adds units of a ticker to a portfolio.
    If an OPEN holding already exists, its unit count is increased and its
    buy_price becomes the weighted average of the old and new purchases.
    Otherwise a new OPEN holding is inserted.
    """
    ticker_symbol = ticker_symbol.upper()

    # Check if ticker exists
    ticker_stmt = select(Ticker).where(Ticker.symbol == ticker_symbol)
    ticker = db.exec(ticker_stmt).first()
    if not ticker:
        raise ValueError(f"Ticker {ticker_symbol} not found.")

    # Check for an existing OPEN holding
    existing_stmt = select(Holding).where(
        Holding.portfolio_id == portfolio_id,
        Holding.symbol == ticker_symbol,
        Holding.status == "OPEN",
    )
    existing = db.exec(existing_stmt).first()

    if existing:
        # Update case: add units and recompute weighted-average buy price
        new_total_units = existing.unit + unit
        existing.buy_price = (
            (existing.unit * existing.buy_price) + (unit * buy_price)
        ) / new_total_units
        existing.unit = new_total_units
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    # Insert case: latest EOD price if available, else buy_price as fallback
    eod_map = _latest_eod_map(db, [ticker_symbol])
    eod_price = eod_map.get(ticker_symbol, buy_price)

    new_holding = Holding(
        portfolio_id=portfolio_id,
        symbol=ticker_symbol,
        unit=unit,
        buy_price=buy_price,
        eod_price=eod_price,
    )
    db.add(new_holding)
    db.commit()
    db.refresh(new_holding)
    return new_holding


def close_holding(
    db: Session,
    portfolio_id: int,
    ticker_symbol: str,
    sell_price: float,
    unit: int,
    exit_date: date,
) -> Holding:
    """
    Closes (fully or partially) a holding.

    - Full close (unit >= holding.unit): status -> "CLOSED", closed_at set.
    - Partial close (unit < holding.unit): the sold chunk is split off into a
      new CLOSED holding row (so it appears in History / realized gains),
      while the original row keeps the remaining units and stays "OPEN".
    """
    ticker_symbol = ticker_symbol.upper()

    # A symbol may have multiple rows (open position + closed exit chunks)
    rows = db.exec(
        select(Holding).where(
            Holding.portfolio_id == portfolio_id,
            Holding.symbol == ticker_symbol,
        )
    ).all()

    if not rows:
        raise HoldingNotFound(
            f"Holding {ticker_symbol} not found in portfolio {portfolio_id}."
        )

    holding = next((h for h in rows if h.status == "OPEN"), None)
    if holding is None:
        raise HoldingAlreadyClosed(f"Holding {ticker_symbol} is already closed.")

    if unit >= holding.unit:
        # Full close: flip the row in place
        holding.sell_price = sell_price
        holding.status = "CLOSED"
        holding.closed_at = exit_date
    else:
        # Partial close: split the sold chunk off as a CLOSED row
        holding.unit -= unit
        holding.sell_price = None  # no full exit on the remaining position
        db.add(holding)

        exit_row = Holding(
            portfolio_id=holding.portfolio_id,
            symbol=holding.symbol,
            unit=unit,
            buy_price=holding.buy_price,
            sell_price=sell_price,
            eod_price=holding.eod_price,
            status="CLOSED",
            closed_at=exit_date,
        )
        db.add(exit_row)

    db.commit()
    db.refresh(holding)
    return holding


def delete_open_holding(db: Session, portfolio_id: int, ticker_symbol: str) -> None:
    """Deletes an open holding from a portfolio."""
    ticker_symbol = ticker_symbol.upper()

    # A symbol may have multiple rows (open position + closed exit chunks);
    # only the OPEN row is deletable, history rows are preserved.
    holding = db.exec(
        select(Holding).where(
            Holding.portfolio_id == portfolio_id,
            Holding.symbol == ticker_symbol,
            Holding.status == "OPEN",
        )
    ).first()

    if not holding:
        exists = db.exec(
            select(Holding)
            .where(
                Holding.portfolio_id == portfolio_id,
                Holding.symbol == ticker_symbol,
            )
            .limit(1)
        ).first()
        if exists:
            raise HoldingAlreadyClosed(
                f"Holding {ticker_symbol} is already closed and cannot be deleted."
            )
        raise HoldingNotFound(
            f"Holding {ticker_symbol} not found in portfolio {portfolio_id}."
        )

    db.delete(holding)
    db.commit()


def get_ticker_universe(db: Session) -> list[dict]:
    """Fetches all tickers from the database."""
    statement = select(Ticker)
    tickers = db.exec(statement).all()
    return [{"ticker": t.symbol, "name": t.name} for t in tickers]
