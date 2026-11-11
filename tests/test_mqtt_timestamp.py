import json
from types import SimpleNamespace
from unittest.mock import Mock

from models import Measurement
from mqtt import MqttPublisher


def publisher() -> MqttPublisher:
    instance = MqttPublisher.__new__(MqttPublisher)
    instance.config = SimpleNamespace(
        basetopic="emon",
        qos=0,
        connect_timeout_seconds=5,
        publish_timeout_seconds=5,
    )
    instance._connected = Mock()
    instance._client = Mock()
    result = Mock(rc=0)
    result.is_published.return_value = True
    instance._client.publish.return_value = result
    return instance


def test_timestamped_measurement_uses_emoncms_json_time_payload() -> None:
    mqtt_publisher = publisher()

    mqtt_publisher.publish(
        Measurement("enedis_linky", "consumption_wh", 120.0, "2026-11-08T00:00:00+01:00")
    )

    args, kwargs = mqtt_publisher._client.publish.call_args
    assert args[0] == "emon/enedis_linky"
    assert json.loads(args[1]) == {
        "consumption_wh": 120.0,
        "time": "2026-11-08T00:00:00+01:00",
    }
    assert kwargs == {"qos": 0, "retain": False}


def test_measurement_without_timestamp_keeps_existing_mqtt_format() -> None:
    mqtt_publisher = publisher()

    mqtt_publisher.publish(Measurement("weather_opio", "temperature_c", 18.5))

    args, _kwargs = mqtt_publisher._client.publish.call_args
    assert args[:2] == ("emon/weather_opio/temperature_c", "18.5")