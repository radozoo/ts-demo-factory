"""Bearer token acquisition and caching for ThoughtSpot REST API v2."""
import time
import requests
from config.settings import Settings


class ThoughtSpotAuth:
    """Manages Bearer token lifecycle with automatic re-auth on expiry."""

    TOKEN_TTL_SECONDS = 3600  # conservative; TS tokens are valid 1h by default

    def __init__(self, settings: Settings):
        self._settings = settings
        self._token: str | None = None
        self._token_acquired_at: float = 0.0

    def get_token(self) -> str:
        """Return a valid Bearer token, refreshing if expired."""
        if self._token and not self._is_expired():
            return self._token
        self._token = self._acquire_token()
        self._token_acquired_at = time.monotonic()
        return self._token

    def invalidate(self) -> None:
        """Force token refresh on next call (e.g. after 401)."""
        self._token = None

    def _is_expired(self) -> bool:
        elapsed = time.monotonic() - self._token_acquired_at
        return elapsed >= self.TOKEN_TTL_SECONDS

    def _acquire_token(self) -> str:
        s = self._settings
        url = f"{s.ts_host}/api/rest/2.0/auth/token/full"
        payload = {
            "username": s.ts_username,
            "password": s.ts_password,
            "validity_time_in_sec": self.TOKEN_TTL_SECONDS,
        }
        if s.ts_org_id != 0:
            payload["org_id"] = s.ts_org_id

        resp = requests.post(url, json=payload, timeout=30)
        if not resp.ok:
            raise RuntimeError(
                f"Token acquisition failed [{resp.status_code}]: {resp.text[:400]}"
            )
        data = resp.json()
        token = data.get("token")
        if not token:
            raise RuntimeError(f"No 'token' in auth response: {data}")
        return token
