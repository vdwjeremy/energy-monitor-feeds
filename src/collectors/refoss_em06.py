"""Read Refoss EM06 metrics over the local network."""

import asyncio
import logging
import math
import sys
from typing import Any, List, Optional

from config import RefossEm06Config
from models import Measurement


LOGGER = logging.getLogger(__name__)


def _finite_number(value: Any, metric: str, channel: int) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        LOGGER.warning("Skipping Refoss channel %s metric %s with invalid value %r", channel, metric, value)
        return None
    return float(value)


def metrics_from_device(node: str, device: Any) -> List[Measurement]:
    """Convert refoss_ha channel values to separate MQTT measurements."""
    measurements: List[Measurement] = []
    for channel in device.channels:
        for subkey, suffix, divisor in (
            ("power", "power_w", 1000.0),
            ("voltage", "voltage_v", 1000.0),
            ("current", "current_a", 1000.0),
            ("factor", "power_factor", 1.0),
        ):
            value = _finite_number(device.get_value(channel, subkey), suffix, channel)
            if value is not None:
                measurements.append(
                    Measurement(node, "channel_{}_{}".format(channel, suffix), value / divisor)
                )

        monthly_energy = _finite_number(device.get_value(channel, "mConsume"), "mConsume", channel)
        if monthly_energy is not None:
            measurements.extend(
                (
                    Measurement(
                        node,
                        "channel_{}_energy_monthly_wh".format(channel),
                        max(0.0, monthly_energy),
                    ),
                    Measurement(
                        node,
                        "channel_{}_energy_returned_monthly_wh".format(channel),
                        max(0.0, -monthly_energy),
                    ),
                )
            )
    return measurements


class RefossEm06Collector:
    def __init__(self, config: RefossEm06Config) -> None:
        self.config = config
        self._discovery: Optional[Any] = None
        self._device: Optional[Any] = None

    async def start(self) -> None:
        if sys.version_info < (3, 11):
            raise RuntimeError("The Refoss EM06 collector requires Python 3.11 or newer")

        from refoss_ha.controller.electricity import ElectricityXMix
        from refoss_ha.device_manager import async_build_base_device
        from refoss_ha.discovery import Discovery

        discovery = Discovery()
        self._discovery = discovery
        try:
            await discovery.initialize()
            devices = await discovery.broadcast_msg(
                wait_for=self.config.discovery_timeout_seconds
            )
            candidates = [
                info
                for info in devices
                if info.device_type.lower() == "em06"
                and (self.config.device_uuid is None or info.uuid == self.config.device_uuid)
            ]
            if len(candidates) != 1:
                discovered = ", ".join(
                    "{} ({})".format(info.dev_name, info.uuid)
                    for info in devices
                    if info.device_type.lower() == "em06"
                ) or "none"
                raise RuntimeError(
                    "Expected one matching Refoss EM06; discovered: {}. Set device_uuid "
                    "when more than one EM06 is on the network.".format(discovered)
                )

            device = await asyncio.wait_for(
                async_build_base_device(candidates[0]),
                timeout=self.config.request_timeout_seconds,
            )
            if not isinstance(device, ElectricityXMix):
                raise RuntimeError("The discovered Refoss EM06 does not expose electricity metrics")
            self._device = device
            LOGGER.info("Connected to Refoss EM06 %s (%s)", device.dev_name, device.uuid)
        except Exception:
            await self.close()
            raise

    async def collect(self) -> List[Measurement]:
        if self._device is None:
            raise RuntimeError("Refoss EM06 collector has not been started")

        await asyncio.wait_for(
            self._device.async_handle_update(),
            timeout=self.config.request_timeout_seconds,
        )
        return metrics_from_device(self.config.node, self._device)

    async def close(self) -> None:
        if self._discovery is not None:
            transport = getattr(self._discovery, "transport", None)
            if transport is not None:
                transport.close()
            self._discovery.clean_up()
            self._discovery = None
        self._device = None