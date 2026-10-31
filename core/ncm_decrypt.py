# -*- coding: utf-8 -*-
"""
NCM 文件解密核心
参考 taurusxin/ncmdump (C++) 实现重写
修复：AES密钥、XOR预处理、自定义流密码
"""

import struct
import base64
from Crypto.Cipher import AES


# ─── 固定密钥（来自 C++ 源码） ───
CORE_KEY = bytes([
    0x68, 0x7A, 0x48, 0x52, 0x41, 0x6D, 0x73, 0x6F,
    0x35, 0x6B, 0x49, 0x6E, 0x62, 0x61, 0x78, 0x57
])  # "hzRAmso5kInbaxW"

MODIFY_KEY = bytes([
    0x23, 0x31, 0x34, 0x6C, 0x6A, 0x6B, 0x5F, 0x21,
    0x5C, 0x5D, 0x26, 0x30, 0x55, 0x3C, 0x27, 0x28
])  # "#14ljk_!\\]&0U<("


def aes_ecb_decrypt(key, data):
    """AES-128-ECB 解密，处理 PKCS7 填充"""
    n = len(data) // 16
    cipher = AES.new(key, AES.MODE_ECB)
    out = b""
    for i in range(n - 1):
        out += cipher.decrypt(data[i*16:(i+1)*16])
    # 最后一个块，去掉 PKCS7 填充
    last = cipher.decrypt(data[(n-1)*16:n*16])
    pad = last[-1]
    if pad > 16:
        pad = 0
    out += last[:16-pad]
    return out


def build_key_box(key):
    """构建自定义 KeyBox（ncmdump 特有算法，非标准 RC4）"""
    box = list(range(256))
    last_byte = 0
    key_offset = 0
    key_len = len(key)
    for i in range(256):
        swap = box[i]
        c = (swap + last_byte + key[key_offset]) & 0xFF
        key_offset += 1
        if key_offset >= key_len:
            key_offset = 0
        box[i] = box[c]
        box[c] = swap
        last_byte = c
    return box


def stream_decrypt(data, key_box):
    """自定义流解密（ncmdump 特有算法）"""
    out = bytearray(len(data))
    for i in range(len(data)):
        j = (i + 1) & 0xFF
        k = (key_box[j] + key_box[(key_box[j] + j) & 0xFF]) & 0xFF
        out[i] = data[i] ^ key_box[k]
    return bytes(out)


def parse_ncm(filepath):
    """
    解析并解密 NCM 文件

    文件结构（ncmdump C++ 实现）:
      [0:4]   0x4e455443 "CTEN"
      [4:8]   0x4d414446 "FDAM"
      [8:10]  跳过2字节
      [10:14] Key长度 (uint32 LE)
      [14:14+N] Key数据（先 XOR 0x64，再 AES-ECB 解密）
               → 取 [17:] 作为 KeyBox 种子
      [14+N:14+N+4] Metadata长度 (uint32 LE)
      [14+N+4:14+N+4+M] Metadata数据
               → XOR 0x63 → 跳过22字节("163 key(Don't modify):")
               → Base64解码 → AES-ECB解密 → 跳过"music:"
               → JSON
      [后面:]  CRC32(4) + 图片版本(1) = 5字节跳过
              封面帧长度(4) + 封面数据长度(4) + 封面数据(N)
              + (封面帧长度 - 封面数据长度) 跳过
              音频数据（用 KeyBox 自定义流解密）
    """
    with open(filepath, "rb") as f:
        data = f.read()

    if len(data) < 20:
        raise ValueError("文件太小")

    # ─── 验证魔数 ───
    magic1 = struct.unpack_from("<I", data, 0)[0]  # 0x4e455443 = "CTEN"
    magic2 = struct.unpack_from("<I", data, 4)[0]  # 0x4d414446 = "FDAM"
    if magic1 != 0x4e455443 or magic2 != 0x4d414446:
        raise ValueError(f"不是NCM文件: {data[:8]}")

    offset = 8

    # ─── 跳过2字节 ───
    offset += 2

    # ─── 读 Key ───
    key_length = struct.unpack_from("<I", data, offset)[0]
    offset += 4

    key_data = bytearray(data[offset:offset + key_length])
    offset += key_length

    # XOR 0x64
    for i in range(len(key_data)):
        key_data[i] ^= 0x64

    # AES-ECB 解密（用 CORE_KEY）
    decrypted_key = aes_ecb_decrypt(CORE_KEY, bytes(key_data))

    # 构建 KeyBox（从第17字节开始）
    key_box = build_key_box(decrypted_key[17:])

    # ─── 读取 Metadata ───
    metadata = {}
    if offset + 4 <= len(data):
        meta_length = struct.unpack_from("<I", data, offset)[0]
        offset += 4

        if meta_length > 0 and offset + meta_length <= len(data):
            modify_data = bytearray(data[offset:offset + meta_length])
            offset += meta_length

            # XOR 0x63
            for i in range(len(modify_data)):
                modify_data[i] ^= 0x63

            try:
                # 跳过前22字节 "163 key(Don't modify):"
                meta_b64 = bytes(modify_data[22:])
                # Base64 解码
                meta_encrypted = base64.b64decode(meta_b64)
                # AES-ECB 解密（用 MODIFY_KEY）
                meta_decrypted = aes_ecb_decrypt(MODIFY_KEY, meta_encrypted)
                # 跳过 "music:" (6字节)
                meta_json = meta_decrypted[6:].decode("utf-8", errors="replace")

                import json
                metadata = json.loads(meta_json)
            except Exception:
                pass  # metadata 解析失败不阻塞

    # ─── 跳过 CRC32(4) + 图片版本(1) = 5字节 ───
    offset += 5

    # ─── 读取封面图片 ───
    cover_data = None
    if offset + 8 <= len(data):
        cover_frame_len = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        image_len = struct.unpack_from("<I", data, offset)[0]
        offset += 4
        if image_len > 0 and offset + image_len <= len(data):
            cover_data = data[offset:offset + image_len]
            offset += image_len
        # 跳过剩余帧数据
        remaining = cover_frame_len - image_len
        if remaining > 0 and offset + remaining <= len(data):
            offset += remaining

    # ─── 解密音频数据（自定义流解密） ───
    encrypted_audio = data[offset:]
    audio_data = stream_decrypt(encrypted_audio, key_box)

    # ─── 判断格式并提取元数据 ───
    fmt = "mp3"
    if audio_data[:4] == b"fLaC":
        fmt = "flac"

    song_info = {}
    if metadata:
        song_info["name"] = metadata.get("musicName", metadata.get("name", ""))
        artists = metadata.get("artist", [])
        if isinstance(artists, list):
            parts = []
            for a in artists:
                if isinstance(a, list) and len(a) > 0:
                    parts.append(str(a[0]))
                elif isinstance(a, str):
                    parts.append(a)
            song_info["artist"] = "/".join(parts)
        else:
            song_info["artist"] = str(artists)
        song_info["album"] = metadata.get("album", metadata.get("albumText", ""))
        song_info["format"] = metadata.get("format", fmt)
        if metadata.get("format"):
            fmt = metadata["format"]

    song_info["cover"] = cover_data

    return audio_data, fmt, song_info


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        try:
            audio, fmt, info = parse_ncm(path)
            name = info.get("name", "")
            artist = info.get("artist", "")
            tag = f" - {name} - {artist}" if name else ""
            print(f"✅ {fmt.upper()} {len(audio)/1024/1024:.1f}MB{tag}")

            out = path.rsplit(".", 1)[0] + "." + fmt
            with open(out, "wb") as f:
                f.write(audio)
            print(f"  输出: {out}")
        except Exception as e:
            print(f"❌ {path}: {e}")
