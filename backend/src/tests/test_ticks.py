import pytest

from src.server.models.enums import to_ticks


@pytest.mark.parametrize("seconds, ticks", [
    (0, 0),
    (0.033, 1),
    (0.25, 8),  # 7.58 ticks end on the 8th
    (0.264, 8),  # exactly 8 ticks despite float noise
    (1.056, 32),  # Ignite interval
    (5, 152),  # 151.5 ticks
])
def test_to_ticks_rounds_up_to_whole_ticks(seconds, ticks):
    assert to_ticks(seconds) == ticks
