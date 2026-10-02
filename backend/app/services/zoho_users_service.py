"""
Service for retrieving and caching Zoho Recruit active users,
matching emails, and deriving application roles without contacting Contacts module.
"""

import time
import asyncio
import logging
from typing import Any
import httpx

from app.core.config import get_settings
from app.infrastructure.zoho_auth import zoho_auth_manager
from app.infrastructure.retry import retry_async
from app.domain.exceptions import ZohoUsersUnavailableError

logger = logging.getLogger(__name__)


class ZohoUsersService:
    CACHE_TTL_SECONDS = 300  # 5 minutes

    def __init__(self) -> None:
        self._cached_users: list[dict[str, Any]] = []
        self._cache_timestamp: float = 0.0
        self._users_source: str = "unavailable"
        self._fallback_invoked: bool = False
        self._lock = asyncio.Lock()

    @property
    def users_source(self) -> str:
        """Returns 'live' if active users were fetched from Zoho, or 'unavailable' if unreachable."""
        return self._users_source

    @property
    def fallback_invoked(self) -> bool:
        """Indicates whether the fallback path was invoked due to Zoho API failure."""
        return self._fallback_invoked

    def invalidate_cache(self) -> None:
        self._cache_timestamp = 0.0
        self._cached_users = []
        self._fallback_invoked = False

    async def get_active_users(self, force_refresh: bool = False) -> list[dict[str, Any]]:
        """
        Fetches all active users from Zoho Recruit with pagination (per_page=200).
        Results are cached in memory for 5 minutes.
        Raises ZohoUsersUnavailableError if Zoho API fails or token lacks permissions.
        """
        now = time.time()
        if not force_refresh and self._cached_users and (now - self._cache_timestamp) < self.CACHE_TTL_SECONDS:
            return self._cached_users

        async with self._lock:
            now = time.time()
            if not force_refresh and self._cached_users and (now - self._cache_timestamp) < self.CACHE_TTL_SECONDS:
                return self._cached_users

            settings = get_settings()
            all_users: list[dict[str, Any]] = []
            page = 1
            per_page = 200

            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    while True:
                        url = f"{settings.zoho_recruit_base_url.rstrip('/')}/users"
                        params = {"type": "ActiveUsers", "page": page, "per_page": per_page}

                        async def _call() -> httpx.Response:
                            token = await zoho_auth_manager.get_access_token(client)
                            headers = {
                                "Authorization": f"Zoho-oauthtoken {token}",
                                "Accept": "application/json",
                            }
                            res = await client.get(url, params=params, headers=headers)
                            if res.status_code == 401:
                                # Token might be invalid, force refresh once
                                zoho_auth_manager.invalidate_token()
                                new_token = await zoho_auth_manager.get_access_token(client)
                                headers["Authorization"] = f"Zoho-oauthtoken {new_token}"
                                res = await client.get(url, params=params, headers=headers)
                            return res

                        response = await retry_async(_call)

                        if response.status_code == 204:
                            # No more records
                            break

                        if response.status_code != 200:
                            logger.error(
                                "Failed to fetch Zoho users HTTP %d: %s (source: unavailable)",
                                response.status_code,
                                response.text,
                            )
                            self._users_source = "unavailable"
                            self._cached_users = self._get_fallback_users()
                            raise ZohoUsersUnavailableError(
                                f"Zoho users API failed HTTP {response.status_code}: {response.text}"
                            )

                        data = response.json()
                        users_page = data.get("users", [])
                        if not users_page:
                            break

                        all_users.extend(users_page)

                        info = data.get("info", {})
                        more_records = info.get("more_records", False)
                        if not more_records or len(users_page) < per_page:
                            break

                        page += 1

            except ZohoUsersUnavailableError:
                raise
            except Exception as exc:
                logger.error("Exception connecting to Zoho users API: %s (source: unavailable)", exc)
                self._users_source = "unavailable"
                self._cached_users = self._get_fallback_users()
                raise ZohoUsersUnavailableError(f"Zoho users API connection error: {exc}") from exc

            self._users_source = "live"
            self._fallback_invoked = False
            self._cached_users = all_users
            self._cache_timestamp = time.time()
            logger.info("Successfully fetched %d active Zoho users (source: live).", len(all_users))
            return self._cached_users

    async def find_user_by_email(self, email: str) -> dict[str, Any] | None:
        """Finds an active Zoho user by email (case-insensitive). Raises ZohoUsersUnavailableError if Zoho is unavailable."""
        normalized = email.strip().lower()
        users = await self.get_active_users()
        for u in users:
            u_email = (u.get("email") or "").strip().lower()
            if u_email == normalized:
                # Check status
                status = (u.get("status") or "").lower()
                if status == "active":
                    return u
        return None

    def _get_fallback_users(self) -> list[dict[str, Any]]:
        """
        Invoked ONLY when Zoho Users API fails or is unreachable.
        Returns an empty list - NO fake or hardcoded test identities.
        Fails loudly rather than authenticating against stale mock users.
        """
        self._fallback_invoked = True
        return []

    def derive_user_role(self, user_record: dict[str, Any]) -> str | None:
        """Derives role from Zoho user profile and role objects."""
        settings = get_settings()
        profile_obj = user_record.get("profile") or {}
        role_obj = user_record.get("role") or {}

        profile_name = profile_obj.get("name") if isinstance(profile_obj, dict) else str(profile_obj)
        role_name = role_obj.get("name") if isinstance(role_obj, dict) else str(role_obj)

        return settings.derive_role(profile_name, role_name)


# Global singleton
zoho_users_service = ZohoUsersService()

