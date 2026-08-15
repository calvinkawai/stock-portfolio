from typing import Generator, Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlmodel import Session

from db.session import get_db
from models.user import User
from repositories.user_repo import get_user_by_session_token


def get_current_user_optional(
    session_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Reads the `session_token` cookie and returns the logged-in User if valid.
    Returns `None` if the cookie is missing or invalid.
    Useful for pages accessible by both guests and logged-in users.
    """
    if not session_token:
        return None

    return get_user_by_session_token(db, token=session_token)


def get_current_user(user: Optional[User] = Depends(get_current_user_optional)) -> User:
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
