"""Read the current air temperature in Opio, France from Open-Meteo."""

import math
from typing import Optional

import requests

from config import WeatherConfig
from models import Measurement


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


class WeatherApiCollector:
    def __init__(self, config: WeatherConfig, session: Optional[requests.Session] = None) -> None:
        self.config = config
        self.session = session or requests.Session()

    def collect(self) -> Measurement:
        response = self.session.get(
            FORECAST_URL,
            params={
                "latitude": self.config.latitude,
                "longitude": self.config.longitude,
                "current": "temperature_2m",
                "temperature_unit": "celsius",
                "timezone": self.config.timezone,
            },
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        current = body.get("current") if isinstance(body, dict) else None
        temperature = current.get("temperature_2m") if isinstance(current, dict) else None
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)):
            raise ValueError("Open-Meteo response does not contain a numeric current temperature")
        if not math.isfinite(temperature):
            raise ValueError("Open-Meteo returned a non-finite temperature")
        return Measurement(self.config.node, self.config.key, float(temperature))