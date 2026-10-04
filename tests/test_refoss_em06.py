from typing import Dict, Tuple

import pytest

from collectors.refoss_em06 import metrics_from_device


class FakeEm06:
    channels = [1, 2]

    def __init__(self, values: Dict[Tuple[int, str], float]) -> None:
        self.values = values

    def get_value(self, channel: int, key: str):
        return self.values.get((channel, key))


def test_metrics_are_normalized_and_separated_by_channel() -> None:
    device = FakeEm06(
        {
            (1, "power"): 1250,
            (1, "voltage"): 230000,
            (1, "current"): 5400,
            (1, "factor"): 0.97,
            (1, "mConsume"): 1234,
            (2, "power"): 2500,
            (2, "mConsume"): -25,
        }
    )

    measurements = metrics_from_device("refoss_em06", device)
    values = {measurement.key: measurement.value for measurement in measurements}

    assert values["channel_1_power_w"] == pytest.approx(1.25)
    assert values["channel_1_voltage_v"] == pytest.approx(230)
    assert values["channel_1_current_a"] == pytest.approx(5.4)
    assert values["channel_1_power_factor"] == pytest.approx(0.97)
    assert values["channel_1_energy_monthly_wh"] == pytest.approx(1234)
    assert values["channel_1_energy_returned_monthly_wh"] == 0
    assert values["channel_2_power_w"] == pytest.approx(2.5)
    assert values["channel_2_energy_monthly_wh"] == 0
    assert values["channel_2_energy_returned_monthly_wh"] == pytest.approx(25)
    assert measurements[0].topic("emon") == "emon/refoss_em06/channel_1_power_w"


def test_metrics_skip_missing_and_invalid_values() -> None:
    device = FakeEm06({(1, "power"): float("nan"), (1, "voltage"): 230000})

    measurements = metrics_from_device("refoss_em06", device)

    assert [(item.key, item.value) for item in measurements] == [("channel_1_voltage_v", 230)]