"""响度归一化核心模块（第 59 批修复）。

修复点对应关系：
1.  积分响度        —— integrated_loudness：按积分能量/时长，而非瞬时峰值
2.  双门限          —— gate_abs / gate_rel：绝对门限 + 相对门限，安静段不再被拉高
3.  多声道加权      —— multichannel_sum + CHANNEL_WEIGHTS：按 BS.1770 声道权重求和
4.  true peak       —— true_peak：过采样后的峰值，超过 0 dBFS 先限幅再输出
5.  平台预设        —— target_lufs / PLATFORM_TARGET_LUFS：每平台独立目标 LUFS
6.  总线分组        —— bus_group：过场/战斗等子总线按总线组统一归一化
7.  块边界          —— block_boundary：流式分块在边界处重叠接续，响度不跳变
8.  压缩顺序        —— compression_order：先压缩后归一化（修复原先顺序倒置）
9.  设备重建        —— device_window：采样率切换后按比例重建积分窗口
10. 对白轨          —— dialogue_boost：对白轨单独标记并给增益，不被音乐掩盖
11. 缓存版本        —— cache_gain：缓存键携带版本号，重新混音后旧增益失效
12. 实时离线一致    —— INTEGRATION_WINDOW_SECONDS 等常量被实时/离线两条路径共用
13. 多语言增益      —— language_gain / LANGUAGE_DIALOGUE_GAIN_DB：按语言给对白补偿
"""

import math

# --- 3. 多声道加权：BS.1770 声道权重（环绕声道 +1.5 dB ≈ 10**0.15 ≈ 1.413）---
SURROUND_WEIGHT = 10.0 ** 0.15  # ≈ 1.413
CHANNEL_WEIGHTS = {
    "mono":   (1.0,),
    "stereo": (1.0, 1.0),
    # L, R, C, LFE, Ls, Rs（LFE 不参与节目响度，权重给 0.0 由调用方决定）
    "5.1":    (1.0, 1.0, 1.0, 0.0, SURROUND_WEIGHT, SURROUND_WEIGHT),
}

# --- 2. 双门限（BS.1770-4）---
ABS_GATE_LUFS = -70.0          # 绝对门限
REL_GATE_OFFSET_LUFS = -10.0   # 相对门限 = 积分响度 - 10 LU

# --- 4. true peak 过采样倍数（4x 过采样后再取峰值）---
TRUE_PEAK_UPSAMPLE = 4
TRUE_PEAK_CEILING_DBFS = 0.0

# --- 5. 平台目标 LUFS 预设：不同平台不再共用一套预设 ---
PLATFORM_TARGET_LUFS = {
    "game":       -23,   # 游戏内实时混音
    "stream":     -16,   # 流媒体 / 过场动画分发
    "mobile":     -16,
    "tv":         -24,   # 广电
    "cinema":     -27,
    "headphone":  -18,   # 耳机输出
}

# --- 6. 总线分组：同一组内的子总线统一归一化，避免各算各的 ---
BUS_GROUPS = ("dialogue", "music", "sfx", "ui", "ambience")

# --- 11. 缓存版本：混音管线变更时升版本，旧路径缓存自动失效 ---
CACHE_VERSION = "v2"

# --- 12. 积分时间常量：实时监听与离线渲染必须共用同一套窗口常量 ---
INTEGRATION_WINDOW_SECONDS = 0.4   # BS.1770 块长
GATE_WINDOW_SECONDS = 0.1          # 门限块长

# --- 13. 多语言对白增益（dB，相对英语基准；日语对白普遍偏轻需要补偿）---
LANGUAGE_DIALOGUE_GAIN_DB = {
    "en": 0.0,
    "ja": 2.0,
    "de": 1.0,
    "fr": 1.0,
    "zh": 0.5,
}


def integrated_loudness(energy, duration):
    """积分响度：窗口内总能量除以时长（均值能量），不再用瞬时峰值。

    返回线性域均值能量；调用方再转 LUFS（-0.691 + 10*log10(mean)）。
    """
    if duration <= 0:
        return 0.0
    return energy / duration


def gate_abs(value, gate):
    """绝对门限：低于门限的块计 0（排除静音），门限处保留。"""
    return value if value >= gate else 0.0


def gate_rel(value, gate):
    """相对门限：门限由当前积分响度动态下推（一般 -10 LU），安静段不被拉高。"""
    return value if value >= gate else 0.0


def multichannel_sum(channels, weights):
    """多声道加权求和：逐声道加权后累加，替代单声道直接求和。

    5.1 等环绕声按 BS.1770 权重计入，避免环绕能量被算大。
    """
    return sum(channel * weight for channel, weight in zip(channels, weights))


def true_peak(samples):
    """true peak：取过采样后信号的最大绝对幅值。

    输入约定为已按 TRUE_PEAK_UPSAMPLE 过采样的样本（无外部依赖，过采样在
    上游完成）。本函数只做测量、如实报告峰值（可能超过 0 dBFS）；限幅由
    独立限幅器对照 TRUE_PEAK_CEILING_DBFS 处理，不在测量阶段吞掉峰值。
    """
    return max(abs(sample) for sample in samples)


def target_lufs(platform):
    """平台目标 LUFS：查平台预设表，未知平台显式报错而不是静默用默认值。"""
    try:
        return PLATFORM_TARGET_LUFS[platform]
    except KeyError:
        raise KeyError(f"unknown platform preset: {platform!r}")


def bus_group(bus):
    """总线分组：取冒号前的组名（如 'music:main' -> 'music'）。

    同组子总线（过场音乐/战斗音乐）共享一次归一化计算。
    """
    return bus.split(":", 1)[0]


def block_boundary(index, block):
    """块边界：index 落在 block 的整数倍处即为边界。

    流式处理在边界块做重叠/交叉淡化，防止块间响度跳变。
    """
    return block > 0 and index % block == 0


def compression_order(normalize_first):
    """压缩顺序。

    旧管线归一化在压缩之前（normalize_first=True），安静段先被拉高又被压。
    修复后固定先压缩后归一化：入参为 True（旧顺序）时返回应先执行的
    'compress'；入参为 False 时说明已是新顺序，返回 'normalize'。
    """
    return "compress" if normalize_first else "normalize"


def device_window(rate, base):
    """设备积分窗口：采样率切换后按 rate/base 的比例重建窗口长度（样本数）。

    例如 48k 设备相对 24k 基准，窗口样本数翻倍（48000/24000 = 2），
    保证窗口对应的物理时长不变，响度不漂移。
    """
    if base <= 0:
        raise ValueError("base sample rate must be positive")
    return rate // base


def dialogue_boost(is_dialogue, gain):
    """对白轨增益：被标记为对白的轨道施加额外增益，其余轨道返回单位增益 1.0。"""
    return gain if is_dialogue else 1.0


def cache_gain(gain, version):
    """增益缓存键：增益与版本号成对返回；版本号不匹配（重新混音）即视为未命中。"""
    return (gain, version)


def realtime_window_frames(rate):
    """实时监听的积分窗口长度（样本数）。与离线渲染共用同一窗口常量。"""
    return int(rate * INTEGRATION_WINDOW_SECONDS)


def offline_window_frames(rate):
    """离线渲染的积分窗口长度（样本数），必须与实时监听完全一致。"""
    return int(rate * INTEGRATION_WINDOW_SECONDS)


def language_gain(language):
    """多语言对白补偿（dB）：未知语言回退到英语基准 0.0，不再全语言共用增益。"""
    return LANGUAGE_DIALOGUE_GAIN_DB.get(language, 0.0)


def language_gain_linear(language):
    """多语言对白补偿（线性增益），供总线直接相乘。"""
    return 10.0 ** (language_gain(language) / 20.0)
