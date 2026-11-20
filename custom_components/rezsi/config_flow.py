"""Config and options flow for Rezsi kalkulátor."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    DateSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)
from homeassistant.util import dt as dt_util, slugify

from .const import (
    CONF_ELEC_MULT, CONF_EXPORT, CONF_GAS, CONF_GAS_MULT, CONF_IMPORT, CONF_OVERRIDES,
    CONF_PERIOD_START, CONF_RHD, CONF_SZALDO, DOMAIN, OVERRIDE_KEYS,
)

ENERGY = EntitySelector(EntitySelectorConfig(domain="sensor", device_class="energy"))
GAS = EntitySelector(EntitySelectorConfig(domain="sensor", device_class="gas"))
MULT = NumberSelector(NumberSelectorConfig(min=1, max=10, step=0.5, mode=NumberSelectorMode.BOX))
PRICE = NumberSelector(NumberSelectorConfig(min=0, step="any", mode=NumberSelectorMode.BOX))


class RezsiConfigFlow(ConfigFlow, domain=DOMAIN):
    """One entry per meter site."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            slug = slugify(user_input[CONF_NAME])
            # HA's slugify maps symbol-only names to "unknown", so check the name itself.
            if not slug or not any(c.isalnum() for c in user_input[CONF_NAME]):
                errors["base"] = "invalid_name"
        if user_input is not None and not errors:
            await self.async_set_unique_id(slug)
            self._abort_if_unique_id_configured()
            data = {k: v for k, v in user_input.items() if k != CONF_NAME}
            return self.async_create_entry(title=user_input[CONF_NAME], data=data)
        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,
                vol.Required(CONF_IMPORT): ENERGY,
                vol.Optional(CONF_EXPORT): ENERGY,
                vol.Optional(CONF_GAS): GAS,
                vol.Required(CONF_SZALDO, default=True): BooleanSelector(),
                vol.Optional(
                    CONF_PERIOD_START,
                    default=(dt_util.now().date() - timedelta(days=365)).isoformat(),
                ): DateSelector(),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> RezsiOptionsFlow:
        return RezsiOptionsFlow()


class RezsiOptionsFlow(OptionsFlow):
    """Multipliers, RHD switch and tariff overrides."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            overrides = {k: v for k, v in user_input.items() if k in OVERRIDE_KEYS and v not in (None, "")}
            base = {k: v for k, v in user_input.items() if k not in OVERRIDE_KEYS}
            return self.async_create_entry(data={**base, CONF_OVERRIDES: overrides})
        opts = self.config_entry.options
        ov = opts.get(CONF_OVERRIDES, {})
        fields: dict[Any, Any] = {
            vol.Required(CONF_SZALDO, default=opts.get(CONF_SZALDO, self.config_entry.data.get(CONF_SZALDO, True))): BooleanSelector(),
            vol.Required(CONF_ELEC_MULT, default=opts.get(CONF_ELEC_MULT, 1)): MULT,
            vol.Required(CONF_GAS_MULT, default=opts.get(CONF_GAS_MULT, 1)): MULT,
            vol.Required(CONF_RHD, default=opts.get(CONF_RHD, False)): BooleanSelector(),
        }
        for key in OVERRIDE_KEYS:
            fields[vol.Optional(key, description={"suggested_value": ov.get(key)})] = PRICE
        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields))
