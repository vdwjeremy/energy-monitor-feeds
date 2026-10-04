"""MQTT publication for EmonCMS topics."""

import logging
import os
import threading
from typing import Optional

import paho.mqtt.client as mqtt_client

from config import MqttConfig
from models import Measurement


LOGGER = logging.getLogger(__name__)


class MqttPublisher:
    def __init__(self, config: MqttConfig) -> None:
        self.config = config
        self._connected = threading.Event()
        self._connect_result: Optional[str] = None
        self._client = mqtt_client.Client(
            callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2,
            client_id=config.client_id,
            protocol=mqtt_client.MQTTv311,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        if config.username_env and config.password_env:
            username = os.environ.get(config.username_env)
            password = os.environ.get(config.password_env)
            if username is None or password is None:
                raise ValueError("MQTT credential environment variables are not set")
            self._client.username_pw_set(username, password)
        if config.tls:
            self._client.tls_set()

    def connect(self) -> None:
        self._client.connect(self.config.host, self.config.port, keepalive=60)
        self._client.loop_start()
        if not self._connected.wait(self.config.connect_timeout_seconds):
            self.close()
            raise TimeoutError("Timed out waiting for MQTT connection")
        if self._connect_result is not None:
            self.close()
            raise ConnectionError("MQTT connection rejected: {}".format(self._connect_result))
        LOGGER.info("Connected to MQTT broker at %s:%s", self.config.host, self.config.port)

    def publish(self, measurement: Measurement) -> None:
        if not self._connected.wait(self.config.connect_timeout_seconds):
            raise ConnectionError("MQTT broker is not connected")
        topic = measurement.topic(self.config.basetopic)
        result = self._client.publish(topic, measurement.payload, qos=self.config.qos, retain=False)
        if result.rc != mqtt_client.MQTT_ERR_SUCCESS:
            raise ConnectionError("MQTT publish failed with code {}".format(result.rc))
        result.wait_for_publish(timeout=self.config.publish_timeout_seconds)
        if not result.is_published():
            raise TimeoutError("Timed out publishing to {}".format(topic))

    def close(self) -> None:
        if self._client.is_connected():
            self._client.disconnect()
        self._client.loop_stop()
        self._connected.clear()

    def _on_connect(self, _client, _userdata, _flags, reason_code, _properties) -> None:
        if reason_code == 0:
            self._connect_result = None
            self._connected.set()
        else:
            self._connect_result = str(reason_code)
            self._connected.set()

    def _on_disconnect(self, _client, _userdata, _disconnect_flags, reason_code, _properties) -> None:
        self._connected.clear()
        if reason_code != 0:
            LOGGER.warning("Disconnected from MQTT broker: %s", reason_code)

    def __enter__(self) -> "MqttPublisher":
        self.connect()
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback) -> None:
        self.close()