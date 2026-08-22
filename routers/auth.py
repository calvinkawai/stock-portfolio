# routers/auth.py
import secrets

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from config import Settings, settings
from core.security import generate_session_token, hash_password, verify_password
from db.session import get_db
from repositories import portfolio_repo, user_repo

templates = Jinja2Templates(directory="templates")

router = APIRouter(tags=["Authentication"])


# --- LOGIN ROUTES ---


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request, session_token: str = Cookie(None), db: Session = Depends(get_db)
):
    # If user is already logged in, redirect them directly to the dashboard
    if session_token and user_repo.get_user_by_session_token(db, session_token):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request, name="auth/login.html", context={"error": None}
    )


@router.post("/login", response_class=HTMLResponse)
def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = user_repo.get_user_by_username(db, username=username)

    # Validate user exists and password matches
    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            request=request,
            name="auth/login.html",
            context={"error": "Invalid username or password.", "username": username},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Generate token & record session in SQLite
    token = generate_session_token()
    user_repo.create_session(db, user_id=user.id, token=token)

    # Set HttpOnly Cookie and Redirect to Dashboard
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="session_token", value=token, httponly=True, samesite="lax")
    return response


# --- REGISTER ROUTES ---


@router.get("/register", response_class=HTMLResponse)
def register_page(
    register_key: str,
    request: Request,
    session_token: str = Cookie(None),
    db: Session = Depends(get_db),
):
    # 1. Compare the key securely
    if not secrets.compare_digest(register_key, settings.REGISTER_KEY):
        return templates.TemplateResponse(
            request=request,
            name="404.html",
        )

    # 2. Redirect logged-in users to dashboard
    if session_token and user_repo.get_user_by_session_token(db, session_token):
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    # 3. Render registration page passing the register_key into template context
    return templates.TemplateResponse(
        request=request,
        name="auth/register.html",
    )


@router.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
):
    # Form Validations
    if password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={
                "error": "Passwords do not match.",
                "username": username,
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if user_repo.get_user_by_username(db, username=username):
        return templates.TemplateResponse(
            request=request,
            name="auth/register.html",
            context={"error": "Username is already taken."},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # Create new user in DB
    hashed_pwd = hash_password(password)
    new_user = user_repo.create_user(db, username=username, hashed_password=hashed_pwd)
    _ = portfolio_repo.create_portfolio(db, user=new_user)

    # Auto-login after registration: create session and set cookie
    token = generate_session_token()
    _ = user_repo.create_session(db, user_id=new_user.id, token=token)

    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="session_token", value=token, httponly=True, samesite="lax")
    return response


# --- LOGOUT ROUTE ---


@router.get("/logout")
def logout(session_token: str = Cookie(None), db: Session = Depends(get_db)):
    if session_token:
        # Delete session from SQLite database
        user_repo.delete_session(db, token=session_token)

    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("session_token")
    return response
