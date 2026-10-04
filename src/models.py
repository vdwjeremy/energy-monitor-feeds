"""Measurement model and EmonCMS MQTT serialization."""

import math
import re
from dataclasses import dataclass
from typing import Union


Number = Union[int, float]
_TOPIC_SEGMENT = re.compile(r"^[A-Za-z0-9_.-]+$")


@dataclass(frozen=True)
class Measurement:
    node: str
    key: str
    value: Number

    def __post_init__(self) -> None:
        for label, segment in (("node", self.node), ("key", self.key)):
            if not isinstance(segment, str) or not _TOPIC_SEGMENT.fullmatch(segment):
                raise ValueError("{} must contain only letters, numbers, '_', '-' or '.'".format(label))
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise ValueError("measurement value must be numeric")
        if not math.isfinite(self.value):
            raise ValueError("measurement value must be finite")

    def topic(self, basetopic: str = "emon") -> str:
        if not _TOPIC_SEGMENT.fullmatch(basetopic):
            raise ValueError("basetopic must be one valid MQTT topic segment")
        return "{}/{}/{}".format(basetopic, self.node, self.key)

    @property
    def payload(self) -> str:
        return str(self.value)