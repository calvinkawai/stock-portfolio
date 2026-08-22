# repositories/user_repo.py
from typing import Optional

from sqlmodel import Session, select

from models.user import Session as UserSession
from models.user import User


def create_user(db: Session, username: str, hashed_password: str) -> User:
    user = User(username=username, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_username(db: Session, username: str) -> User | None:
    statement = select(User).where(User.username == username)
    return db.exec(statement).first()


def create_session(db: Session, user_id: int, token: str) -> UserSession:
    user_session = UserSession(token=token, user_id=user_id)
    db.add(user_session)
    db.commit()
    return user_session


def delete_session(db: Session, token: str) -> bool:
    """
    Deletes a session record by its token string.
    Returns True if deleted, or False if the session token was not found.
    """
    if not token:
        return False

    statement = select(UserSession).where(UserSession.token == token)
    session_record = db.exec(statement).first()

    if session_record:
        db.delete(session_record)
        db.commit()
        return True

    return False


def get_user_by_session_token(db: Session, token: str) -> User | None:
    if not token:
        return None
    statement = select(UserSession).where(UserSession.token == token)
    session_record = db.exec(statement).first()
    return session_record.user if session_record else None
