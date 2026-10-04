import pytest

from collectors.yf_b10 import YfB10Collector, flow_metrics_from_pulses
from config import YfB10Config


class FakeInputDevice:
    def close(self) -> None:
        pass


def test_flow_metrics_convert_frequency_to_flow() -> None:
    measurements = flow_metrics_from_pulses("yf_b10", pulse_count=44, elapsed_seconds=10)

    assert [(item.key, item.value) for item in measurements] == [
        ("frequency_hz", 4.4),
        ("flow_l_min", pytest.approx((4.4 + 4) / 8)),
    ]
    assert measurements[0].topic("emon") == "emon/yf_b10/frequency_hz"
    assert measurements[1].topic("emon") == "emon/yf_b10/flow_l_min"


def test_zero_pulses_report_zero_flow() -> None:
    measurements = flow_metrics_from_pulses("yf_b10", pulse_count=0, elapsed_seconds=10)

    assert [item.value for item in measurements] == [0, 0]


@pytest.mark.parametrize(
    ("pulse_count", "elapsed_seconds"),
    [(-1, 1), (True, 1), (1, 0), (1, float("inf"))],
)
def test_flow_metrics_reject_invalid_sample_window(pulse_count, elapsed_seconds) -> None:
    with pytest.raises(ValueError):
        flow_metrics_from_pulses("yf_b10", pulse_count, elapsed_seconds)


def test_collector_counts_edges_between_sampling_windows() -> None:
    current_time = [0.0]
    collector = YfB10Collector(
        YfB10Config(gpio_pin=16, node="yf_b10", interval_seconds=10),
        clock=lambda: current_time[0],
    )
    collector._input_device = FakeInputDevice()
    collector._last_read_time = 0.0
    for _ in range(44):
        collector._record_pulse()
    current_time[0] = 10.0

    measurements = collector.collect()

    assert [item.value for item in measurements] == [4.4, pytest.approx(1.05)]
    collector.close()