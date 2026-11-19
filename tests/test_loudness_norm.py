import pytest
from audio import loudness_norm as mod

CASES = [
    ("integrated", 'm.integrated_loudness(10.0, 2.0) == approx(5.0)'),
    ("gate_abs", 'm.gate_abs(5.0, 4.0) == approx(5.0)'),
    ("gate_abs_low", 'm.gate_abs(3.0, 4.0) == approx(0.0)'),
    ("gate_rel", 'm.gate_rel(5.0, 4.0) == approx(5.0)'),
    ("gate_rel_low", 'm.gate_rel(3.0, 4.0) == approx(0.0)'),
    ("multichannel", 'm.multichannel_sum([1.0, 2.0], [0.5, 0.5]) == approx(1.5)'),
    ("peak", 'm.true_peak([-2.0, 1.0]) == approx(2.0)'),
    ("target_game", 'm.target_lufs("game") == -23'),
    ("target_stream", 'm.target_lufs("stream") == -16'),
    ("bus", 'm.bus_group("music:main") == "music"'),
    ("block", 'm.block_boundary(4, 4) is True'),
    ("order", 'm.compression_order(True) == "compress"'),
    ("device", 'm.device_window(48000, 24000) == 2'),
    ("dialogue", 'm.dialogue_boost(True, 2.0) == approx(2.0)'),
    ("cache", 'm.cache_gain(2.0, "v1") == (2.0, "v1")')
]

@pytest.mark.parametrize("name,expr", CASES, ids=[c[0] for c in CASES])
def test_contract(name, expr):
    assert eval(expr, {"m": mod, "approx": pytest.approx})
