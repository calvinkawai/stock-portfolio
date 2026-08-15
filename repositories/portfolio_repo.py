from datetime import date
from typing import Optional

from sqlmodel import Session, select

from models.portfolio import Holding, Portfolio
from models.ticker import EODPrice, Ticker
from models.user import User


def create_portfolio(db: Session, user: User) -> Portfolio:
    portfolio = Portfolio(name=f"{user.username}'s Postions", user_id=user.id)
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio


def get_all_portfolios_with_holdings_and_tickers(db: Session) -> list[dict]:
    """
    Fetches all portfolios along with their holdings, ticker names, and latest EOD prices.
    Returns a list of dictionaries structured for the DashboardContext.
    """
    # 1. Fetch all portfolios with owner information
    # We join with User to get the owner's username
    statement = select(Portfolio, User.username).join(
        User, Portfolio.user_id == User.id
    )
    portfolios_raw = db.exec(statement).all()

    # 2. Fetch all holdings
    # We join with Ticker to get names and EODPrice for current prices
    # This is a large join, but it's more efficient than querying per portfolio
    holdings_statement = (
        select(Holding, Ticker.name, EODPrice.close_price)
        .join(Ticker, Holding.symbol == Ticker.symbol)
        .outerjoin(EODPrice, Holding.symbol == EODPrice.symbol)
        .order_by(EODPrice.price_date.desc())  # Ensure we get latest price
    )
    holdings_raw = db.exec(holdings_statement).all()

    # 3. Group holdings by portfolio_id
    holdings_map: dict[int, list[dict]] = {}
    total_unit = sum([holding.unit for holding, _, _ in holdings_raw])
    print(total_unit, "total unit")
    for holding, ticker_name, eod_price in holdings_raw:
        if holding.portfolio_id not in holdings_map:
            holdings_map[holding.portfolio_id] = []

        holdings_map[holding.portfolio_id].append(
            {
                "ticker": holding.symbol,
                "name": ticker_name,
                "weight": holding.unit/total_unit * 100,
                "unit": holding.unit,
                "buy": holding.buy_price,
                "sell": holding.sell_price,
                "eod": eod_price,
                "status": holding.status,
                "closed_at": holding.closed_at,
            }
        )

    # 4. Construct the final structured list
    result = []
    for portfolio, owner_username in portfolios_raw:
        portfolio_holdings = holdings_map.get(portfolio.id, [])

        # Split holdings into "OPEN" and "CLOSED"
        open_holdings = [h for h in portfolio_holdings if h["status"] == "OPEN"]
        closed_holdings = [
            {
                "ticker": h["ticker"],
                "weight": h["weight"],
                "buy": h["buy"],
                "sell": h["sell"] if h["sell"] is not None else 0.0,
                "date": h["closed_at"].strftime("%Y-%m-%d")
                if h["closed_at"]
                else "N/A",
            }
            for h in portfolio_holdings
            if h["status"] == "CLOSED"
        ]

        result.append(
            {
                "id": portfolio.id,
                "name": portfolio.name,
                "description": portfolio.description,
                "user_id": portfolio.user_id,
                "owner_username": owner_username,
                "holdings": open_holdings,
                "closed": closed_holdings,
                "total_unit": total_unit
            }
        )

    return result


def add_holding(
    db: Session,
    portfolio_id: int,
    ticker_symbol: str,
    unit: int,
    buy_price: float,
) -> Holding:
    """Adds a new holding to a portfolio."""
    # Check if ticker exists
    ticker_stmt = select(Ticker).where(Ticker.symbol == ticker_symbol)
    ticker = db.exec(ticker_stmt).first()
    if not ticker:
        raise ValueError(f"Ticker {ticker_symbol} not found.")

    # Check if holding already exists
    existing_stmt = select(Holding).where(
        Holding.portfolio_id == portfolio_id,
        Holding.symbol == ticker_symbol,
        Holding.status == "OPEN",
    )
    if db.exec(existing_stmt).first():
        raise ValueError(f"Ticker {ticker_symbol} already exists in this portfolio.")

    # Calculate current EOD price if possible, else use buy_price as fallback
    eod_stmt = (
        select(EODPrice)
        .where(EODPrice.symbol == ticker_symbol, EODPrice.price_date == date.today())
        .order_by(EODPrice.price_date.desc())
    )
    eod_data = db.exec(eod_stmt).first()
    eod_price = eod_data.close_price if eod_data else buy_price

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
    holding_id: int,
    sell_price: float,
    exit_date: date,
) -> Holding:
    """Closes an existing holding."""
    holding_stmt = select(Holding).where(Holding.id == holding_id)
    holding = db.exec(holding_stmt).first()
    if not holding:
        raise ValueError(f"Holding {holding_id} not found.")

    if holding.status != "OPEN":
        raise ValueError(f"Holding {holding_id} is already closed.")

    holding.sell_price = sell_price
    holding.status = "CLOSED"
    holding.closed_at = exit_date

    db.commit()
    db.refresh(holding)
    return holding


def delete_holding(db: Session, holding_id: int) -> bool:
    """Deletes a holding from the database."""
    holding_stmt = select(Holding).where(Holding.id == holding_id)
    holding = db.exec(holding_stmt).first()
    if not holding:
        raise ValueError(f"Holding {holding_id} not found.")

    db.delete(holding)
    db.commit()
    return True


def get_ticker_universe(db: Session) -> list[dict]:
    """Fetches all tickers from the database."""
    statement = select(Ticker)
    tickers = db.exec(statement).all()
    return [{"ticker": t.symbol, "name": t.name} for t in tickers]
