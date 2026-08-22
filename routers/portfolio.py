from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from core.dependencies import get_current_user
from db.session import get_db
from models.user import User

templates = Jinja2Templates(directory="templates")
router = APIRouter(tags=["portfolio"])


@router.get("/", response_class=HTMLResponse)
def show_dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from services.dashboard_service import get_dashboard_context

    context_obj = get_dashboard_context(db, user)
    context = context_obj.model_dump()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "context": context},
    )
