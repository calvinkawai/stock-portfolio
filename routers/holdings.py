import json
from datetime import date
from typing import Optional
from urllib.parse import parse_qsl

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlmodel import Session, select

from core.dependencies import get_current_user
from db.session import get_db
from models.portfolio import Portfolio
from models.user import User
from repositories.portfolio_repo import (
    add_holding,
    close_holding,
    get_single_portfolio_data,
    delete_open_holding,
    HoldingNotFound,
    HoldingAlreadyClosed,
)
from models.portfolio import Holding
from schemas.dashboard_context import CloseHoldingRequest, HoldingRequest

templates = Jinja2Templates(directory="templates")

router = APIRouter(prefix="/api/portfolios", tags=["Holdings"])


def _error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": message})


def _render_panel(request: Request, key: str, data: dict) -> HTMLResponse:
    return templates.TemplateResponse(
        "partials/portfolio_panel_response.html",
        {
            "request": request,
            "key": key,
            "p": data,
            "context": {"api_base": "/api"},
        },
    )


async def _parse_holding_request(request: Request) -> Optional[HoldingRequest]:
    """Accepts both HTMX form posts (urlencoded) and JSON bodies."""
    body = await request.body()
    if not body:
        return None

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            raw = json.loads(body)
        except (ValueError, TypeError):
            return None
    else:
        raw = dict(parse_qsl(body.decode()))

    try:
        return HoldingRequest(**raw)
    except ValidationError:
        return None


async def _parse_close_request(request: Request) -> Optional[CloseHoldingRequest]:
    """Accepts both HTMX form posts (urlencoded) and JSON bodies."""
    body = await request.body()
    if not body:
        return None

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            raw = json.loads(body)
        except (ValueError, TypeError):
            return None
    else:
        raw = dict(parse_qsl(body.decode()))

    try:
        return CloseHoldingRequest(**raw)
    except ValidationError:
        return None


@router.post("/{portfolio_key}/holdings", response_class=HTMLResponse)
async def add_holding_endpoint(
    portfolio_key: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Adds (or tops up) a position and returns the re-rendered portfolio panel."""
    # Resolve portfolio
    try:
        portfolio_id = int(portfolio_key)
    except (TypeError, ValueError):
        return _error(404, "Portfolio not found.")

    portfolio = db.exec(select(Portfolio).where(Portfolio.id == portfolio_id)).first()
    if not portfolio:
        return _error(404, "Portfolio not found.")

    # Authorization: only the owner may mutate
    if portfolio.user_id != user.id:
        return _error(403, "You do not have permission to modify this portfolio.")

    # Parse + validate payload (form or JSON)
    payload = await _parse_holding_request(request)
    if payload is None:
        return _error(400, "Invalid request: ticker, unit and buy are required.")
    if not payload.ticker or not payload.ticker.strip():
        return _error(400, "Ticker is required.")
    if payload.unit is None or payload.unit <= 0:
        return _error(400, "Unit must be greater than 0.")
    if payload.buy is None or payload.buy <= 0:
        return _error(400, "Buy price must be greater than 0.")

    # Mutate
    try:
        add_holding(db, portfolio_id, payload.ticker.strip(), payload.unit, payload.buy)
    except ValueError as exc:
        return _error(400, str(exc))

    # Re-render the affected panel only
    data = get_single_portfolio_data(db, portfolio_id, user.id)
    if data is None:
        return _error(500, "Failed to load updated portfolio data.")

    return _render_panel(request, portfolio_key, data)


@router.post(
    "/{portfolio_key}/holdings/{ticker}/close", response_class=HTMLResponse
)
async def close_holding_endpoint(
    portfolio_key: str,
    ticker: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Closes (fully or partially) a holding and returns the re-rendered portfolio panel."""
    # Resolve portfolio
    try:
        portfolio_id = int(portfolio_key)
    except (TypeError, ValueError):
        return _error(404, "Portfolio not found.")

    portfolio = db.exec(select(Portfolio).where(Portfolio.id == portfolio_id)).first()
    if not portfolio:
        return _error(404, "Portfolio not found.")

    # Authorization: only the owner may mutate
    if portfolio.user_id != user.id:
        return _error(403, "You do not have permission to modify this portfolio.")

    # Parse + validate payload (form or JSON)
    payload = await _parse_close_request(request)
    if payload is None:
        return _error(400, "Invalid request: sell, unit and date are required.")
    if payload.sell is None or payload.sell <= 0:
        return _error(400, "Sell price must be greater than 0.")
    if payload.unit is None or payload.unit <= 0:
        return _error(400, "Unit must be a positive integer.")

    try:
        exit_date = date.fromisoformat(payload.date)
    except (TypeError, ValueError):
        return _error(400, "Date must be in YYYY-MM-DD format.")
    if exit_date > date.today():
        return _error(400, "Date cannot be in the future.")

    # Cannot sell more units than are held.
    # A symbol may have multiple rows (open position + closed exit chunks);
    # only the OPEN row is sellable.
    rows = db.exec(
        select(Holding).where(
            Holding.portfolio_id == portfolio_id,
            Holding.symbol == ticker.upper(),
        )
    ).all()
    if not rows:
        return _error(404, f"Holding {ticker.upper()} not found in this portfolio.")
    holding = next((h for h in rows if h.status == "OPEN"), None)
    if holding is None:
        return _error(409, f"Holding {ticker.upper()} is already closed.")
    if payload.unit > holding.unit:
        return _error(
            400,
            f"Cannot sell {payload.unit} units; only {holding.unit} are held.",
        )

    # Mutate
    try:
        close_holding(db, portfolio_id, ticker, payload.sell, payload.unit, exit_date)
    except HoldingNotFound as exc:
        return _error(404, str(exc))
    except HoldingAlreadyClosed as exc:
        return _error(409, str(exc))

    # Re-render the affected panel only
    data = get_single_portfolio_data(db, portfolio_id, user.id)
    if data is None:
        return _error(500, "Failed to load updated portfolio data.")

    return _render_panel(request, portfolio_key, data)


@router.delete("/{portfolio_key}/holdings/{ticker}", response_class=HTMLResponse)
async def delete_holding_endpoint(
    portfolio_key: str,
    ticker: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Deletes an open holding and returns the re-rendered portfolio panel."""
    # Resolve portfolio
    try:
        portfolio_id = int(portfolio_key)
    except (TypeError, ValueError):
        return _error(404, "Portfolio not found.")

    portfolio = db.exec(select(Portfolio).where(Portfolio.id == portfolio_id)).first()
    if not portfolio:
        return _error(404, "Portfolio not found.")

    # Authorization: only the owner may mutate
    if portfolio.user_id != user.id:
        return _error(403, "You do not have permission to modify this portfolio.")

    # Mutate
    try:
        delete_open_holding(db, portfolio_id, ticker)
    except HoldingNotFound as exc:
        return _error(404, str(exc))
    except HoldingAlreadyClosed as exc:
        return _error(409, str(exc))

    # Re-render the affected panel only
    data = get_single_portfolio_data(db, portfolio_id, user.id)
    if data is None:
        return _error(500, "Failed to load updated portfolio data.")

    return _render_panel(request, portfolio_key, data)
