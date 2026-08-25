"""Async client for the ModBridge REST API.

Talks to a running ModBridge server (https://github.com/Xerolux/modbridge).
Authentication uses the session_token cookie issued by POST /api/login plus a
CSRF token (cookie + X-CSRF-Token header) required for state-changing calls.
Cookies are managed manually so the client also works with IP-address hosts.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp
from aiohttp import ClientError, ClientResponseError

from .const import MIN_TIME_BETWEEN_LOGIN

_LOGGER = logging.getLogger(__name__)


class ModBridgeError(Exception):
    """Base exception for ModBridge errors."""


class ModBridgeConnectionError(ModBridgeError):
    """Raised when the ModBridge server cannot be reached."""


class ModBridgeAuthError(ModBridgeError):
    """Raised when authentication fails (bad credentials)."""


class ModBridgePasswordChangeRequiredError(ModBridgeAuthError):
    """Raised when the account must change its password before API access."""


class ModBridgeApiError(ModBridgeError):
    """Raised when the ModBridge API returns an unexpected error."""


class ModBridgeClient:
    """Small async wrapper around the ModBridge HTTP API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        username: str,
        password: str,
        use_tls: bool = False,
        verify_ssl: bool = True,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._verify_ssl = verify_ssl
        self._session_token: str | None = None
        self._csrf_token: str | None = None
        self._last_login = 0.0
        scheme = "https" if use_tls else "http"
        self._base_url = f"{scheme}://{host}:{port}"

    @property
    def base_url(self) -> str:
        """Return the base URL of the ModBridge server."""
        return self._base_url

    @property
    def host(self) -> str:
        """Return the ModBridge host."""
        return self._host

    @staticmethod
    def _extract_cookie(response: aiohttp.ClientResponse, name: str) -> str | None:
        """Extract a cookie value from the response Set-Cookie headers."""
        if name in response.cookies:
            morsel = response.cookies[name]
            if morsel.value:
                return morsel.value
        return None

    async def close(self) -> None:
        """Best-effort logout. Safe to call without an open session."""
        if not self._session_token:
            return
        headers = {"Cookie": f"session_token={self._session_token}"}
        if self._csrf_token:
            headers["X-CSRF-Token"] = self._csrf_token
        try:
            async with self._session.post(
                f"{self._base_url}/api/logout",
                data=b"",
                headers=headers,
                ssl=self._verify_ssl,
            ) as resp:
                _LOGGER.debug("ModBridge logout: %s", resp.status)
        except (ClientError, TimeoutError):
            pass
        finally:
            self._session_token = None
            self._csrf_token = None

    async def login(self) -> None:
        """Authenticate and store session + CSRF tokens.

        The {username, password} payload works in both multi-user mode and the
        legacy single-user mode (which ignores the username field).
        """
        now = time.monotonic()
        wait = MIN_TIME_BETWEEN_LOGIN - (now - self._last_login)
        if wait > 0:
            # Respect the ModBridge login rate limit (5/min) by waiting out
            # the window instead of hammering the endpoint.
            _LOGGER.debug("Login throttled, waiting %.1fs", wait)
            await asyncio.sleep(wait)
        self._last_login = time.monotonic()

        payload = {"username": self._username, "password": self._password}
        try:
            async with self._session.post(
                f"{self._base_url}/api/login",
                json=payload,
                ssl=self._verify_ssl,
            ) as resp:
                if resp.status == 401:
                    raise ModBridgeAuthError("Invalid credentials")
                if resp.status == 429:
                    raise ModBridgeApiError("Login rate limited by ModBridge")
                resp.raise_for_status()
                self._session_token = self._extract_cookie(resp, "session_token")
                self._csrf_token = self._extract_cookie(resp, "csrf_token")
        except ClientResponseError as err:
            raise ModBridgeApiError(f"Login failed: {err.message}") from err
        except (ClientError, TimeoutError) as err:
            raise ModBridgeConnectionError(f"Cannot reach ModBridge: {err}") from err

        if not self._session_token or not self._csrf_token:
            raise ModBridgeApiError("ModBridge did not issue session cookies")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        auth: bool = True,
        json: Any | None = None,
        retried: bool = False,
    ) -> Any:
        """Perform an API request with automatic re-login on expired sessions."""
        headers: dict[str, str] = {}
        if auth:
            if not self._session_token:
                await self.login()
            headers["Cookie"] = f"session_token={self._session_token}"
            if self._csrf_token and method != "GET":
                headers["X-CSRF-Token"] = self._csrf_token

        url = f"{self._base_url}{path}"
        try:
            async with self._session.request(
                method,
                url,
                json=json,
                headers=headers,
                ssl=self._verify_ssl,
            ) as resp:
                if resp.status in (401, 403) and auth:
                    body = await resp.text()
                    if "password change required" in body.lower():
                        raise ModBridgePasswordChangeRequiredError(
                            "ModBridge requires a password change before API access; "
                            "log in to the ModBridge WebUI once and change the password"
                        )
                    if not retried and (
                        resp.status == 401 or "invalid csrf token" in body.lower()
                    ):
                        # Session expired or CSRF token stale -> re-login + retry.
                        self._session_token = None
                        self._csrf_token = None
                        await self.login()
                        return await self._request(method, path, json=json, retried=True)
                if resp.status == 401:
                    raise ModBridgeAuthError("Session expired")
                resp.raise_for_status()

                if resp.content_type == "application/json":
                    return await resp.json()
                return None
        except ClientResponseError as err:
            raise ModBridgeApiError(
                f"{method} {path} failed: {err.message} ({err.status})"
            ) from err
        except ModBridgeError:
            raise
        except (ClientError, TimeoutError) as err:
            raise ModBridgeConnectionError(f"Cannot reach ModBridge: {err}") from err

    async def async_change_password(self, current: str, new: str) -> None:
        """Change the password of the logged-in user and re-login."""
        await self._request(
            "POST",
            "/api/config/password",
            json={"current_password": current, "new_password": new},
        )
        self._password = new
        self._session_token = None
        self._csrf_token = None
        await self.login()

    async def async_get_status(self) -> dict[str, Any]:
        """Fetch the public status endpoint (no auth required)."""
        return await self._request("GET", "/api/status", auth=False)

    async def async_get_proxies(self) -> list[dict[str, Any]]:
        """Fetch all proxies including live statistics (requires auth)."""
        data = await self._request("GET", "/api/proxies")
        if isinstance(data, list):
            return data
        return []

    async def async_get_system_info(self) -> dict[str, Any]:
        """Fetch server runtime info (requires auth)."""
        data = await self._request("GET", "/api/system/info")
        return data if isinstance(data, dict) else {}

    async def async_get_version(self) -> str | None:
        """Fetch the ModBridge server version.

        Uses /api/update/check which reports current_version. The endpoint
        also contacts GitHub; a 502 means the check failed but the version
        is still reported, other failures return None.
        """
        try:
            data = await self._request("GET", "/api/update/check")
        except ModBridgeError:
            # Version detection must never break the update cycle.
            return None
        if isinstance(data, dict):
            version = data.get("current_version")
            if version:
                return str(version)
        return None

    async def async_control_proxy(self, proxy_id: str, action: str) -> None:
        """Run a control action for a single proxy."""
        await self._request(
            "POST",
            "/api/proxies/control",
            json={"id": proxy_id, "action": action},
        )

    async def async_control_all(self, action: str) -> None:
        """Run a bulk control action (start_all/stop_all/restart_all)."""
        await self._request(
            "POST",
            "/api/proxies/control",
            json={"action": action},
        )

    async def async_restart_system(self) -> None:
        """Restart the ModBridge server process."""
        await self._request(
            "POST",
            "/api/system/restart",
            json={},
        )
