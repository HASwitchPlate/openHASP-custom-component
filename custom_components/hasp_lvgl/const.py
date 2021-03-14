"""Constants for HASP Open Hardware edition custom component."""

TOGGLE = ["off", "on"]
DOMAIN = "hasp_lvgl"
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
DATA_IDLE = "idle"

DEFAULT_TOPIC = "hasp"
DEFAULT_AWAKE_BRIGHNESS = 100
DEFAULT_IDLE_BRIGHNESS = 10

HASP_HOME_PAGE = 1
HASP_VAL = "val"
HASP_EVENT = "event"
HASP_EVENT_ON = "on"
HASP_EVENT_OFF = "off"
HASP_EVENT_DOWN = "down"
HASP_EVENT_UP = "up"
HASP_EVENT_SHORT = "short"
HASP_EVENT_LONG = "long"
HASP_EVENTS = HASP_EVENT_ON, HASP_EVENT_OFF, HASP_EVENT_DOWN, HASP_EVENT_UP, HASP_EVENT_SHORT, HASP_EVENT_LONG
HASP_IDLE_OFF = "off"
HASP_IDLE_SHORT = "short"
HASP_IDLE_LONG = "long"
HASP_IDLE_STATES = HASP_IDLE_OFF, HASP_IDLE_SHORT, HASP_IDLE_LONG

ATTR_CURRENT_PAGE = "page"
ATTR_CURRENT_DIM = "dim"