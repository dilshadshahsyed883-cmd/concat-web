"""Concat Uploader: verified identity boundary and copied working ASGI backend."""
from contextlib import asynccontextmanager
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.auth import Principal, current_principal
from app.contracts.navigation import UPLOADER
from app.ui import render_page
from .gateway import page_response, resource_response, shutdown_backend


@asynccontextmanager
async def _lifecycle(app):
    try:
        yield
    finally:
        await shutdown_backend(app)


router = APIRouter(prefix="/concat-uploader", lifespan=_lifecycle)


@router.get("")
@router.get("/")
async def index(_: Principal = Depends(current_principal)):
    return RedirectResponse("/concat-uploader/sheets-sync", status_code=303)


async def _page(request: Request, principal: Principal, slug: str, idx: int):
    # Preserve the foundation shell while the owner-specific backend is OFF.
    # Once explicitly enabled, errors fail closed instead of serving a mock UI.
    if os.environ.get("CONCAT_UPLOADER_ENABLED") != "1":
        return render_page(request, principal, UPLOADER[idx])
    return await page_response(request, principal, slug)


@router.get("/sheets-sync")
async def sheets(request: Request, principal: Principal = Depends(current_principal)):
    return await _page(request, principal, "sheets-sync", 0)


@router.get("/channels")
async def channels(request: Request, principal: Principal = Depends(current_principal)):
    return await _page(request, principal, "channels", 1)


@router.get("/upload-engine")
async def upload_engine(request: Request, principal: Principal = Depends(current_principal)):
    return await _page(request, principal, "upload-engine", 2)


@router.get("/queue")
async def queue(request: Request, principal: Principal = Depends(current_principal)):
    return await _page(request, principal, "queue", 3)


@router.api_route("/{path:path}", methods=["GET", "HEAD", "POST"],
                  include_in_schema=False)
async def reused_uploader(request: Request, path: str,
                          principal: Principal = Depends(current_principal)):
    return await resource_response(request, principal, path)
