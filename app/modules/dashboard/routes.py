from fastapi import APIRouter, Depends, Request
from app.auth import Principal, current_principal
from app.contracts.navigation import DASHBOARD
from app.ui import render_page

router = APIRouter()

@router.get("/dashboard")
async def dashboard(request: Request, principal: Principal = Depends(current_principal)):
    return render_page(request, principal, DASHBOARD[0])
