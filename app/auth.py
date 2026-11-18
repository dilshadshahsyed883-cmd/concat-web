"""Fail-closed verified identity contract. Untrusted headers are NEVER accepted."""
from dataclasses import dataclass
import inspect
from typing import Awaitable, Callable, Optional, Union
from fastapi import Depends, HTTPException, Request

@dataclass(frozen=True, slots=True)
class Principal:
    username: str
    is_admin: bool = False
    is_active: bool = False
    concat_granted: bool = False

    def valid(self) -> bool:
        return (bool(self.username) and self.username == self.username.strip()
                and len(self.username) <= 128 and
                not any(ord(c) < 33 or c in "/\\:" for c in self.username))

IdentityResolver = Callable[[Request], Union[Optional[Principal], Awaitable[Optional[Principal]]]]

async def current_principal(request: Request) -> Principal:
    resolver: Optional[IdentityResolver] = getattr(request.app.state, "identity_resolver", None)
    if resolver is None:
        raise HTTPException(status_code=401, detail="Verified authentication not connected")
    principal = resolver(request)
    if inspect.isawaitable(principal):
        principal = await principal
    if not isinstance(principal, Principal) or not principal.valid() or not principal.is_active:
        raise HTTPException(status_code=401, detail="Active authenticated session required")
    if not principal.concat_granted:
        raise HTTPException(status_code=403, detail="Concat Web access not granted")
    return principal

async def admin_principal(principal: Principal = Depends(current_principal)) -> Principal:
    if not principal.is_admin:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return principal
