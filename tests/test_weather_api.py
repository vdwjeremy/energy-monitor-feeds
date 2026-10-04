from typing import Any, Dict
from unittest.mock import Mock

import pytest

from collectors.weather_api import FORECAST_URL, WeatherApiCollector
from config import WeatherConfig


def weather_config() -> WeatherConfig:
    return WeatherConfig(
        latitude=43.66862,
        longitude=6.98212,
        timezone="Europe/Paris",
        node="weather_opio",
        key="temperature_c",
        interval_seconds=300,
        request_timeout_seconds=12,
    )


def make_session(body: Dict[str, Any]) -> Mock:
    session = Mock()
    session.get.return_value.json.return_value = body
    return session


def test_collector_requests_opio_temperature_and_returns_measurement() -> None:
    session = make_session({"current": {"temperature_2m": 17.25}})

    measurement = WeatherApiCollector(weather_config(), session=session).collect()

    assert measurement.node == "weather_opio"
    assert measurement.key == "temperature_c"
    assert measurement.value == pytest.approx(17.25)
    session.get.assert_called_once_with(
        FORECAST_URL,
        params={
            "latitude": 43.66862,
            "longitude": 6.98212,
            "current": "temperature_2m",
            "temperature_unit": "celsius",
            "timezone": "Europe/Paris",
        },
        timeout=12,
    )
    session.get.return_value.raise_for_status.assert_called_once_with()


def test_collector_rejects_missing_temperature() -> None:
    session = make_session({"current": {}})

    with pytest.raises(ValueError, match="numeric current temperature"):
        WeatherApiCollector(weather_config(), session=session).collect()