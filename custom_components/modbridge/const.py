"""Constants for the ModBridge integration.

The integration version is always kept in sync with the upstream ModBridge
project (https://github.com/Xerolux/modbridge). The single source of truth is
the "version" key in manifest.json, which mirrors modbridge/version.txt.
"""

import json
from pathlib import Path

DOMAIN = "modbridge"
MANUFACTURER = "Xerolux"

# Version is read from the manifest so it always matches the upstream release.
VERSION = json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))[
    "version"
]

CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_USE_TLS = "use_tls"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_PORT = 8080
DEFAULT_USERNAME = "admin"
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 10
MAX_SCAN_INTERVAL = 3600

# ModBridge proxy states
STATUS_RUNNING = "Running"
STATUS_STOPPED = "Stopped"
STATUS_ERROR = "Error"

ATTR_PROXY_ID = "proxy_id"
ATTR_PROXY_NAME = "name"
ATTR_PROXY_STATUS = "status"
ATTR_PROXY_PAUSED = "paused"
ATTR_PROXY_ENABLED = "enabled"
ATTR_PROXY_LISTEN_ADDR = "listen_addr"
ATTR_PROXY_TARGET_ADDR = "target_addr"
ATTR_PROXY_UPTIME = "uptime_s"
ATTR_PROXY_REQUESTS = "requests"
ATTR_PROXY_ERRORS = "errors"
ATTR_PROXY_ACTIVE_CONNECTIONS = "active_connections"
ATTR_PROXY_LATENCY_MEAN = "latency_mean_ms"
ATTR_PROXY_LATENCY_P50 = "latency_p50_ms"
ATTR_PROXY_LATENCY_P95 = "latency_p95_ms"
ATTR_PROXY_LATENCY_P99 = "latency_p99_ms"
ATTR_PROXY_PROTOCOL = "protocol"
ATTR_PROXY_DESCRIPTION = "description"
ATTR_PROXY_TAGS = "tags"

SERVICE_START_PROXY = "start_proxy"
SERVICE_STOP_PROXY = "stop_proxy"
SERVICE_RESTART_PROXY = "restart_proxy"
SERVICE_PAUSE_PROXY = "pause_proxy"
SERVICE_RESUME_PROXY = "resume_proxy"
SERVICE_START_ALL = "start_all"
SERVICE_STOP_ALL = "stop_all"
SERVICE_RESTART_ALL = "restart_all"
SERVICE_RESTART_SYSTEM = "restart_system"

MIN_TIME_BETWEEN_LOGIN = 12  # ModBridge login rate limit is 5/min
