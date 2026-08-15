# db/session.py
from sqlmodel import Session, SQLModel, create_engine

SQLITE_FILE_NAME = "portfolio_app.db"
sqlite_url = f"sqlite:///{SQLITE_FILE_NAME}"

# connect_args={"check_same_thread": False} is required for SQLite + FastAPI async handling
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})


def create_db_and_tables():
    """Generates SQLite tables automatically from your models."""
    SQLModel.metadata.create_all(engine)


def get_db():
    """FastAPI Dependency: Yields a fresh database session per web request."""
    with Session(engine) as session:
        yield session
