# -*- coding: utf-8 -*-
"""音频转码核心：FLAC/其他格式 → MP3"""

import subprocess
import os
import tempfile
from pathlib import Path

def flac_to_mp3(input_path, output_path=None, bitrate="320k", remove_original=False, callback=None):
    """
    将 FLAC（或其他ffmpeg支持的格式）转换为 MP3
    
    参数:
        input_path: 源文件路径
        output_path: 输出路径（默认同目录同名.mp3）
        bitrate: MP3比特率 (128k, 192k, 256k, 320k)
        remove_original: 转换后是否删除源文件
        callback: 进度回调函数
    返回:
        (成功:bool, 输出路径:str, 消息:str)
    """
    input_path = str(input_path)
    
    if not os.path.exists(input_path):
        return False, "", f"文件不存在: {input_path}"
    
    # 自动确定输出路径
    if not output_path:
        base = os.path.splitext(input_path)[0]
        output_path = base + ".mp3"
    
    # 检查是否已经是 MP3（跳过）
    ext = os.path.splitext(input_path)[1].lower()
    if ext == ".mp3":
        return True, input_path, "已是 MP3 格式，无需转换"
    
    if callback:
        callback(0, "正在分析...")
    
    try:
        # 使用 ffmpeg 转换
        cmd = [
            "ffmpeg",
            "-i", input_path,
            "-y",                              # 覆盖输出文件
            "-codec:a", "libmp3lame",           # MP3编码器
            "-b:a", bitrate,                    # 比特率
            "-q:a", "2",                        # 质量 (0-9, 0最好)
            "-map_metadata", "0",               # 保留元数据
            "-id3v2_version", "3",              # ID3v2.3兼容性更好
            "-write_id3v1", "1",
            output_path
        ]
        
        if callback:
            callback(30, "转换中...")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            startupinfo=subprocess.STARTUPINFO(),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        
        if result.returncode != 0:
            error_msg = result.stderr[-300:] if result.stderr else "未知错误"
            return False, "", f"转换失败: {error_msg}"
        
        if callback:
            callback(90, "正在处理...")
        
        # 验证输出
        if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
            return False, "", "输出文件为空"
        
        # 删除源文件
        if remove_original:
            try:
                os.remove(input_path)
            except Exception as e:
                pass  # 删除失败不阻塞
        
        if callback:
            callback(100, "完成")
        
        old_size = os.path.getsize(input_path)
        new_size = os.path.getsize(output_path)
        ratio = (1 - new_size / old_size) * 100 if old_size > 0 else 0
        
        return True, output_path, f"转换成功! 压缩: {ratio:.1f}%"
        
    except subprocess.TimeoutExpired:
        return False, "", "转换超时（超过5分钟）"
    except FileNotFoundError:
        return False, "", "未找到 ffmpeg，请安装 FFmpeg"
    except Exception as e:
        return False, "", f"转换异常: {str(e)}"


def get_audio_info(filepath):
    """获取音频文件信息"""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", str(filepath)],
            capture_output=True, text=True, timeout=15,
            startupinfo=subprocess.STARTUPINFO(),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        import json
        if result.returncode == 0 and result.stdout:
            info = json.loads(result.stdout)
            streams = info.get("streams", [])
            fmt = info.get("format", {})
            
            # 查找音频流
            audio_stream = None
            for s in streams:
                if s.get("codec_type") == "audio":
                    audio_stream = s
                    break
            
            return {
                "format": fmt.get("format_name", ""),
                "codec": audio_stream.get("codec_name", "") if audio_stream else "",
                "duration": float(fmt.get("duration", 0)),
                "bitrate": int(fmt.get("bit_rate", 0)),
                "sample_rate": int(audio_stream.get("sample_rate", 0)) if audio_stream else 0,
                "channels": audio_stream.get("channels", 0) if audio_stream else 0,
                "size": int(fmt.get("size", 0)),
            }
    except:
        pass
    return None


def get_supported_formats():
    """获取 ffmpeg 支持的音频格式列表（用于文件过滤）"""
    return [
        ("音频文件", "*.flac *.ncm *.wav *.aac *.ogg *.wma *.ape *.m4a *.opus"),
        ("FLAC", "*.flac"),
        ("NCM (网易云)", "*.ncm"),
        ("WAV", "*.wav"),
        ("AAC", "*.aac"),
        ("OGG", "*.ogg"),
        ("WMA", "*.wma"),
        ("APE", "*.ape"),
        ("M4A", "*.m4a"),
        ("Opus", "*.opus"),
        ("所有文件", "*.*"),
    ]
