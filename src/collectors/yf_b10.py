"""Read YF-B10 flow pulses from a Raspberry Pi GPIO pin."""

import logging
import math
import threading
import time
from typing import Any, List, Tuple

from config import YfB10Config
from models import Measurement


LOGGER = logging.getLogger(__name__)


def flow_metrics_from_pulses(node: str, pulse_count: int, elapsed_seconds: float) -> List[Measurement]:
    """Convert a pulse count window to frequency and estimated flow rate."""
    if isinstance(pulse_count, bool) or not isinstance(pulse_count, int) or pulse_count < 0:
        raise ValueError("pulse_count must be a non-negative integer")
    if not math.isfinite(elapsed_seconds) or elapsed_seconds <= 0:
        raise ValueError("elapsed_seconds must be a positive finite number")

    frequency_hz = pulse_count / elapsed_seconds
    flow_l_min = 0.0 if pulse_count == 0 else (frequency_hz + 4.0) / 8.0
    return [
        Measurement(node, "frequency_hz", frequency_hz),
        Measurement(node, "flow_l_min", flow_l_min),
    ]


class YfB10Collector:
    def __init__(self, config: YfB10Config, clock: Any = time.monotonic) -> None:
        self.config = config
        self._clock = clock
        self._lock = threading.Lock()
        self._pulse_count = 0
        self._last_pulse_count = 0
        self._last_read_time = 0.0
        self._input_device: Any = None

    def start(self) -> None:
        if self._input_device is not None:
            return

        from gpiozero import DigitalInputDevice

        input_device = DigitalInputDevice(self.config.gpio_pin, pull_up=True)
        input_device.when_activated = self._record_pulse
        self._input_device = input_device
        self._last_read_time = self._clock()
        LOGGER.info("Reading YF-B10 flow sensor on BCM GPIO %s", self.config.gpio_pin)

    def _record_pulse(self) -> None:
        with self._lock:
            self._pulse_count += 1

    def collect(self) -> List[Measurement]:
        if self._input_device is None:
            raise RuntimeError("YF-B10 collector has not been started")

        now = self._clock()
        with self._lock:
            pulse_count = self._pulse_count - self._last_pulse_count
            elapsed_seconds = now - self._last_read_time
            self._last_pulse_count = self._pulse_count
            self._last_read_time = now
        if elapsed_seconds <= 0:
            raise RuntimeError("YF-B10 sampling interval must advance")
        return flow_metrics_from_pulses(self.config.node, pulse_count, elapsed_seconds)

    def close(self) -> None:
        if self._input_device is not None:
            self._input_device.close()
            self._input_device = None