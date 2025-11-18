"""Common classes and functions for NiceHash."""
from datetime import timedelta
from logging import getLogger
from typing import Any, Dict
import async_timeout

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import HomeAssistantError

from custom_components.nicehash.nicehash import NiceHashPrivateAPI
from custom_components.nicehash.const import (
    ACCOUNT_OBJ,
    DOMAIN,
    RIGS_OBJ,
)

PLACEHOLDER_RIG_NAMES = {"__DEFAULT__", "- UNMANAGED -", "UNMANAGED"}

_LOGGER = getLogger(__name__)


class NiceHashSensorDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold NiceHash data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: NiceHashPrivateAPI,
        update_interval: int,
        fiat="USD",
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=update_interval),
            update_method=self._async_update_data,
        )
        self._api = api
        self._fiat = fiat

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(10):
                rigs = await self._api.get_rigs_data()
                _LOGGER.debug(f"API Rigs response: {rigs}")
                account = await self._api.get_account_data(self._fiat)
                return {RIGS_OBJ: rigs, ACCOUNT_OBJ: account}
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err


def resolve_rig_name(rig: Dict[str, Any] | None) -> str | None:
    """Return the most meaningful name for a rig."""

    if not rig:
        return None

    placeholder_tokens = {token.upper() for token in PLACEHOLDER_RIG_NAMES}

    def _normalize(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        name = value.strip()
        if not name:
            return None
        if name.upper() in placeholder_tokens:
            return None
        return name

    keys = (
        "name",
        "displayName",
        "rigDisplayName",
        "label",
        "worker",
        "rigName",
        "groupName",
    )

    metadata = rig.get("metadata") or {}
    group = rig.get("group") or {}
    v4 = rig.get("v4") or {}
    mmv = v4.get("mmv") or {}

    candidates = [rig.get(key) for key in keys]
    candidates.extend(metadata.get(key) for key in keys)
    candidates.extend(group.get(key) for key in keys if isinstance(group, dict))
    candidates.append(rig.get("groupName"))

    candidates.append(mmv.get("workerName"))

    for os_value in v4.get("osv") or []:
        candidates.append(os_value.get("value"))

    for device in v4.get("devices") or []:
        dsv = device.get("dsv") or {}
        candidates.append(dsv.get("name"))

    for device in rig.get("devices", []):
        candidates.append(device.get("name"))

    for candidate in candidates:
        normalized = _normalize(candidate)
        if normalized:
            return normalized

    return rig.get("rigId")
