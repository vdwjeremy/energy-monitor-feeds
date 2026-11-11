"""Write timestamped values directly to EmonCMS feeds."""

import logging
import os
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

import requests

from config import EnedisConsoConfig
from models import Measurement


LOGGER = logging.getLogger(__name__)


def _unix_timestamp(value: Optional[str]) -> int:
    if value is None:
        raise ValueError("A source timestamp is required to insert a feed datapoint")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Invalid ISO 8601 measurement timestamp") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("CET"))
    return int(parsed.timestamp())


class EmoncmsFeedClient:
    def __init__(
        self,
        config: EnedisConsoConfig,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.config = config
        self.session = session or requests.Session()

    def insert(self, measurement: Measurement) -> None:
        api_key = os.environ.get(self.config.emoncms_api_key_env)
        if not api_key:
            raise ValueError("EmonCMS API key environment variable is not set")

        response = self.session.get(
            "{}/feed/insert.json".format(self.config.emoncms_url),
            params={
                "id": self.config.feed_id,
                "time": _unix_timestamp(measurement.timestamp),
                "value": measurement.value,
            },
            headers={
                "Authorization": "Bearer {}".format(api_key),
                "Accept": "application/json",
            },
            timeout=self.config.request_timeout_seconds,
        )
        response.raise_for_status()

        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict) and body.get("success") is False:
            raise RuntimeError("EmonCMS rejected feed insert: {}".format(body.get("message", "unknown error")))
        LOGGER.debug(
            "Inserted Enedis measurement into EmonCMS feed %s at %s",
            self.config.feed_id,
            measurement.timestamp,
        )