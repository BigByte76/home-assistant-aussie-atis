"""Config and options flows for the Australian ATIS integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import get_airports
from .const import AIRPORTS, CONF_AIRPORTS, DOMAIN


def _airports_schema(default: list[str]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_AIRPORTS, default=default): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=code, label=f"{code} – {name}")
                        for code, name in AIRPORTS.items()
                    ],
                    multiple=True,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            )
        }
    )


def _validate(user_input: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    """Return the de-duplicated selection and any form errors."""
    airports = list(dict.fromkeys(user_input.get(CONF_AIRPORTS, [])))
    return airports, ({} if airports else {"base": "no_airports"})


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
            airports, errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(title="Australian ATIS", data={CONF_AIRPORTS: airports})

        return self.async_show_form(step_id="user", data_schema=_airports_schema([]), errors=errors)


class AussieAtisOptionsFlow(OptionsFlow):
    """Change the monitored airports after setup."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the airport selection."""
        errors: dict[str, str] = {}
        if user_input is not None:
            airports, errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(data={CONF_AIRPORTS: airports})

        # Drop codes that are no longer offered (e.g. YGNB from v1.0.0).
        default = [code for code in get_airports(self.config_entry) if code in AIRPORTS]
        return self.async_show_form(step_id="init", data_schema=_airports_schema(default), errors=errors)
