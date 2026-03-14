"""Powerpal API client."""
import logging
from aiohttp import ClientSession

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://readings.powerpal.net/api/v1"


class PowerpalAuthenticationError(Exception):
    """Raised when API key is invalid (401)."""


class PowerpalAuthorizationError(Exception):
    """Raised when device ID is invalid (403)."""


class PowerpalError(Exception):
    """Generic Powerpal API error."""


class PowerpalApiClient:
    """Simple async client for Powerpal readings API."""

    def __init__(self, session: ClientSession, auth_key: str, device_id: str) -> None:
        self._session = session
        self._auth_key = auth_key
        self._device_id = device_id

    @property
    def device_id(self) -> str:
        return self._device_id

    async def _request(self, path: str, params: dict | None = None) -> dict | list:
        """Make an authenticated request to the Powerpal API."""
        url = f"{BASE_URL}{path}"
        headers = {
            "Authorization": self._auth_key,
            "Accept": "application/json",
        }
        try:
            async with self._session.get(url, headers=headers, params=params) as resp:
                if resp.status == 401:
                    raise PowerpalAuthenticationError("Invalid API key")
                if resp.status == 403:
                    raise PowerpalAuthorizationError("Invalid device ID")
                if resp.status != 200:
                    raise PowerpalError(f"API returned status {resp.status}")
                return await resp.json()
        except (PowerpalAuthenticationError, PowerpalAuthorizationError, PowerpalError):
            raise
        except Exception as err:
            raise PowerpalError(f"Error communicating with Powerpal API: {err}") from err

    async def get_device_data(self) -> dict:
        """Get current device status and totals."""
        return await self._request(f"/device/{self._device_id}")

    async def get_time_series(
        self,
        start: int | None = None,
        end: int | None = None,
        sample: int | None = None,
    ) -> list[dict]:
        """Get time series meter readings.

        Args:
            start: Unix timestamp for start of range.
            end: Unix timestamp for end of range.
            sample: Bucket size in minutes (e.g. 60 for hourly).

        Returns:
            List of reading dicts with timestamp, watt_hours, cost, etc.
            Limited to 50,000 records per request.
        """
        params = {}
        if start is not None:
            params["start"] = start
        if end is not None:
            params["end"] = end
        if sample is not None:
            params["sample"] = sample
        return await self._request(f"/meter_reading/{self._device_id}", params=params)
