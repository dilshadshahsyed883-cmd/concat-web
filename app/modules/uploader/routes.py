"""Concat Uploader: verified identity boundary and copied working ASGI backend."""
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.auth import Principal, current_principal
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


@router.get("/sheets-sync")
async def sheets(request: Request, principal: Principal = Depends(current_principal)):
    return await page_response(request, principal, "sheets-sync")


@router.get("/channels")
async def channels(request: Request, principal: Principal = Depends(current_principal)):
    return await page_response(request, principal, "channels")


@router.get("/upload-engine")
async def upload_engine(request: Request, principal: Principal = Depends(current_principal)):
    return await page_response(request, principal, "upload-engine")


@router.get("/queue")
async def queue(request: Request, principal: Principal = Depends(current_principal)):
    return await page_response(request, principal, "queue")


@router.api_route("/{path:path}", methods=["GET", "HEAD", "POST"],
                  include_in_schema=False)
async def reused_uploader(request: Request, path: str,
                          principal: Principal = Depends(current_principal)):
    return await resource_response(request, principal, path)
