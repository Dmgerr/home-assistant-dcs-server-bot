"""Constants for the DCS Server Bot integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "dcs_server_bot"
NAME = "DCS Server Bot Operations Center"
CONFIGURATION_URL = f"homeassistant://config/integrations/integration/{DOMAIN}"

CONF_URL = "url"
CONF_API_KEY = "api_key"
CONF_VERIFY_SSL = "verify_ssl"
CONF_ENABLE_CONTROL = "enable_control"
CONF_ENABLE_MODERATION = "enable_moderation"
CONF_MODERATION_URL = "moderation_url"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_URL = "http://localhost:9876"
DEFAULT_VERIFY_SSL = True
DEFAULT_ENABLE_CONTROL = False
DEFAULT_ENABLE_MODERATION = False
DEFAULT_MODERATION_URL = ""
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 300

DEFAULT_TIMEOUT = 15
CONTROL_TIMEOUT = 600
UPDATE_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
STATISTICS_INTERVAL = timedelta(minutes=15)

EVENT_SERVER_STATUS_CHANGED = f"{DOMAIN}_server_status_changed"
EVENT_PLAYER_JOINED = f"{DOMAIN}_player_joined"
EVENT_PLAYER_LEFT = f"{DOMAIN}_player_left"

SERVICE_START_SERVER = "start_server"
SERVICE_STOP_SERVER = "stop_server"
SERVICE_RESTART_SERVER = "restart_server"
SERVICE_PAUSE_MISSION = "pause_mission"
SERVICE_RESUME_MISSION = "resume_mission"
SERVICE_RESTART_MISSION = "restart_mission"
SERVICE_LOAD_MISSION = "load_mission"
SERVICE_KICK_PLAYER = "kick_player"
SERVICE_BAN_PLAYER = "ban_player"
SERVICE_UNBAN_PLAYER = "unban_player"

ATTR_SERVER_NAME = "server_name"
ATTR_MISSION_NAME = "mission_name"
ATTR_ENTRY_ID = "entry_id"
ATTR_PLAYER_NAME = "player_name"
ATTR_REASON = "reason"
ATTR_DAYS = "days"

CONTROL_ENDPOINTS: dict[str, str] = {
    SERVICE_START_SERVER: "/instance/start",
    SERVICE_STOP_SERVER: "/instance/stop",
    SERVICE_RESTART_SERVER: "/instance/restart",
    SERVICE_PAUSE_MISSION: "/instance/mission/pause",
    SERVICE_RESUME_MISSION: "/instance/mission/unpause",
    SERVICE_RESTART_MISSION: "/instance/mission/restart",
    SERVICE_LOAD_MISSION: "/instance/mission/load",
}

RUNNING_STATES = {"running", "paused"}
