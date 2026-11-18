from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from app.auth import Principal, current_principal
from app.contracts.navigation import UPLOADER
from app.ui import render_page

router = APIRouter(prefix="/concat-uploader")

@router.get("")
@router.get("/")
async def index(_: Principal = Depends(current_principal)):
    return RedirectResponse("/concat-uploader/sheets-sync", status_code=303)

@router.get("/sheets-sync")
async def sheets(request: Request, principal: Principal = Depends(current_principal)):
    return render_page(request, principal, UPLOADER[0])

@router.get("/channels")
async def channels(request: Request, principal: Principal = Depends(current_principal)):
    return render_page(request, principal, UPLOADER[1])

@router.get("/upload-engine")
async def upload_engine(request: Request, principal: Principal = Depends(current_principal)):
    return render_page(request, principal, UPLOADER[2])

@router.get("/queue")
async def queue(request: Request, principal: Principal = Depends(current_principal)):
    return render_page(request, principal, UPLOADER[3])
