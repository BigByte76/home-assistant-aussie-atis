"""Data update coordinator for the Australian ATIS integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .atis_parser import AirportInfo, parse_airport_page
from .const import BASE_URL, DOMAIN, REQUEST_TIMEOUT, SCAN_INTERVAL

if TYPE_CHECKING:
    from . import AtisConfigEntry

_LOGGER = logging.getLogger(__name__)


class AtisCoordinator(DataUpdateCoordinator[dict[str, AirportInfo]]):
    """Fetch ATIS, METAR and TAF for every configured airport in one update.

    ``data`` maps ICAO code to the latest parsed info. An airport that failed in
    the most recent update is left out, so its entities go unavailable. The
    update as a whole only fails when every airport fails.
    """

    config_entry: AtisConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AtisConfigEntry, airports: list[str]) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.airports = airports
        self._session = async_get_clientsession(hass)
        self._failing: set[str] = set()

    async def _async_update_data(self) -> dict[str, AirportInfo]:
        results = await asyncio.gather(
            *(self._async_fetch(code) for code in self.airports),
            return_exceptions=True,
        )

        data: dict[str, AirportInfo] = {}
        for code, result in zip(self.airports, results, strict=True):
            if isinstance(result, BaseException):
                if code not in self._failing:
                    _LOGGER.warning("Unable to update ATIS for %s: %s", code, result)
                    self._failing.add(code)
                continue
            if code in self._failing:
                _LOGGER.info("ATIS for %s is available again", code)
                self._failing.discard(code)
            data[code] = result

        if self.airports and not data:
            raise UpdateFailed("Unable to reach aussieadsb.com for any configured airport")
        return data

    async def _async_fetch(self, code: str) -> AirportInfo:
        url = BASE_URL.format(code=code.lower())
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
            ) as response:
                response.raise_for_status()
                page = await response.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Error fetching {url}: {err or type(err).__name__}") from err
        return parse_airport_page(page)
