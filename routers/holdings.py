from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from core.dependencies import ensure_owner, get_portfolio
from db.session import get_db
from models.portfolio import Holding, Portfolio
from repositories.portfolio_repo import (
    add_holding,
    close_holding,
    delete_open_holding,
    get_single_portfolio_data,
)
from schemas.dashboard_context import CloseHoldingRequest, HoldingRequest

templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix="/portfolios", tags=["Holdings"])


def _render_panel(request: Request, key: str, data: dict) -> HTMLResponse:
    return templates.TemplateResponse(
        "partials/portfolio_panel_response.html",
        {
            "request": request,
            "key": key,
            "p": data,
            "context": {"api_base": ""},
        },
    )


@router.post("/{portfolio_key}/holdings", response_class=HTMLResponse)
async def add_holding_endpoint(
    portfolio_key: str,
    request: Request,
    db: Session = Depends(get_db),
    portfolio: Portfolio = Depends(ensure_owner),
    payload: HoldingRequest = Depends(),
):
    """Adds (or tops up) a position and returns the re-rendered portfolio panel."""
    add_holding(db, portfolio.id, payload.ticker, payload.unit, payload.buy)
    data = get_single_portfolio_data(db, portfolio.id, portfolio.user_id)
    return _render_panel(request, portfolio_key, data)


@router.post("/{portfolio_key}/holdings/{ticker}/close", response_class=HTMLResponse)
async def close_holding_endpoint(
    portfolio_key: str,
    ticker: str,
    request: Request,
    db: Session = Depends(get_db),
    portfolio: Portfolio = Depends(ensure_owner),
    payload: CloseHoldingRequest = Depends(),
):
    """Closes (fully or partially) a holding and returns the re-rendered portfolio panel."""
    rows = db.exec(
        select(Holding).where(
            Holding.portfolio_id == portfolio.id,
            Holding.symbol == ticker.upper(),
        )
    ).all()
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Holding {ticker.upper()} not found in this portfolio.",
        )
    holding = next((h for h in rows if h.status == "OPEN"), None)
    if holding is None:
        raise HTTPException(
            status_code=409, detail=f"Holding {ticker.upper()} is already closed."
        )
    if payload.unit > holding.unit:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot sell {payload.unit} units; only {holding.unit} are held.",
        )

    exit_date = date.fromisoformat(payload.date)
    close_holding(db, portfolio.id, ticker, payload.sell, payload.unit, exit_date)
    data = get_single_portfolio_data(db, portfolio.id, portfolio.user_id)
    return _render_panel(request, portfolio_key, data)


@router.delete("/{portfolio_key}/holdings/{ticker}", response_class=HTMLResponse)
async def delete_holding_endpoint(
    portfolio_key: str,
    ticker: str,
    request: Request,
    db: Session = Depends(get_db),
    portfolio: Portfolio = Depends(ensure_owner),
):
    """Deletes an open holding and returns the re-rendered portfolio panel."""
    delete_open_holding(db, portfolio.id, ticker)
    data = get_single_portfolio_data(db, portfolio.id, portfolio.user_id)
    return _render_panel(request, portfolio_key, data)
