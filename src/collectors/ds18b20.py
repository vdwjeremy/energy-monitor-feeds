"""Read DS18B20 temperature sensors from the Linux 1-Wire sysfs interface."""

import logging
import math
from pathlib import Path
from typing import List

from config import Ds18b20Config
from models import Measurement


LOGGER = logging.getLogger(__name__)


class Ds18b20Collector:
    def __init__(self, config: Ds18b20Config) -> None:
        self.config = config

    def collect(self) -> List[Measurement]:
        """Read and convert every detected sensor's sysfs temperature value."""
        measurements: List[Measurement] = []
        for sensor_path in sorted(self.config.devices_path.glob("28-*")):
            if not sensor_path.is_dir():
                continue
            temperature_path = sensor_path / "temperature"
            try:
                raw_value = float(temperature_path.read_text(encoding="ascii").strip())
                temperature = raw_value / 1000.0
                if not math.isfinite(temperature):
                    raise ValueError("temperature is not finite")
                measurement = Measurement(
                    self.config.node,
                    "{}_temperature_c".format(sensor_path.name),
                    temperature,
                )
            except (OSError, ValueError) as error:
                LOGGER.warning("Could not read DS18B20 sensor %s: %s", sensor_path.name, error)
                continue
            measurements.append(measurement)
        if not measurements:
            LOGGER.warning("No readable DS18B20 sensors found in %s", self.config.devices_path)
        return measurements