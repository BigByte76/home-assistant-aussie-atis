"""Data update coordinator for the Australian ATIS integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .atfm_parser import DailyPlan, carry_over_hours, parse_daily_plan
from .atis_parser import AirportInfo, parse_airport_page
from .const import (
    ATFM_REQUEST_TIMEOUT,
    ATFM_RETRY_INTERVAL,
    ATFM_SCAN_INTERVAL,
    ATFM_URL,
    BASE_URL,
    DOMAIN,
    REQUEST_TIMEOUT,
    SCAN_INTERVAL,
)

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


class AtfmCoordinator(DataUpdateCoordinator[DailyPlan]):
    """Fetch the ATFM Daily Plan every few hours.

    The plan covers a whole day, so after a failed download the last plan is
    kept (its hourly values are still valid) and the download is retried
    sooner than usual.
    """

    config_entry: AtisConfigEntry

    def __init__(self, hass: HomeAssistant, entry: AtisConfigEntry) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_atfm",
            update_interval=ATFM_SCAN_INTERVAL,
        )
        self._session = async_get_clientsession(hass)

    async def _async_update_data(self) -> DailyPlan:
        try:
            plan = await self._async_fetch()
        except UpdateFailed as err:
            self.update_interval = ATFM_RETRY_INTERVAL
            if self.data is None:
                raise
            _LOGGER.warning("Unable to update the ATFM Daily Plan, keeping the last one: %s", err)
            return self.data
        self.update_interval = ATFM_SCAN_INTERVAL
        if self.data is not None:
            carry_over_hours(self.data, plan, dt_util.utcnow())
        return plan

    async def _async_fetch(self) -> DailyPlan:
        try:
            async with self._session.get(
                ATFM_URL, timeout=aiohttp.ClientTimeout(total=ATFM_REQUEST_TIMEOUT)
            ) as response:
                response.raise_for_status()
                content = await response.read()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise UpdateFailed(f"Error fetching the ATFM Daily Plan: {err or type(err).__name__}") from err

        # Parsing a PDF takes a moment of CPU, so keep it off the event loop.
        plan = await self.hass.async_add_executor_job(parse_daily_plan, content)
        if not plan.airports:
            raise UpdateFailed("The ATFM Daily Plan has no airport pages that could be read")
        return plan
