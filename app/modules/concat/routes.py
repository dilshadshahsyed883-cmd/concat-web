from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from app.auth import Principal, current_principal
from app.contracts.navigation import CONCAT
from app.ui import render_page

router = APIRouter(prefix="/concat")

@router.get("")
@router.get("/")
async def index(_: Principal = Depends(current_principal)):
    return RedirectResponse("/concat/production", status_code=303)

@router.get("/production")
async def production(request: Request, principal: Principal = Depends(current_principal)):
    return render_page(request, principal, CONCAT[0])

@router.get("/media")
async def media(request: Request, principal: Principal = Depends(current_principal)):
    return render_page(request, principal, CONCAT[1])

@router.get("/gpu-config")
async def gpu_config(request: Request, principal: Principal = Depends(current_principal)):
    return render_page(request, principal, CONCAT[2])
