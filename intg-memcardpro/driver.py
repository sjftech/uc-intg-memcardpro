"""
MemCard PRO integration driver for Unfolded Circle Remote 3.

Polls each configured MemCard PRO device and exposes a media_player entity
showing the currently loaded game title and cover art.

Supports PS1 (MemCard PRO), PS2 (MemCard PRO 2), and GameCube (MemCard PRO GC).
Cover art is sourced from serial-based GitHub repos — no API key required.
"""

import asyncio
import json
import logging
import os
import ssl
from pathlib import Path

import aiohttp
import ucapi

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

POLL_INTERVAL = 10  # seconds
API_ENDPOINT = "/api/currentState"
CONFIG_FILE = "memcardpro_config.json"

IDLE_GAME_IDS = {"XSTATION", ""}

CONSOLE_NAMES = {
    "PS1": "PlayStation",
    "PS2": "PlayStation 2",
    "GC": "GameCube",
}

COVER_ART_URLS = {
    "PS1": "https://raw.githubusercontent.com/xlenore/psx-covers/main/covers/default/{serial}.jpg",
    "PS2": "https://raw.githubusercontent.com/xlenore/ps2-covers/main/covers/default/{serial}.jpg",
    "GC": "https://raw.githubusercontent.com/AppCakeLtd/gc-covers/main/covers/default/{serial}.png",
}


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

api = ucapi.IntegrationAPI()

# In-memory config: list of {"id": str, "host": str, "name": str}
_devices: list[dict] = []
# aiohttp session shared across all polling
_session: aiohttp.ClientSession | None = None
# SSL context that ignores self-signed certs (MemCard PRO uses self-signed)
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


# ---------------------------------------------------------------------------
# Config persistence
# ---------------------------------------------------------------------------

def _config_path() -> Path:
    config_home = os.environ.get("UC_CONFIG_HOME", str(Path.home()))
    return Path(config_home) / CONFIG_FILE


def _load_config() -> list[dict]:
    path = _config_path()
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            _LOGGER.error("Failed to load config: %s", e)
    return []


def _save_config(devices: list[dict]) -> None:
    path = _config_path()
    try:
        with open(path, "w") as f:
            json.dump(devices, f, indent=2)
        _LOGGER.debug("Config saved to %s", path)
    except Exception as e:
        _LOGGER.error("Failed to save config: %s", e)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _device_id(host: str) -> str:
    """Stable entity ID derived from hostname."""
    return f"memcardpro_{host.replace('.', '_').replace('-', '_')}"


def _normalise_serial(game_id: str, mode: str) -> str:
    """Trim GC serials from 8 to 6 chars for cover art lookup."""
    if mode == "GC" and len(game_id) > 6:
        return game_id[:6]
    return game_id


def _cover_art_url(game_id: str, mode: str) -> str | None:
    if not game_id or game_id in IDLE_GAME_IDS or not mode:
        return None
    template = COVER_ART_URLS.get(mode)
    if not template:
        return None
    return template.format(serial=_normalise_serial(game_id, mode))


def _detect_mode(data: dict) -> str | None:
    """Detect console mode — GC devices don't return currentMode."""
    if "currentMode" in data:
        return data["currentMode"]
    game_id = data.get("gameID", "")
    if game_id and "-" not in game_id and game_id.isalnum():
        return "GC"
    return None


async def _fetch_device_state(host: str) -> dict | None:
    """Poll a single MemCard PRO and return parsed state, or None on error."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession()

    url = f"https://{host}{API_ENDPOINT}"
    try:
        async with asyncio.timeout(10):
            resp = await _session.get(url, ssl=_ssl_ctx)
            resp.raise_for_status()
            data = await resp.json(content_type=None)
            # Inject normalised mode for GC devices
            if "currentMode" not in data:
                data["currentMode"] = _detect_mode(data)
            return data
    except Exception as e:
        _LOGGER.warning("Failed to poll %s: %s", host, e)
        return None


# ---------------------------------------------------------------------------
# Entity management
# ---------------------------------------------------------------------------

def _create_entity(device: dict) -> ucapi.MediaPlayer:
    """Build a MediaPlayer entity for a MemCard PRO device."""
    entity_id = _device_id(device["host"])
    return ucapi.MediaPlayer(
        entity_id,
        {ucapi.Language.EN: device["name"]},
        [ucapi.MediaPlayerFeatures.MEDIA_TITLE, ucapi.MediaPlayerFeatures.MEDIA_IMAGE_URL],
        {
            ucapi.MediaAttr.STATE: ucapi.MediaPlayerStates.STANDBY,
            ucapi.MediaAttr.MEDIA_TITLE: "",
            ucapi.MediaAttr.MEDIA_IMAGE_URL: "",
        },
    )


def _register_entities() -> None:
    """Register all configured devices as available entities."""
    for device in _devices:
        entity = _create_entity(device)
        if not api.available_entities.contains(entity.id):
            api.available_entities.add(entity)
            _LOGGER.info("Registered entity: %s (%s)", entity.id, device["name"])


# ---------------------------------------------------------------------------
# Polling loop
# ---------------------------------------------------------------------------

async def _poll_loop() -> None:
    """Background task that polls all configured devices and pushes updates."""
    while True:
        for device in _devices:
            entity_id = _device_id(device["host"])

            # Only push updates for entities the remote has subscribed to
            if not api.configured_entities.contains(entity_id):
                continue

            data = await _fetch_device_state(device["host"])

            if data is None:
                api.configured_entities.update_attributes(
                    entity_id,
                    {ucapi.MediaAttr.STATE: ucapi.MediaPlayerStates.UNAVAILABLE},
                )
                continue

            game_id = data.get("gameID", "")
            game_name = data.get("gameName", "")
            mode = data.get("currentMode", "")

            if not game_name or game_id in IDLE_GAME_IDS:
                state = ucapi.MediaPlayerStates.ON
                title = ""
                art_url = ""
            else:
                state = ucapi.MediaPlayerStates.PLAYING
                title = game_name
                art_url = _cover_art_url(game_id, mode) or ""

            _LOGGER.debug(
                "%s: state=%s title=%s art=%s",
                entity_id, state, title, art_url
            )

            api.configured_entities.update_attributes(
                entity_id,
                {
                    ucapi.MediaAttr.STATE: state,
                    ucapi.MediaAttr.MEDIA_TITLE: title,
                    ucapi.MediaAttr.MEDIA_IMAGE_URL: art_url,
                },
            )

        await asyncio.sleep(POLL_INTERVAL)


# ---------------------------------------------------------------------------
# UCR3 event handlers
# ---------------------------------------------------------------------------

@api.on(ucapi.Events.CONNECT)
async def on_connect():
    """Remote connected — push current state of all subscribed entities."""
    _LOGGER.info("Remote connected")
    await api.set_device_state(ucapi.DeviceStates.CONNECTED)


@api.on(ucapi.Events.DISCONNECT)
async def on_disconnect():
    """Remote disconnected."""
    _LOGGER.info("Remote disconnected")


@api.on(ucapi.Events.ENTER_STANDBY)
async def on_enter_standby():
    """Remote going to standby — nothing special needed for read-only integration."""
    _LOGGER.debug("Remote entering standby")


@api.on(ucapi.Events.EXIT_STANDBY)
async def on_exit_standby():
    """Remote waking from standby — state will catch up on next poll."""
    _LOGGER.debug("Remote exiting standby")


@api.on(ucapi.Events.SUBSCRIBE_ENTITIES)
async def on_subscribe_entities(entity_ids: list[str]):
    """Remote subscribed to entities — push immediate state."""
    _LOGGER.info("Subscribe entities: %s", entity_ids)
    for entity_id in entity_ids:
        device = next((d for d in _devices if _device_id(d["host"]) == entity_id), None)
        if device is None:
            continue
        data = await _fetch_device_state(device["host"])
        if data:
            game_id = data.get("gameID", "")
            game_name = data.get("gameName", "")
            mode = data.get("currentMode", "")
            if not game_name or game_id in IDLE_GAME_IDS:
                state = ucapi.MediaPlayerStates.ON
                title = ""
                art_url = ""
            else:
                state = ucapi.MediaPlayerStates.PLAYING
                title = game_name
                art_url = _cover_art_url(game_id, mode) or ""
            api.configured_entities.update_attributes(
                entity_id,
                {
                    ucapi.MediaAttr.STATE: state,
                    ucapi.MediaAttr.MEDIA_TITLE: title,
                    ucapi.MediaAttr.MEDIA_IMAGE_URL: art_url,
                },
            )


@api.on(ucapi.Events.UNSUBSCRIBE_ENTITIES)
async def on_unsubscribe_entities(entity_ids: list[str]):
    _LOGGER.info("Unsubscribe entities: %s", entity_ids)


# ---------------------------------------------------------------------------
# Setup flow
# ---------------------------------------------------------------------------

@api.on(ucapi.Events.SETUP_DRIVER)
async def on_setup_driver(msg, data=None):
    """Handle the setup flow from the remote UI."""

    # Step 1: initial request — show the input form
    if isinstance(msg, ucapi.driver.DriverSetupRequest):
        _LOGGER.debug("Setup flow started")
        await api.driver_setup_progress(ucapi.IntegrationSetupError.NONE)
        return ucapi.driver.RequestUserInput(
            {"en": "Add a MemCard PRO device"},
            [
                {
                    "id": "host",
                    "label": {"en": "IP Address or Hostname"},
                    "field": {
                        "text": {
                            "value": "",
                            "placeholder": {"en": "e.g. 192.168.1.100 or memcardpro.local"}
                        }
                    },
                },
                {
                    "id": "name",
                    "label": {"en": "Device Name"},
                    "field": {
                        "text": {
                            "value": "MemCard PRO",
                            "placeholder": {"en": "e.g. PS2 MemCard PRO"}
                        }
                    },
                },
            ],
        )

    # Step 2: user submitted the form
    if isinstance(msg, ucapi.driver.UserDataResponse):
        host = msg.input_values.get("host", "").strip()
        host = host.removeprefix("https://").removeprefix("http://").strip("/")
        name = msg.input_values.get("name", "").strip() or "MemCard PRO"

        _LOGGER.debug("Setup: host=%s name=%s", host, name)

        if not host:
            _LOGGER.error("Setup: no host provided")
            return ucapi.SetupError(ucapi.IntegrationSetupError.NOT_FOUND)

        # Validate the host by fetching it
        await api.driver_setup_progress(ucapi.IntegrationSetupError.NONE)
        state = await _fetch_device_state(host)

        if state is None:
            _LOGGER.error("Setup: could not connect to %s", host)
            return ucapi.SetupError(ucapi.IntegrationSetupError.CONNECTION_REFUSED)

        # Save the new device
        device_id = _device_id(host)
        device = {"id": device_id, "host": host, "name": name}

        # Replace if already exists, otherwise append
        global _devices
        _devices = [d for d in _devices if d["id"] != device_id]
        _devices.append(device)
        _save_config(_devices)

        # Register the entity
        entity = _create_entity(device)
        if api.available_entities.contains(entity.id):
            api.available_entities.remove(entity.id)
        api.available_entities.add(entity)
        _LOGGER.info("Setup complete for %s (%s)", host, name)

        return ucapi.SetupComplete()

    _LOGGER.warning("Unexpected setup message: %s", type(msg))
    return ucapi.SetupError(ucapi.IntegrationSetupError.OTHER)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    """Start the integration."""
    global _devices

    # Load persisted config
    _devices = _load_config()
    _LOGGER.info("Loaded %d configured device(s)", len(_devices))

    # Register any already-configured devices as available entities
    _register_entities()

    # Start background polling
    asyncio.create_task(_poll_loop())

    # Start the ucapi WebSocket server (blocks until shutdown)
    await api.init("driver.json")


if __name__ == "__main__":
    asyncio.run(main())
