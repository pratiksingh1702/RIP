"""Authentication service for OAuth logins and user session management."""

from __future__ import annotations

import os
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from dotenv import load_dotenv
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

load_dotenv()

from core.storage.models.user import User, UserOAuthAccount, UserSession


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def generate_session_token() -> tuple[str, str, str]:
    token = "rip_" + secrets.token_urlsafe(32)
    prefix = token[:10]
    token_hash = hash_token(token)
    return token, prefix, token_hash


class AuthService:
    """Service handling OAuth authentication flows and session creation."""

    # FULL REPOSITORY ACCESS SCOPE FOR GITHUB (repo, user:email, read:user, admin:repo_hook, workflow)
    GITHUB_SCOPES = ["repo", "user:email", "read:user", "admin:repo_hook", "workflow"]
    GOOGLE_SCOPES = ["openid", "email", "profile"]

    @classmethod
    def get_github_client_id(cls) -> str:
        return os.getenv("GITHUB_CLIENT_ID", "").strip()

    @classmethod
    def get_github_client_secret(cls) -> str:
        return os.getenv("GITHUB_CLIENT_SECRET", "").strip()

    @classmethod
    def get_google_client_id(cls) -> str:
        return os.getenv("GOOGLE_CLIENT_ID", "").strip()

    @classmethod
    def get_google_client_secret(cls) -> str:
        return os.getenv("GOOGLE_CLIENT_SECRET", "").strip()

    @classmethod
    def get_providers_status(cls) -> dict[str, Any]:
        """Check which OAuth providers are configured."""
        gh_id = cls.get_github_client_id()
        goog_id = cls.get_google_client_id()
        return {
            "github": {
                "enabled": bool(gh_id),
                "client_id": gh_id,
                "scopes": cls.GITHUB_SCOPES,
            },
            "google": {
                "enabled": bool(goog_id),
                "client_id": goog_id,
                "scopes": cls.GOOGLE_SCOPES,
            },
        }

    @classmethod
    def build_authorize_url(cls, provider: str, redirect_uri: str, state: str) -> str:
        """Build the OAuth authorization URL for the user to visit."""
        provider = provider.lower().strip()
        if provider == "github":
            client_id = cls.get_github_client_id()
            scope_str = "%20".join(cls.GITHUB_SCOPES)
            return (
                f"https://github.com/login/oauth/authorize"
                f"?client_id={client_id}"
                f"&redirect_uri={redirect_uri}"
                f"&scope={scope_str}"
                f"&state={state}"
            )
        elif provider == "google":
            client_id = cls.get_google_client_id()
            scope_str = "%20".join(cls.GOOGLE_SCOPES)
            return (
                f"https://accounts.google.com/o/oauth2/v2/auth"
                f"?client_id={client_id}"
                f"&redirect_uri={redirect_uri}"
                f"&response_type=code"
                f"&scope={scope_str}"
                f"&state={state}"
                f"&access_type=offline"
                f"&prompt=consent"
            )
        else:
            raise ValueError(f"Unsupported OAuth provider: '{provider}'")

    @classmethod
    async def exchange_code(
        cls,
        db: AsyncSession,
        provider: str,
        code: str,
        redirect_uri: str,
        device_info: str | None = None,
        ip_address: str | None = None,
    ) -> tuple[User, str, UserSession]:
        """Exchange OAuth authorization code for tokens, fetch profile, and create User Session."""
        provider = provider.lower().strip()
        if provider == "github":
            return await cls._handle_github_exchange(db, code, redirect_uri, device_info, ip_address)
        elif provider == "google":
            return await cls._handle_google_exchange(db, code, redirect_uri, device_info, ip_address)
        else:
            raise ValueError(f"Unsupported OAuth provider: '{provider}'")

    @classmethod
    async def _handle_github_exchange(
        cls,
        db: AsyncSession,
        code: str,
        redirect_uri: str,
        device_info: str | None,
        ip_address: str | None,
    ) -> tuple[User, str, UserSession]:
        """Exchange GitHub OAuth code for access token with full repo scope."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Exchange code for access token
            token_resp = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": cls.get_github_client_id(),
                    "client_secret": cls.get_github_client_secret(),
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            scopes_granted = token_data.get("scope", "")

            if not access_token:
                err = token_data.get("error_description") or token_data.get("error") or "Failed to obtain GitHub access token"
                raise RuntimeError(f"GitHub OAuth error: {err}")

            # 2. Fetch user profile from GitHub
            user_resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}", "User-Agent": "RIP-Platform"},
            )
            user_info = user_resp.json()
            provider_user_id = str(user_info.get("id"))
            username = user_info.get("login", "")
            display_name = user_info.get("name") or username
            avatar_url = user_info.get("avatar_url")
            email = user_info.get("email")

            # If email is missing, fetch user emails
            if not email:
                try:
                    emails_resp = await client.get(
                        "https://api.github.com/user/emails",
                        headers={"Authorization": f"Bearer {access_token}", "User-Agent": "RIP-Platform"},
                    )
                    emails = emails_resp.json()
                    if isinstance(emails, list):
                        primary_email = next((e["email"] for e in emails if e.get("primary")), None)
                        email = primary_email or (emails[0]["email"] if emails else None)
                except Exception:
                    pass

        return await cls._upsert_user_and_create_session(
            db=db,
            provider="github",
            provider_user_id=provider_user_id,
            provider_username=username,
            provider_email=email,
            display_name=display_name,
            avatar_url=avatar_url,
            access_token=access_token,
            refresh_token=None,
            scopes=scopes_granted or ",".join(cls.GITHUB_SCOPES),
            device_info=device_info,
            ip_address=ip_address,
        )

    @classmethod
    async def _handle_google_exchange(
        cls,
        db: AsyncSession,
        code: str,
        redirect_uri: str,
        device_info: str | None,
        ip_address: str | None,
    ) -> tuple[User, str, UserSession]:
        """Exchange Google OAuth code for ID & Access Tokens."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Exchange code for access token
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": cls.get_google_client_id(),
                    "client_secret": cls.get_google_client_secret(),
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_data = token_resp.json()
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")
            scopes_granted = token_data.get("scope", "")

            if not access_token:
                err = token_data.get("error_description") or token_data.get("error") or "Failed to obtain Google access token"
                raise RuntimeError(f"Google OAuth error: {err}")

            # 2. Fetch user profile from Google UserInfo
            user_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_info = user_resp.json()
            provider_user_id = str(user_info.get("sub"))
            email = user_info.get("email")
            display_name = user_info.get("name") or email or "Google User"
            avatar_url = user_info.get("picture")

        return await cls._upsert_user_and_create_session(
            db=db,
            provider="google",
            provider_user_id=provider_user_id,
            provider_username=email,
            provider_email=email,
            display_name=display_name,
            avatar_url=avatar_url,
            access_token=access_token,
            refresh_token=refresh_token,
            scopes=scopes_granted or ",".join(cls.GOOGLE_SCOPES),
            device_info=device_info,
            ip_address=ip_address,
        )

    @classmethod
    async def _upsert_user_and_create_session(
        cls,
        db: AsyncSession,
        provider: str,
        provider_user_id: str,
        provider_username: str | None,
        provider_email: str | None,
        display_name: str,
        avatar_url: str | None,
        access_token: str | None,
        refresh_token: str | None,
        scopes: str | None,
        device_info: str | None,
        ip_address: str | None,
    ) -> tuple[User, str, UserSession]:
        """Find or create User & UserOAuthAccount, then mint UserSession."""
        now = utc_now()
        
        # Check if OAuth account exists
        stmt = select(UserOAuthAccount).where(
            UserOAuthAccount.provider == provider,
            UserOAuthAccount.provider_user_id == provider_user_id,
        )
        res = await db.execute(stmt)
        oauth_acct = res.scalar_one_or_none()

        if oauth_acct:
            user_stmt = select(User).where(User.id == oauth_acct.user_id)
            user_res = await db.execute(user_stmt)
            user = user_res.scalar_one()

            # Update profile info
            user.display_name = display_name
            if avatar_url:
                user.avatar_url = avatar_url
            if provider_email:
                user.email = provider_email
            user.last_login_at = now

            # Update OAuth account tokens & scope
            oauth_acct.access_token = access_token
            if refresh_token:
                oauth_acct.refresh_token = refresh_token
            oauth_acct.scopes = scopes
            oauth_acct.provider_email = provider_email
            oauth_acct.provider_username = provider_username
            oauth_acct.provider_avatar_url = avatar_url
        else:
            # Check if User exists by email
            user = None
            if provider_email:
                u_stmt = select(User).where(User.email == provider_email)
                u_res = await db.execute(u_stmt)
                user = u_res.scalar_one_or_none()

            if not user:
                user = User(
                    email=provider_email,
                    display_name=display_name,
                    avatar_url=avatar_url,
                    is_active=True,
                    created_at=now,
                    last_login_at=now,
                )
                db.add(user)
                await db.flush()

            oauth_acct = UserOAuthAccount(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=provider_email,
                provider_username=provider_username,
                provider_avatar_url=avatar_url,
                access_token=access_token,
                refresh_token=refresh_token,
                scopes=scopes,
                created_at=now,
            )
            db.add(oauth_acct)

        # Generate UserSession (API key for mobile client)
        plaintext_token, prefix, token_hash = generate_session_token()
        session = UserSession(
            user_id=user.id,
            token_hash=token_hash,
            token_prefix=prefix,
            device_info=device_info,
            ip_address=ip_address,
            created_at=now,
            expires_at=now + timedelta(days=90),
        )
        db.add(session)
        await db.commit()
        await db.refresh(user)
        await db.refresh(session)

        return user, plaintext_token, session

    @classmethod
    async def verify_user_session(cls, db: AsyncSession, plaintext_token: str) -> tuple[User, UserSession] | None:
        """Verify user session token."""
        token_h = hash_token(plaintext_token)
        now = utc_now()

        stmt = select(UserSession, User).join(User, UserSession.user_id == User.id).where(
            UserSession.token_hash == token_h,
            UserSession.revoked_at.is_(None),
            User.is_active == True,
        )
        res = await db.execute(stmt)
        row = res.first()
        if not row:
            return None

        session, user = row
        if session.expires_at and now > session.expires_at:
            return None

        return user, session
