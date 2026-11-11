from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from config import EnedisConsoConfig
from emoncms import EmoncmsFeedClient, _unix_timestamp
from models import Measurement


def emoncms_config() -> EnedisConsoConfig:
    return EnedisConsoConfig(
        point_id="12345678901234",
        token_env="CONSO_API_TOKEN",
        emoncms_url="https://emoncms.example",
        feed_id=42,
        emoncms_api_key_env="EMONCMS_API_KEY",
        node="enedis_linky",
        key="consumption_wh",
        interval_seconds=86400,
        lookback_days=3,
        request_timeout_seconds=12,
    )


def test_naive_timestamp_defaults_to_cet() -> None:
    assert _unix_timestamp("2026-11-08T00:00:00") == _unix_timestamp(
        "2026-11-08T00:00:00+01:00"
    )


def test_insert_posts_feed_id_value_and_unix_timestamp(monkeypatch) -> None:
    monkeypatch.setenv("EMONCMS_API_KEY", "write-key")
    session = Mock()
    session.get.return_value.json.return_value = 120.0
    measurement = Measurement("enedis_linky", "consumption_wh", 120.0, "2026-11-08T00:00:00+01:00")

    EmoncmsFeedClient(emoncms_config(), session=session).insert(measurement)

    session.get.assert_called_once_with(
        "https://emoncms.example/feed/insert.json",
        params={
            "id": 42,
            "time": int(datetime(2026, 11, 7, 23, tzinfo=timezone.utc).timestamp()),
            "value": 120.0,
        },
        headers={
            "Authorization": "Bearer write-key",
            "Accept": "application/json",
        },
        timeout=12,
    )
    session.get.return_value.raise_for_status.assert_called_once_with()


def test_insert_requires_api_key_without_request(monkeypatch) -> None:
    monkeypatch.delenv("EMONCMS_API_KEY", raising=False)
    session = Mock()
    measurement = Measurement("enedis_linky", "consumption_wh", 120.0, "2026-11-08T00:00:00Z")

    with pytest.raises(ValueError, match="EmonCMS API key environment variable"):
        EmoncmsFeedClient(emoncms_config(), session=session).insert(measurement)

    session.get.assert_not_called()


def test_insert_surfaces_emoncms_api_rejection(monkeypatch) -> None:
    monkeypatch.setenv("EMONCMS_API_KEY", "write-key")
    session = Mock()
    session.get.return_value.json.return_value = {
        "success": False,
        "message": "Feed does not exist",
    }
    measurement = Measurement("enedis_linky", "consumption_wh", 120.0, "2026-11-08T00:00:00Z")

    with pytest.raises(RuntimeError, match="Feed does not exist"):
        EmoncmsFeedClient(emoncms_config(), session=session).insert(measurement)