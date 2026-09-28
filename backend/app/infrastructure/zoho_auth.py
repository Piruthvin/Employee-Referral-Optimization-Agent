"""
Zoho OAuth2 token management.
Handles thread-safe caching, proactive refresh before expiry, and forced invalidation on 401.
"""

import time
import asyncio
import logging
import httpx
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class ZohoAuthManager:
    """Manages Zoho OAuth2 access tokens for India DC or configured region."""

    def __init__(self) -> None:
        self._access_token: str | None = None
        self._token_expiry: float = 0.0
        self._lock = asyncio.Lock()

    def invalidate_token(self) -> None:
        """Forces the cached token to be considered expired, triggering refresh on next call."""
        self._access_token = None
        self._token_expiry = 0.0
        logger.info("Zoho access token cache invalidated.")

    async def get_access_token(self, client: httpx.AsyncClient | None = None) -> str:
        """
        Retrieves a valid Zoho access token, refreshing if missing or expiring within 60s.
        """
        now = time.time()
        # Fast path if valid with 60 second buffer
        if self._access_token and now < (self._token_expiry - 60):
            return self._access_token

        async with self._lock:
            # Double-check inside lock
            now = time.time()
            if self._access_token and now < (self._token_expiry - 60):
                return self._access_token

            settings = get_settings()
            if not settings.zoho_client_id or not settings.zoho_client_secret or not settings.zoho_refresh_token:
                raise ValueError("Zoho OAuth credentials (client_id, client_secret, refresh_token) are not configured.")

            token_url = f"{settings.zoho_accounts_base_url.rstrip('/')}/oauth/v2/token"
            data = {
                "grant_type": "refresh_token",
                "client_id": settings.zoho_client_id,
                "client_secret": settings.zoho_client_secret,
                "refresh_token": settings.zoho_refresh_token,
            }

            logger.info("Refreshing Zoho access token from %s", token_url)
            created_client = False
            http_client = client
            if http_client is None:
                http_client = httpx.AsyncClient(timeout=15.0)
                created_client = True

            try:
                resp = await http_client.post(token_url, data=data)
                if resp.status_code != 200:
                    logger.error("Zoho token refresh failed HTTP %d: %s", resp.status_code, resp.text)
                    raise RuntimeError(f"Zoho token refresh failed HTTP {resp.status_code}: {resp.text}")

                resp_data = resp.json()
                access_token = resp_data.get("access_token")
                if not access_token:
                    logger.error("Zoho token response missing access_token: %s", resp_data)
                    raise RuntimeError(f"Zoho token response invalid: {resp_data}")

                expires_in = int(resp_data.get("expires_in", 3600))
                self._access_token = access_token
                self._token_expiry = time.time() + expires_in
                logger.info("Successfully refreshed Zoho access token, valid for %d seconds.", expires_in)
                return self._access_token
            finally:
                if created_client and http_client:
                    await http_client.aclose()


# Global singleton
zoho_auth_manager = ZohoAuthManager()


async def get_zoho_access_token() -> str:
    return await zoho_auth_manager.get_access_token()
