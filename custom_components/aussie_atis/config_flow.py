"""Config and options flows for the Australian ATIS integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import get_airports, get_atfm_enabled
from .const import AIRPORTS, CONF_AIRPORTS, CONF_ATFM, DOMAIN


def _schema(airports: list[str], atfm: bool) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_AIRPORTS, default=airports): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=code, label=f"{code} – {name}")
                        for code, name in AIRPORTS.items()
                    ],
                    multiple=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(CONF_ATFM, default=atfm): BooleanSelector(),
        }
    )


def _validate(user_input: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
    """Return the entry data (de-duplicated selection) and any form errors."""
    airports = list(dict.fromkeys(user_input.get(CONF_AIRPORTS, [])))
    data = {CONF_AIRPORTS: airports, CONF_ATFM: bool(user_input.get(CONF_ATFM, False))}
    return data, ({} if airports else {"base": "no_airports"})


class AussieAtisConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AussieAtisOptionsFlow:
        """Return the options flow handler."""
        return AussieAtisOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Pick the airports to monitor."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(title="Australian ATIS", data=data)

        return self.async_show_form(step_id="user", data_schema=_schema([], False), errors=errors)


class AussieAtisOptionsFlow(OptionsFlow):
    """Change the monitored airports and the ATFM Daily Plan after setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the airport selection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            data, errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(data=data)

        # Drop codes that are no longer offered (e.g. YGNB from v1.0.0).
        default = [code for code in get_airports(self.config_entry) if code in AIRPORTS]
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(default, get_atfm_enabled(self.config_entry)),
            errors=errors,
        )
