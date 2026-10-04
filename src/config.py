"""Load and validate runtime configuration."""

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib


@dataclass(frozen=True)
class MqttConfig:
    host: str
    port: int
    basetopic: str
    client_id: str
    qos: int
    tls: bool
    connect_timeout_seconds: float
    publish_timeout_seconds: float
    username_env: Optional[str] = None
    password_env: Optional[str] = None


@dataclass(frozen=True)
class WeatherConfig:
    latitude: float
    longitude: float
    timezone: str
    node: str
    key: str
    interval_seconds: float
    request_timeout_seconds: float


@dataclass(frozen=True)
class AppConfig:
    mqtt: MqttConfig
    weather_api: WeatherConfig


def _section(data: Dict[str, Any], name: str) -> Dict[str, Any]:
    section = data.get(name)
    if not isinstance(section, dict):
        raise ValueError("Missing or invalid configuration section: [{}]".format(name))
    return section


def _positive_number(section: Dict[str, Any], key: str) -> float:
    value = section.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value <= 0
    ):
        raise ValueError("{} must be a positive number".format(key))
    return float(value)


def _coordinate(section: Dict[str, Any], key: str, minimum: float, maximum: float) -> float:
    value = section.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= maximum:
        raise ValueError("{} must be between {} and {}".format(key, minimum, maximum))
    return float(value)


def _non_empty_string(section: Dict[str, Any], key: str) -> str:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("{} must be a non-empty string".format(key))
    return value.strip()


def load_config(path: Path) -> AppConfig:
    """Read TOML settings and validate values needed by the weather daemon."""
    with Path(path).open("rb") as config_file:
        data = tomllib.load(config_file)

    mqtt_data = _section(data, "mqtt")
    weather_data = _section(_section(data, "collectors"), "weather_api")

    host = mqtt_data.get("host")
    if not isinstance(host, str) or not host.strip():
        raise ValueError("mqtt.host must be a non-empty string")

    port = mqtt_data.get("port", 1883)
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        raise ValueError("mqtt.port must be an integer from 1 to 65535")

    basetopic = mqtt_data.get("basetopic", "emon")
    if not isinstance(basetopic, str) or not basetopic or "/" in basetopic:
        raise ValueError("mqtt.basetopic must be one non-empty topic segment")
    if "+" in basetopic or "#" in basetopic:
        raise ValueError("mqtt.basetopic cannot contain MQTT wildcards")

    qos = mqtt_data.get("qos", 0)
    if isinstance(qos, bool) or not isinstance(qos, int) or qos not in (0, 1, 2):
        raise ValueError("mqtt.qos must be 0, 1 or 2")

    tls = mqtt_data.get("tls", False)
    if not isinstance(tls, bool):
        raise ValueError("mqtt.tls must be true or false")

    username_env = mqtt_data.get("username_env") or None
    password_env = mqtt_data.get("password_env") or None
    if bool(username_env) != bool(password_env):
        raise ValueError("Set both mqtt.username_env and mqtt.password_env, or neither")
    if username_env is not None and (not isinstance(username_env, str) or not isinstance(password_env, str)):
        raise ValueError("MQTT credential environment-variable names must be strings")

    weather_config = WeatherConfig(
        latitude=_coordinate(weather_data, "latitude", -90, 90),
        longitude=_coordinate(weather_data, "longitude", -180, 180),
        timezone=_non_empty_string(weather_data, "timezone"),
        node=_non_empty_string(weather_data, "node"),
        key=_non_empty_string(weather_data, "key"),
        interval_seconds=_positive_number(weather_data, "interval_seconds"),
        request_timeout_seconds=_positive_number(weather_data, "request_timeout_seconds"),
    )

    return AppConfig(
        mqtt=MqttConfig(
            host=host.strip(),
            port=port,
            basetopic=basetopic,
            client_id=_non_empty_string(mqtt_data, "client_id"),
            qos=qos,
            tls=tls,
            connect_timeout_seconds=_positive_number(mqtt_data, "connect_timeout_seconds"),
            publish_timeout_seconds=_positive_number(mqtt_data, "publish_timeout_seconds"),
            username_env=username_env,
            password_env=password_env,
        ),
        weather_api=weather_config,
    )