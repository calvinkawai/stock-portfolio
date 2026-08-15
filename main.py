# main.py
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse

from db.session import create_db_and_tables, get_db
from models.portfolio import Portfolio
from models.user import Session as UserSession

# Import all models here so SQLModel metadata detects them prior to table creation
from models.user import User
from repositories.user_repo import get_user_by_session_token
from routers import auth, portfolio, holdings
from services.ticker_loader import seed_tickers_if_empty

# List of routes that MUST remain accessible to guests
PUBLIC_PATHS = {"/login", "/register", "/static", "/favicon.ico"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs on startup: creates portfolio_app.db and all tables
    create_db_and_tables()
    seed_tickers_if_empty()
    print("Database and tables initialized successfully!")
    yield


app = FastAPI(title="Portfolio Sharing App", lifespan=lifespan)


# Register the router here!
app.include_router(portfolio.router)
app.include_router(auth.router)
app.include_router(holdings.router)

# List of routes that MUST remain accessible to guests
PUBLIC_PATHS = {"/login", "/register", "/static", "/favicon.ico"}


@app.middleware("http")
async def enforce_login_middleware(request: Request, call_next):
    path = request.url.path

    # 1. Allow public routes or static files
    if path in PUBLIC_PATHS or path.startswith("/static/"):
        return await call_next(request)

    # 2. Extract session token cookie
    session_token = request.cookies.get("session_token")

    # 3. Validate user session against SQLite DB
    is_authenticated = False
    if session_token:
        # Get a DB session manually for middleware
        db_gen = get_db()
        db = next(db_gen)
        try:
            user = get_user_by_session_token(db, session_token)
            if user:
                is_authenticated = True
        finally:
            db_gen.close()

    # 4. Redirect unauthenticated users to /login
    if not is_authenticated:
        return RedirectResponse(url="/login", status_code=303)

    return await call_next(request)


@app.get("/")
def read_root():
    return {"message": "Portfolio API is running!"}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    # If a protected route throws a 401 Unauthorized, redirect to /login
    if exc.status_code == 401:
        return RedirectResponse(url="/login", status_code=303)
    return exc
