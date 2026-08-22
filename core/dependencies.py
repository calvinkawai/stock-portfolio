from typing import Generator

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from db.session import get_db
from models.portfolio import Portfolio
from models.user import User
from repositories.user_repo import get_user_by_session_token


def get_current_user_optional(
    session_token: str | None = Cookie(None), db: Session = Depends(get_db)
) -> User | None:
    """
    Reads the `session_token` cookie and returns the logged-in User if valid.
    Returns `None` if the cookie is missing or invalid.
    Useful for pages accessible by both guests and logged-in users.
    """
    if not session_token:
        return None

    return get_user_by_session_token(db, token=session_token)


def get_current_user(user: User | None = Depends(get_current_user_optional)) -> User:
    """
    Enforces authentication.
    If the user is not logged in, raises an HTTP 401 Unauthorized exception.
    Use this dependency on protected routes (e.g., dashboard, adding trades).
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def get_portfolio(portfolio_key: str, db: Session = Depends(get_db)) -> Portfolio:
    try:
        portfolio_id = int(portfolio_key)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
    portfolio = db.exec(select(Portfolio).where(Portfolio.id == portfolio_id)).first()
    if not portfolio:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found.")
    return portfolio


def ensure_owner(portfolio: Portfolio = Depends(get_portfolio), user: User = Depends(get_current_user)) -> Portfolio:
    if portfolio.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to modify this portfolio.")
    return portfolio
