"""Constants for the Rezsi kalkulátor integration."""

DOMAIN = "rezsi"

CONF_IMPORT = "import_entity"
CONF_EXPORT = "export_entity"
CONF_GAS = "gas_entity"
CONF_SZALDO = "szaldo"
CONF_PERIOD_START = "period_start"
CONF_ELEC_MULT = "elec_band_mult"
CONF_GAS_MULT = "gas_band_mult"
CONF_RHD = "rhd"
CONF_OVERRIDES = "overrides"

OVERRIDE_KEYS = (
    "electricity.reduced",
    "electricity.above",
    "electricity.band_kwh",
    "electricity.market",
    "electricity.feed_in",
    "gas.reduced",
    "gas.above",
    "gas.band_m3",
    "gas.market",
)
