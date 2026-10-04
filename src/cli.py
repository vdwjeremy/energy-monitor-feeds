"""Command-line entry point for collector services."""

import argparse
import logging
import signal
import threading
import time
from pathlib import Path
from typing import Optional, Sequence

from collectors.weather_api import WeatherApiCollector
from config import load_config
from logging_config import configure_logging
from mqtt import MqttPublisher


LOGGER = logging.getLogger("energy_feed")
DEFAULT_CONFIG = Path("/etc/energy-monitor-feeds/config.toml")


def _run_weather_api(config_path: Path, stop: threading.Event) -> None:
    config = load_config(config_path)
    collector = WeatherApiCollector(config.weather_api)
    with MqttPublisher(config.mqtt) as publisher:
        LOGGER.info("Starting weather collector for Opio, France")
        while not stop.is_set():
            cycle_started = time.monotonic()
            try:
                measurement = collector.collect()
                publisher.publish(measurement)
                LOGGER.info(
                    "Published %s=%s to %s",
                    measurement.key,
                    measurement.payload,
                    measurement.topic(config.mqtt.basetopic),
                )
            except Exception:
                LOGGER.exception("Weather collection or MQTT publication failed")

            remaining = config.weather_api.interval_seconds - (time.monotonic() - cycle_started)
            stop.wait(max(0.0, remaining))


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Collect and publish energy-monitor measurements")
    parser.add_argument("collector", choices=("weather_api",), help="collector to run")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="path to TOML config")
    args = parser.parse_args(argv)

    configure_logging()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda _signal, _frame: stop.set())
    signal.signal(signal.SIGINT, lambda _signal, _frame: stop.set())
    try:
        _run_weather_api(args.config, stop)
    except Exception:
        LOGGER.exception("Collector stopped")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())