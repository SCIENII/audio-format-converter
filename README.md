# 音频格式转换器 (Audio Format Converter)

纯本地运行的加密音频格式解密转换工具，支持网易云、酷狗、QQ音乐等平台的加密格式转为通用格式。

**完全免费、开源、无广告、无会员、无任何授权验证。**

## 支持的格式

| 平台 | 加密格式 | 说明 |
|------|----------|------|
| 网易云音乐 | `.ncm` | NCM 容器解密 |
| 酷狗音乐 | `.kgm` / `.kgma` / `.mgg` / `.mflac` / `.mflac0` | KGM/MGG 系列 |
| QQ音乐 | `.qmc0` / `.qmc3` / `.qmcflac` / `.qmcogg` / `.mflac` | QMC 系列 |

解密后通过 FFmpeg 转为 MP3 或其他通用格式。

## 功能特性

- 拖拽批量导入
- 彩色分级日志输出
- 实时进度条
- 全局异常捕获，不会闪退
- 纯本地处理，不联网、不上传任何文件

## 环境要求

- Python 3.9+
- FFmpeg（需在 PATH 中，或放在程序同目录）

## 安装

```bash
pip install -r requirements.txt
```

## 运行

```bash
python converter_gui.py
```

Windows 下也可直接双击 `run.bat`。

## 打包为 EXE

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --icon=icon.ico --add-data "core;core" converter_gui.py
```

## 项目结构

```
.
├── converter_gui.py        # GUI 主程序
├── core/
│   ├── ncm_decrypt.py      # 网易云 NCM 解密
│   ├── kgm_decrypt.py      # 酷狗 KGM/MGG 解密
│   ├── qmc_decrypt.py      # QQ音乐 QMC 解密
│   └── converter.py        # FFmpeg 转码封装
├── icon.ico
├── run.bat
└── requirements.txt
```

## 免责声明

本项目仅供**个人学习和技术研究**使用，用于解密你自己合法购买的音乐文件以便在个人设备上播放。

请勿将本工具用于：
- 传播、分发受版权保护的音乐
- 任何商业用途
- 任何侵犯版权方权益的行为

使用者需自行承担因使用本工具产生的一切法律责任。音乐版权归各版权方所有，请支持正版。

## 许可证

MIT License
