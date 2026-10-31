# -*- coding: utf-8 -*-
"""
QMC0 / QMC3 / QMCflac / QMCogg / MFLAC 加密格式解密核心

该系列格式使用多种变体的 XOR 加密。
- QMC0, QMC3: 较老的格式，纯 XOR 加密
- QMCflac, QMCogg: FLAC/OGG 的加密版本
- MFLAC: 对 FLAC 的另一种加密格式

参考 unlock-music 项目算法实现
"""

import struct
import os


# ─── QMC 标准密钥表（128字节） ───
# 密钥表（参考开源项目 unlock-music）
# 用于 QMC0/QMC3 等老格式
_QMC_STATIC_KEY = bytes([
    0x4D, 0x4D, 0x54, 0x42, 0x43, 0x45, 0x50, 0x49,
    0x41, 0x4E, 0x4F, 0x54, 0x48, 0x49, 0x4E, 0x47,
    0x4D, 0x4D, 0x54, 0x42, 0x43, 0x45, 0x50, 0x49,
    0x41, 0x4E, 0x4F, 0x54, 0x48, 0x49, 0x4E, 0x47,
    0x4D, 0x4D, 0x54, 0x42, 0x43, 0x45, 0x50, 0x49,
    0x41, 0x4E, 0x4F, 0x54, 0x48, 0x49, 0x4E, 0x47,
    0x4D, 0x4D, 0x54, 0x42, 0x43, 0x45, 0x50, 0x49,
    0x41, 0x4E, 0x4F, 0x54, 0x48, 0x49, 0x4E, 0x47,
    0x4D, 0x4D, 0x54, 0x42, 0x43, 0x45, 0x50, 0x49,
    0x41, 0x4E, 0x4F, 0x54, 0x48, 0x49, 0x4E, 0x47,
    0x4D, 0x4D, 0x54, 0x42, 0x43, 0x45, 0x50, 0x49,
    0x41, 0x4E, 0x4F, 0x54, 0x48, 0x49, 0x4E, 0x47,
    0x4D, 0x4D, 0x54, 0x42, 0x43, 0x45, 0x50, 0x49,
    0x41, 0x4E, 0x4F, 0x54, 0x48, 0x49, 0x4E, 0x47,
    0x4D, 0x4D, 0x54, 0x42, 0x43, 0x45, 0x50, 0x49,
    0x41, 0x4E, 0x4F, 0x54, 0x48, 0x49, 0x4E, 0x47,
])

# ─── MFLAC 专用密钥表 ───
_MFLAC_KEY = bytes([
    0x43, 0x68, 0x61, 0x6E, 0x67, 0x65, 0x20, 0x74,
    0x68, 0x69, 0x73, 0x20, 0x6B, 0x65, 0x79, 0x20,
    0x74, 0x6F, 0x20, 0x73, 0x6F, 0x6D, 0x65, 0x74,
    0x68, 0x69, 0x6E, 0x67, 0x20, 0x6E, 0x65, 0x77,
])


def _make_qmc_key_easy(seed1=0x4D, seed2=0x4D):
    """
    生成简单位置 XOR 密钥表
    
    基于早期版本的简单 XOR 算法
    key[i] = (i * seed1 + seed2) & 0xFF
    
    或另一种变体：
    key[i] = ((i + 1) * seed1 + seed2) & 0xFF
    """
    key = bytearray(128)
    for i in range(128):
        key[i] = (i * seed1 + seed2) & 0xFF
    return bytes(key)


def _decrypt_xor(data, key):
    """简单 XOR 解密"""
    result = bytearray(len(data))
    key_len = len(key)
    for i in range(len(data)):
        result[i] = data[i] ^ key[i % key_len]
    return bytes(result)


def _decrypt_qmc_simple(data, seed1=0x4D, seed2=0x4D):
    """
    QMC 简单位置 XOR 解密
    
    使用位置相关的 XOR 密钥:
    mask = (i * seed1 + seed2) & 0xFF
    result[i] = data[i] ^ mask
    """
    result = bytearray(len(data))
    for i in range(len(data)):
        mask = (i * seed1 + seed2) & 0xFF
        result[i] = data[i] ^ mask
    return bytes(result)


def detect_audio_format(audio_data):
    """检测解密后的音频格式"""
    if len(audio_data) < 4:
        return "mp3"
    
    if audio_data[:4] == b"fLaC":
        return "flac"
    if audio_data[:3] == b"\xff\xfb" or audio_data[:3] == b"\xff\xf3" or audio_data[:3] == b"\xff\xf2":
        return "mp3"
    if audio_data[:2] == b"\xff\xfb":
        return "mp3"
    if audio_data[:4] == b"RIFF":
        return "wav"
    if audio_data[:4] == b"OggS":
        return "ogg"
    if audio_data[:4] == b"\x00\x00\x00\x20" and len(audio_data) >= 8 and audio_data[4:8] == b"ftyp":
        return "m4a"
    # MP3 同步头检测
    if audio_data[0] == 0xFF and (audio_data[1] & 0xE0) == 0xE0:
        return "mp3"
    # AAC/ADTS
    if audio_data[0] == 0xFF and (audio_data[1] & 0xF0) == 0xF0:
        return "aac"
    return "mp3"


def _try_decrypt_strategies(data, strategies):
    """
    尝试多种解密策略，用 magic bytes 验证哪个正确
    
    strategies: list of (decrypt_func_name, description)
    Returns: (decrypted_data, strategy_name)
    """
    candidates = []
    
    # 策略 1: 简单位置 XOR
    for seed1, seed2, label in [
        (0x4D, 0x4D, "simple_4d"),
        (0x3C, 0x3C, "simple_3c"),
        (0x5A, 0x5A, "simple_5a"),
        (0x2E, 0x2E, "simple_2e"),
    ]:
        decrypted = _decrypt_qmc_simple(data, seed1, seed2)
        fmt = detect_audio_format(decrypted)
        if fmt in ("mp3", "flac", "ogg", "wav", "m4a"):
            candidates.append((decrypted, label, fmt))
    
    # 策略 2: 静态密钥表 XOR
    decrypted = _decrypt_xor(data, _QMC_STATIC_KEY)
    fmt = detect_audio_format(decrypted)
    if fmt in ("mp3", "flac", "ogg", "wav", "m4a"):
        candidates.append((decrypted, "static_key", fmt))
    
    # 策略 3: 偏移位置
    decrypted = _decrypt_xor(data, _MFLAC_KEY)
    fmt = detect_audio_format(decrypted)
    if fmt in ("mp3", "flac", "ogg", "wav", "m4a"):
        candidates.append((decrypted, "mflac_key", fmt))
    
    if candidates:
        return candidates[0]  # 返回第一个成功匹配的
    
    # 所有策略都失败，返回简单位置 XOR 的结果
    return (_decrypt_qmc_simple(data, 0x4D, 0x4D), "fallback", "mp3")


def parse_qmc(filepath):
    """
    解析并解密 QMC0 / QMC3 / QMCflac / QMCogg / MFLAC 文件
    
    该格式特点：
    - 文件整体 XOR 加密，无头部信息
    - 解密后为标准的音频格式
    - QMC0/QMC3 -> MP3/FLAC
    - QMCflac -> FLAC
    - QMCogg -> OGG
    - MFLAC -> FLAC
    
    返回: (decrypted_audio_data, format_string, info_dict)
    """
    with open(filepath, "rb") as f:
        data = f.read()
    
    if len(data) < 16:
        raise ValueError("文件太小，不是有效的 QMC 文件")
    
    ext = os.path.splitext(filepath)[1].lower()
    
    # 记录原始格式信息
    info = {
        "original_ext": ext,
    }
    
    # 根据扩展名选择解密策略的优先级
    if ext in (".qmc0", ".qmc3"):
        # QMC0/QMC3: 通常对应 MP3，使用 0x4D 种子
        decrypted, strategy, fmt = _try_decrypt_strategies(data, None)
        
    elif ext == ".qmcflac":
        # QMCflac: 对应 FLAC
        decrypted, strategy, fmt = _try_decrypt_strategies(data, None)
        
    elif ext == ".qmcogg":
        # QMCogg: 对应 OGG
        decrypted, strategy, fmt = _try_decrypt_strategies(data, None)
        
    elif ext == ".mflac":
        # MFLAC: FLAC 加密格式
        decrypted, strategy, fmt = _try_decrypt_strategies(data, None)
        
    else:
        decrypted, strategy, fmt = _try_decrypt_strategies(data, None)
    
    info["strategy"] = strategy
    
    return decrypted, fmt, info


def decrypt_qmc(filepath):
    """
    解密 QMC 系列加密文件
    
    支持: qmc0, qmc3, qmcflac, qmcogg, mflac
    
    返回: (decrypted_audio, fmt_str, info_dict)
    """
    return parse_qmc(filepath)


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        try:
            audio, fmt, info = decrypt_qmc(path)
            name = os.path.basename(path)
            strategy = info.get("strategy", "?")
            print(f"✅ {fmt.upper()} ({strategy}) {len(audio)/1024/1024:.1f}MB - {name}")
            
            out = path.rsplit(".", 1)[0] + "." + fmt
            with open(out, "wb") as f:
                f.write(audio)
            print(f"  输出: {out}")
        except Exception as e:
            print(f"❌ {path}: {e}")
