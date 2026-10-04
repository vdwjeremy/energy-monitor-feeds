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


def test_load_config_reads_optional_refoss_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    write_config(config_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + '\n[collectors.refoss_em06]\ndevice_uuid = "em06-uuid"\nnode = "refoss_em06"\n'
        + "interval_seconds = 30\ndiscovery_timeout_seconds = 5\nrequest_timeout_seconds = 10\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.refoss_em06 is not None
    assert config.refoss_em06.device_uuid == "em06-uuid"
    assert config.refoss_em06.discovery_timeout_seconds == 5


def test_load_config_reads_optional_ds18b20_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.toml"
    write_config(config_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8")
        + '\n[collectors.ds18b20]\ndevices_path = "/tmp/w1/devices"\n'
        + 'node = "temperatures"\ninterval_seconds = 15\n',
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.ds18b20 is not None
    assert config.ds18b20.devices_path == Path("/tmp/w1/devices")
    assert config.ds18b20.node == "temperatures"
    assert config.ds18b20.interval_seconds == 15