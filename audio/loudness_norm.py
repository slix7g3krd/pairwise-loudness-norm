"""第 59 批：同一段对白在游戏里正常，切到过场动画突然炸耳，接耳机又小得听不清..."""

def integrated_loudness(energy, duration):
    """积分响度。"""
    raise NotImplementedError("TODO: integrated_loudness")

def gate_abs(value, gate):
    """绝对门限。"""
    raise NotImplementedError("TODO: gate_abs")

def gate_rel(value, gate):
    """相对门限。"""
    raise NotImplementedError("TODO: gate_rel")

def multichannel_sum(channels, weights):
    """多声道加权求和。"""
    raise NotImplementedError("TODO: multichannel_sum")

def true_peak(samples):
    """true peak。"""
    raise NotImplementedError("TODO: true_peak")

def target_lufs(platform):
    """平台目标 LUFS。"""
    raise NotImplementedError("TODO: target_lufs")

def bus_group(bus):
    """总线分组。"""
    raise NotImplementedError("TODO: bus_group")

def block_boundary(index, block):
    """块边界。"""
    raise NotImplementedError("TODO: block_boundary")

def compression_order(normalize_first):
    """压缩顺序。"""
    raise NotImplementedError("TODO: compression_order")

def device_window(rate, base):
    """设备积分窗口。"""
    raise NotImplementedError("TODO: device_window")

def dialogue_boost(is_dialogue, gain):
    """对白增益。"""
    raise NotImplementedError("TODO: dialogue_boost")

def cache_gain(gain, version):
    """增益缓存键。"""
    raise NotImplementedError("TODO: cache_gain")
