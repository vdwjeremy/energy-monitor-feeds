"""Read hourly electricity consumption from Conso API."""

import math
import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import requests

from config import EnedisConsoConfig
from models import Measurement


CONSO_API_URL = "https://conso.boris.sh/api/courbe_de_charge_consommation"
LOGGER = logging.getLogger(__name__)


def _grandeurs(body: Any) -> List[Dict[str, Any]]:
    if not isinstance(body, dict):
        return []

    grandeurs: List[Dict[str, Any]] = []
    direct = body.get("grandeur")
    if isinstance(direct, list):
        grandeurs.extend(item for item in direct if isinstance(item, dict))

    contextes = body.get("contexte")
    if isinstance(contextes, list):
        for contexte in contextes:
            if isinstance(contexte, dict) and isinstance(contexte.get("grandeur"), list):
                grandeurs.extend(
                    item for item in contexte["grandeur"] if isinstance(item, dict)
                )
    return grandeurs


def _value_in_wh(value: Any, unit: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None

    if unit == "W":
        return number
    if unit == "Wh":
        return number
    if unit == "kWh":
        return number * 1000.0
    return None


def _valid_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


class EnedisConsoCollector:
    def __init__(
        self,
        config: EnedisConsoConfig,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()

    def collect(self, today: Optional[date] = None) -> List[Measurement]:
        token = os.environ.get(self.config.token_env)
        if not token:
            raise ValueError("Conso API token environment variable is not set")

        end_date = today or date.today()
        start_date = end_date - timedelta(days=self.config.lookback_days)
        LOGGER.info(
            "Requesting Enedis hourly consumption from %s to %s",
            start_date.isoformat(),
            end_date.isoformat(),
        )
        response = self.session.get(
            CONSO_API_URL,
            params={
                "pointId": self.config.point_id,
                "dateDebut": start_date.isoformat(),
                "dateFin": end_date.isoformat(),
            },
            headers={
                "Authorization": "Bearer {}".format(token),
                "Accept": "application/json",
                "User-Agent": "energy-monitor-feeds",
            },
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        LOGGER.info("Conso API returned HTTP %s", response.status_code)
        if isinstance(body, dict):
            LOGGER.debug("Conso API response top-level keys: %s", sorted(body.keys()))
        else:
            LOGGER.warning("Conso API response is %s, expected a JSON object", type(body).__name__)

        measurements: List[Measurement] = []
        invalid_timestamp_count = 0
        invalid_value_count = 0
        missing_points_count = 0
        unknown_units = set()
        grandeur_details = []
        grandeurs = _grandeurs(body)
        LOGGER.debug("Found %s measurement grandeur(s)", len(grandeurs))
        for grandeur_index, grandeur in enumerate(grandeurs):
            unit = grandeur.get("unite")
            points = grandeur.get("points")
            LOGGER.debug(
                "Grandeur %s: keys=%s unit=%r points_type=%s point_count=%s",
                grandeur_index,
                sorted(grandeur.keys()),
                unit,
                type(points).__name__,
                len(points) if isinstance(points, list) else "n/a",
            )
            grandeur_details.append(
                {
                    "keys": sorted(grandeur.keys()),
                    "unit": unit,
                    "points_type": type(points).__name__,
                    "point_count": len(points) if isinstance(points, list) else None,
                }
            )
            if not isinstance(points, list):
                missing_points_count += 1
                continue
            if unit not in ("W", "Wh", "kWh"):
                unknown_units.add(repr(unit))
            for point in points:
                LOGGER.debug("point: %s", point)
                if not isinstance(point, dict):
                    invalid_value_count += 1
                    continue
                timestamp = point.get("d")
                value = _value_in_wh(point.get("v"), unit)
                if not _valid_timestamp(timestamp):
                    LOGGER.debug("invalid timestamp: %s", timestamp)
                    invalid_timestamp_count += 1
                    continue
                if value is None:
                    LOGGER.debug("invalid value: %s", value)
                    invalid_value_count += 1
                    continue
                measurements.append(
                    Measurement(self.config.node, self.config.key, value, timestamp)
                )

        if not measurements:
            response_error = {}
            if isinstance(body, dict):
                response_error = {
                    key: body.get(key)
                    for key in ("status", "message", "error")
                    if key in body
                }
            LOGGER.warning(
                "No valid hourly consumption points: response_keys=%s grandeurs=%r "
                "missing_points=%s invalid_timestamps=%s invalid_values=%s "
                "unknown_units=%s api_error=%r",
                sorted(body.keys()) if isinstance(body, dict) else [],
                grandeur_details,
                missing_points_count,
                invalid_timestamp_count,
                invalid_value_count,
                sorted(unknown_units),
                response_error,
            )
            raise ValueError("Conso API returned no valid hourly consumption points")
        LOGGER.info("Parsed %s valid hourly consumption point(s)", len(measurements))
        return measurements