from pathlib import Path

import pytest

from config import load_config


def write_config(path: Path, port: int = 1883) -> None:
    path.write_text(
        """[mqtt]
host = "localhost"
port = {port}
basetopic = "emon"
client_id = "weather-test"
qos = 0
tls = false
connect_timeout_seconds = 5
publish_timeout_seconds = 5

[collectors.weather_api]
latitude = 43.66862
longitude = 6.98212
timezone = "Europe/Paris"
node = "weather_opio"
key = "temperature_c"
interval_seconds = 300
request_timeout_seconds = 10
""".format(port=port),
        encoding="utf-8",
    )


def test_load_config_returns_opio_weather_and_mqtt_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    write_config(config_path)

    config = load_config(config_path)

    assert config.mqtt.host == "localhost"
    assert config.mqtt.basetopic == "emon"
    assert config.weather_api.node == "weather_opio"
    assert config.weather_api.latitude == pytest.approx(43.66862)


def test_load_config_rejects_invalid_mqtt_port(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    write_config(config_path, port=70000)

    with pytest.raises(ValueError, match="mqtt.port"):
        load_config(config_path)


def test_load_config_rejects_infinite_collection_interval(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    write_config(config_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace("interval_seconds = 300", "interval_seconds = inf"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="interval_seconds"):
        load_config(config_path)