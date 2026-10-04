"""Scaffold for future local sensor integrations.

No hardware driver is selected yet. Implement this collector after the sensor
model and Linux interface (GPIO, I2C, SPI, or serial) are decided.
"""

from models import Measurement


class LocalSensorsCollector:
    def collect(self) -> Measurement:
        raise NotImplementedError("Select and configure a local sensor driver first")