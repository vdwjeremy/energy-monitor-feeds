"""Command-line entry point for collector services."""

import argparse
import asyncio
import logging
import signal
import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Optional, Sequence

from collectors.weather_api import WeatherApiCollector
from collectors.refoss_em06 import RefossEm06Collector
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


async def _run_refoss_em06(config_path: Path, stop: threading.Event) -> None:
    config = load_config(config_path)
    if config.refoss_em06 is None:
        raise ValueError("Missing [collectors.refoss_em06] configuration section")

    collector = RefossEm06Collector(config.refoss_em06)
    mqtt_config = replace(config.mqtt, client_id="{}-refoss-em06".format(config.mqtt.client_id))
    with MqttPublisher(mqtt_config) as publisher:
        await collector.start()
        try:
            LOGGER.info("Starting Refoss EM06 collector")
            while not stop.is_set():
                cycle_started = time.monotonic()
                try:
                    measurements = await collector.collect()
                    for measurement in measurements:
                        try:
                            publisher.publish(measurement)
                            LOGGER.info(
                                "Published %s=%s to %s",
                                measurement.key,
                                measurement.payload,
                                measurement.topic(config.mqtt.basetopic),
                            )
                        except Exception:
                            LOGGER.exception("Failed to publish Refoss metric %s", measurement.key)
                    if not measurements:
                        LOGGER.warning("Refoss EM06 returned no valid metrics this cycle")
                except Exception:
                    LOGGER.exception("Refoss EM06 collection failed")

                remaining = config.refoss_em06.interval_seconds - (time.monotonic() - cycle_started)
                await asyncio.to_thread(stop.wait, max(0.0, remaining))
        finally:
            await collector.close()


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Collect and publish energy-monitor measurements")
    parser.add_argument("collector", choices=("weather_api", "refoss_em06"), help="collector to run")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="path to TOML config")
    args = parser.parse_args(argv)

    configure_logging()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda _signal, _frame: stop.set())
    signal.signal(signal.SIGINT, lambda _signal, _frame: stop.set())
    try:
        if args.collector == "weather_api":
            _run_weather_api(args.config, stop)
        else:
            asyncio.run(_run_refoss_em06(args.config, stop))
    except Exception:
        LOGGER.exception("Collector stopped")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())