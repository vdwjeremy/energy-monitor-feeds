from pathlib import Path

import pytest

from collectors.ds18b20 import Ds18b20Collector
from config import Ds18b20Config


def create_sensor(devices_path: Path, sensor_id: str, temperature: str) -> None:
    sensor_path = devices_path / sensor_id
    sensor_path.mkdir(parents=True)
    (sensor_path / "temperature").write_text(temperature, encoding="ascii")


def test_collect_reads_each_sensor_as_a_separate_celsius_measurement(tmp_path: Path) -> None:
    create_sensor(tmp_path, "28-000000000001", "21562\n")
    create_sensor(tmp_path, "28-000000000002", "-1250\n")
    collector = Ds18b20Collector(Ds18b20Config(tmp_path, "ds18b20", 30))

    measurements = collector.collect()

    assert [(item.key, item.value) for item in measurements] == [
        ("28-000000000001_temperature_c", 21.562),
        ("28-000000000002_temperature_c", -1.25),
    ]
    assert measurements[0].topic("emon") == "emon/ds18b20/28-000000000001_temperature_c"
    assert measurements[1].topic("emon") == "emon/ds18b20/28-000000000002_temperature_c"


def test_collect_skips_unreadable_sensor_and_non_sensor_entries(tmp_path: Path) -> None:
    create_sensor(tmp_path, "28-000000000001", "not-a-number")
    (tmp_path / "28-not-a-directory").write_text("ignored", encoding="ascii")
    create_sensor(tmp_path, "28-000000000002", "19750")
    collector = Ds18b20Collector(Ds18b20Config(tmp_path, "ds18b20", 30))

    measurements = collector.collect()

    assert [(item.key, item.value) for item in measurements] == [
        ("28-000000000002_temperature_c", 19.75)
    ]


@pytest.mark.parametrize("raw_value", ["nan", "inf", "-inf"])
def test_collect_skips_non_finite_values(tmp_path: Path, raw_value: str) -> None:
    create_sensor(tmp_path, "28-000000000001", raw_value)
    collector = Ds18b20Collector(Ds18b20Config(tmp_path, "ds18b20", 30))

    assert collector.collect() == []