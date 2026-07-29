"""FastAPI Auth Router for Google and GitHub OAuth and User Session Management."""

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.services.auth_service import AuthService
from core.storage.database import get_db_session
from server.middleware.auth import verify_api_key

router = APIRouter(prefix="/auth", tags=["auth"])


class OAuthExchangeRequest(BaseModel):
    provider: str
    code: str
    redirect_uri: str
    device_info: str | None = None


class UserProfileResponse(BaseModel):
    id: str
    email: str | None = None
    display_name: str
    avatar_url: str | None = None
    created_at: str
    last_login_at: str | None = None


class SessionResponse(BaseModel):
    id: str
    token_prefix: str
    device_info: str | None = None
    created_at: str
    expires_at: str | None = None


@router.get("/providers")
async def get_providers() -> dict[str, Any]:
    """Get status of configured OAuth providers."""
    return AuthService.get_providers_status()


@router.get("/{provider}/login")
async def oauth_login(provider: str, redirect_uri: str, state: str = "rip_auth") -> dict[str, str]:
    """Generate authorization redirect URL for specified provider."""
    try:
        url = AuthService.build_authorize_url(provider, redirect_uri, state)
        return {"provider": provider, "url": url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{provider}/callback")
async def oauth_browser_callback(
    provider: str,
    code: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
    state: str | None = None,
):
    """Handle browser GET redirect from OAuth provider (e.g. GitHub callback)."""
    ip_addr = request.client.host if request.client else None
    redirect_uri = str(request.url).split("?")[0]
    try:
        user, plaintext_token, session = await AuthService.exchange_code(
            db=db,
            provider=provider,
            code=code,
            redirect_uri=redirect_uri,
            device_info="Browser Callback",
            ip_address=ip_addr,
        )
        html_content = f"""
        <! illusion HTML >
        <html>
        <head>
            <title>RIP Authentication Success</title>
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0F172A; color: #F8FAFC; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; text-align: center; }}
                .card {{ background: #1E293B; border: 1px solid #334155; border-radius: 24px; padding: 32px; max-width: 440px; width: 100%; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }}
                .icon {{ font-size: 48px; margin-bottom: 16px; }}
                h2 {{ margin: 0 0 8px 0; color: #38BDF8; font-size: 24px; }}
                p {{ color: #94A3B8; font-size: 14px; line-height: 1.5; margin-bottom: 24px; }}
                .code-box {{ background: #090D16; border: 1px solid #334155; border-radius: 12px; padding: 12px; font-family: monospace; font-size: 13px; color: #38BDF8; word-break: break-all; margin-bottom: 20px; user-select: all; }}
                .btn {{ display: inline-block; background: #0EA5E9; color: white; text-decoration: none; font-weight: 600; padding: 12px 24px; border-radius: 12px; transition: all 0.2s; }}
                .btn:hover {{ background: #0284C7; }}
            </style>
        </head>
        <body>
            <div class="card">
                <div class="icon">🎉</div>
                <h2>Authentication Successful!</h2>
                <p>Welcome back, <strong>{user.display_name}</strong>. Your RIP Mobile App session is created.</p>
                <div class="code-box" id="token">{plaintext_token}</div>
                <a class="btn" href="riplink://oauth/callback?api_key={plaintext_token}">Open RIP Mobile App</a>
            </div>
        </body>
        </html>
        """
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=html_content)
    except Exception as e:
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=f"<h2>Authentication Failed</h2><p>{e}</p>", status_code=400)


@router.post("/{provider}/callback")
@router.post("/oauth/exchange")
async def oauth_exchange(
    req: OAuthExchangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Exchange OAuth code for user session token (`rip_...`)."""
    ip_addr = request.client.host if request.client else None
    try:
        user, plaintext_token, session = await AuthService.exchange_code(
            db=db,
            provider=req.provider,
            code=req.code,
            redirect_uri=req.redirect_uri,
            device_info=req.device_info,
            ip_address=ip_addr,
        )
        return {
            "status": "success",
            "api_key": plaintext_token,
            "token_type": "Bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "display_name": user.display_name,
                "avatar_url": user.avatar_url,
            },
            "session_id": session.id,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me", dependencies=[Depends(verify_api_key)])
async def get_current_user_profile(request: Request) -> dict[str, Any]:
    """Get currently logged-in user profile."""
    user = getattr(request.state, "user", None)
    if not user:
        # Legacy API key mode / Dev mode
        api_key = getattr(request.state, "api_key", None)
        return {
            "id": "system-user",
            "email": "dev@rip.local",
            "display_name": getattr(api_key, "name", "Developer"),
            "avatar_url": None,
            "auth_type": "api_key",
        }

    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "auth_type": "oauth",
    }


@router.post("/logout", dependencies=[Depends(verify_api_key)])
async def logout(request: Request, db: AsyncSession = Depends(get_db_session)) -> dict[str, str]:
    """Revoke active user session."""
    user_session = getattr(request.state, "user_session", None)
    if user_session:
        from datetime import datetime, timezone
        user_session.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    return {"status": "ok", "message": "Logged out successfully"}
