@echo off
title 音频格式转换器 v3.0
cd /d "%~dp0"
echo 正在启动 音频格式转换器 v3.0 ...
echo 支持: NCM/KGM/MGG/QMC0/QMC3/QMCflac/QMCogg/MFLAC
start "" pythonw converter_gui.py
echo 窗口已打开（如未见窗口请双击 run.bat）
