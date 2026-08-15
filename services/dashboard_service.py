from typing import Optional

from sqlmodel import Session

from models.user import User
from repositories.portfolio_repo import (
    get_all_portfolios_with_holdings_and_tickers,
    get_ticker_universe,
)
from schemas.dashboard_context import DashboardContext


def get_dashboard_context(db: Session, current_user: User) -> DashboardContext:
    """
    Aggregates all data required for the dashboard into a single context object.
    """
    # 1. Fetch raw data from repositories
    portfolios_data = get_all_portfolios_with_holdings_and_tickers(db)
    ticker_universe_raw = get_ticker_universe(db)

    # 2. Process Portfolios
    portfolios_dict: dict[str, dict] = {}
    for p in portfolios_data:
        owner_display = (
            "you" if p["user_id"] == current_user.id else p["owner_username"]
        )

        portfolios_dict[str(p["id"])] = {
            "label": p["name"],
            "owner": owner_display,
            "editable": p["user_id"] == current_user.id,
            "holdings": p["holdings"],
            "closed": p["closed"],
            "total_unit": p["total_unit"]
        }

    # 3. Determine current_portfolio_key
    current_portfolio_key = None
    for p_id, p_data in portfolios_dict.items():
        if p_data["editable"]:
            current_portfolio_key = p_id
            break

    if not current_portfolio_key and portfolios_dict:
        current_portfolio_key = list(portfolios_dict.keys())[0]

    if not current_portfolio_key:
        current_portfolio_key = "none"

    # 4. Construct Final Context
    return DashboardContext(
        app_name="Ledgr",
        app_short="LG",
        user={
            "username": current_user.username,
            "initials": current_user.username[:2].upper(),
        },
        current_portfolio_key=current_portfolio_key,
        portfolios=portfolios_dict,
        ticker_universe=ticker_universe_raw,
    )
