import pytest

from models import Measurement


def test_measurement_uses_emoncms_topic_and_numeric_payload() -> None:
    measurement = Measurement("weather_opio", "temperature_c", 18.5)

    assert measurement.topic("emon") == "emon/weather_opio/temperature_c"
    assert measurement.payload == "18.5"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True])
def test_measurement_rejects_non_numeric_or_non_finite_values(value: float) -> None:
    with pytest.raises(ValueError):
        Measurement("weather_opio", "temperature_c", value)