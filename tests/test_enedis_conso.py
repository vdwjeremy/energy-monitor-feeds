from datetime import date
from typing import Any, Dict
from unittest.mock import Mock

import pytest

from collectors.enedis_conso import CONSO_API_URL, EnedisConsoCollector
from config import EnedisConsoConfig


def conso_config() -> EnedisConsoConfig:
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


def make_session(body: Dict[str, Any]) -> Mock:
    session = Mock()
    session.get.return_value.json.return_value = body
    return session


def test_collector_requests_recent_curve_and_keeps_source_timestamps(monkeypatch) -> None:
    monkeypatch.setenv("CONSO_API_TOKEN", "test-token")
    session = make_session(
        {
            "grandeur": [
                {
                    "unite": "Wh",
                    "points": [
                        {"d": "2026-11-08T00:00:00+01:00", "v": "120"},
                        {"d": "2026-11-08T01:00:00+01:00", "v": 90},
                        {"d": "invalid", "v": "NaN"},
                        {"d": "invalid", "v": 10},
                    ],
                },
                {
                    "unite": "kWh",
                    "points": [{"d": "2026-11-08T02:00:00+01:00", "v": "0.25"}],
                },
            ]
        }
    )

    measurements = EnedisConsoCollector(conso_config(), session=session).collect(
        today=date(2026, 11, 11)
    )

    assert [(item.value, item.timestamp) for item in measurements] == [
        (120.0, "2026-11-08T00:00:00+01:00"),
        (90.0, "2026-11-08T01:00:00+01:00"),
        (250.0, "2026-11-08T02:00:00+01:00"),
    ]
    session.get.assert_called_once_with(
        CONSO_API_URL,
        params={
            "pointId": "12345678901234",
            "dateDebut": "2026-11-08",
            "dateFin": "2026-11-11",
        },
        headers={
            "Authorization": "Bearer test-token",
            "Accept": "application/json",
            "User-Agent": "energy-monitor-feeds",
        },
        timeout=12,
    )
    session.get.return_value.raise_for_status.assert_called_once_with()


def test_collector_requires_token_without_making_request(monkeypatch) -> None:
    monkeypatch.delenv("CONSO_API_TOKEN", raising=False)
    session = make_session({})

    with pytest.raises(ValueError, match="token environment variable"):
        EnedisConsoCollector(conso_config(), session=session).collect()

    session.get.assert_not_called()


def test_collector_logs_response_shape_when_no_valid_points(monkeypatch, caplog) -> None:
    monkeypatch.setenv("CONSO_API_TOKEN", "test-token")
    session = make_session(
        {
            "grandeur": [{"unite": "kWh", "points": [{"d": "invalid", "v": "NaN"}]}],
            "error": {"error": "no_data_found"},
        }
    )

    with pytest.raises(ValueError, match="no valid hourly consumption points"):
        EnedisConsoCollector(conso_config(), session=session).collect(today=date(2026, 11, 11))

    assert "'unit': 'kWh'" in caplog.text
    assert "'point_count': 1" in caplog.text
    assert "invalid_timestamps=1" in caplog.text
    assert "invalid_values=0" in caplog.text
    assert "no_data_found" in caplog.text
    assert "Bearer" not in caplog.text