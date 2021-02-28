"""Constants for HASP Open Hardware edition custom component."""

TOGGLE = ["off", "on"]
DOMAIN = "hasp-lvgl"
CONF_OBJID = "obj"
CONF_EVENT = "event"
CONF_TRACK = "track"
CONF_ENTITY = "entity"
CONF_TOPIC = "topic"
CONF_PAGES = "pages"
CONF_PAGES_PREV = "prev_obj"
CONF_PAGES_HOME = "home_obj"
CONF_PAGES_NEXT = "next_obj"
CONF_OBJECTS = "objects"
CONF_IDLE_BRIGHTNESS = "idle_brightness"
CONF_AWAKE_BRIGHTNESS = "awake_brightness"

DATA_SERVICE_MAP = "service_mapping"
DATA_ENTITY_MAP = "entity_mapping"
DATA_TOPIC = "topic"
DATA_PLATE_TOPIC = "plate_topic"
DATA_PAGE_ENTITY = "page_entity"

DEFAULT_TOPIC = "hasp"
DEFAULT_AWAKE_BRIGHNESS = 100
DEFAULT_IDLE_BRIGHNESS = 10


HASP_HOME_PAGE = 1
HASP_VAL = "val"
HASP_EVENT = "event"
HASP_EVENTS = "DOWN", "UP", "SHORT", "LONG"
HASP_IDLE_STATES = "OFF", "SHORT", "LONG"
