from fastapi import APIRouter, Depends, Request
from app.auth import Principal, admin_principal
from app.contracts.navigation import ADMIN
from app.ui import render_page

router = APIRouter()

@router.get("/admin")
async def admin(request: Request, principal: Principal = Depends(admin_principal)):
    return render_page(request, principal, ADMIN[0])
