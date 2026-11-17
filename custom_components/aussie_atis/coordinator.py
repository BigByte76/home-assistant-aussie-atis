"""Data update coordinator for the Australian ATIS integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .atfm_parser import DailyPlan, carry_over_hours, hours_to_json, parse_daily_plan, plan_from_hours_json
from .atis_parser import AirportInfo, parse_airport_page
from .const import (
    ATFM_REQUEST_TIMEOUT,
    ATFM_RETRY_INTERVAL,
    ATFM_SCAN_INTERVAL,
    ATFM_STORE_VERSION,
    ATFM_URL,
    BASE_URL,
    DOMAIN,
    REQUEST_TIMEOUT,
    SCAN_INTERVAL,
    atfm_store_key,
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

    The hours that haven't ended are saved after every download. The next
    day's plan replaces the current one for download in the evening, so after
    a restart the saved hours are the only source for the rest of today.
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
        self._store: Store[dict] = Store(hass, ATFM_STORE_VERSION, atfm_store_key(entry.entry_id))
        # Hours saved before the last restart, used once for the first plan.
        self._saved: DailyPlan | None = None
        self._loaded = False

    async def _async_update_data(self) -> DailyPlan:
        if not self._loaded:
            self._loaded = True
            stored = await self._store.async_load()
            if isinstance(stored, dict):
                self._saved = plan_from_hours_json(stored.get("hours"))
        try:
            plan = await self._async_fetch()
        except UpdateFailed as err:
            self.update_interval = ATFM_RETRY_INTERVAL
            if self.data is None:
                raise
            _LOGGER.warning("Unable to update the ATFM Daily Plan, keeping the last one: %s", err)
            return self.data
        self.update_interval = ATFM_SCAN_INTERVAL
        now = dt_util.utcnow()
        if (previous := self.data or self._saved) is not None:
            carry_over_hours(previous, plan, now)
        self._saved = None
        # Write errors are logged by Store and don't fail the update.
        await self._store.async_save({"hours": hours_to_json(plan, now)})
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
