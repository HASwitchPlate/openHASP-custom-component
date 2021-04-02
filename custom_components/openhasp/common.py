"""HASP-LVGL Commonalities."""
import voluptuous as vol

from .const import HASP_IDLE_STATES

HASP_IDLE_SCHEMA = vol.Schema(vol.Any(*HASP_IDLE_STATES))
