# -*- coding: utf-8 -*-
"""
NCM/FLAC → MP3 音频格式转换器 v2.0
功能: 拖拽导入 | 颜色日志 | 菜单操作 | 防闪退 | 进度条
"""

import sys
import os
import threading
import queue
import time
import traceback
from pathlib import Path

# ─── 防闪退：全局异常捕获 ───
def global_excepthook(exc_type, exc_value, exc_traceback):
    msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    try:
        import tkinter.messagebox
        tkinter.messagebox.showerror("程序异常",
            f"发生未捕获的异常:\n\n{exc_value}\n\n日志已保存到桌面 error.log")
    except:
        pass
    with open(os.path.join(os.path.expanduser("~"), "Desktop", "error.log"), "w") as f:
        f.write(msg)

sys.excepthook = global_excepthook

# ─── 导入核心 ───
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from core.ncm_decrypt import parse_ncm
    from core.kgm_decrypt import decrypt_kgm_mgg
    from core.qmc_decrypt import decrypt_qmc
    from core.converter import flac_to_mp3, get_supported_formats
except ImportError:
    parent = str(Path(__file__).parent)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    from core.ncm_decrypt import parse_ncm
    from core.kgm_decrypt import decrypt_kgm_mgg
    from core.qmc_decrypt import decrypt_qmc
    from core.converter import flac_to_mp3, get_supported_formats

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES

APP_DIR = Path(__file__).parent
ICON_PATH = APP_DIR / "icon.ico"
ICON_PNG = APP_DIR / "icon.png"


class ColoredLog(tk.Text):
    """带颜色的日志控件"""
    COLORS = {
        "INFO": "#0ecb81",
        "WARN": "#f0b90b",
        "ERROR": "#f6465d",
        "DEBUG": "#707a8a",
        "SYSTEM": "#2d8cf0",
    }

    def write(self, text, tag="INFO"):
        self.config(state="normal")
        color = self.COLORS.get(tag, "white")
        self.insert("end", text, (tag,))
        self.tag_config(tag, foreground=color, font=("Consolas", 9))
        self.see("end")
        self.config(state="disabled")
        self.update_idletasks()


class AudioConverterApp:
    def __init__(self):
        # ─── 正式初始化 ───
        self.root = TkinterDnD.Tk()
        self.root.title("🎵 音频格式转换器 v3.0 - 支持NCM/FLAC/KGM/MGG/QMC")
        self.root.geometry("950x700")
        self.root.minsize(800, 550)

        # 图标
        if ICON_PATH.exists():
            try:
                self.root.iconbitmap(str(ICON_PATH))
            except:
                pass
        elif ICON_PNG.exists():
            try:
                from PIL import Image, ImageTk
                img = Image.open(ICON_PNG)
                self.root.iconphoto(True, ImageTk.PhotoImage(img))
            except:
                pass

        # 变量
        self.file_records = []
        self.output_dir = tk.StringVar(value=str(Path.home() / "Desktop" / "转换输出"))
        self.bitrate_var = tk.StringVar(value="320k")
        self.remove_orig = tk.BooleanVar(value=False)
        self.converting = False
        self.log_queue = queue.Queue()

        # 样式
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=5)
        style.configure("Primary.TButton", foreground="white", background="#2d8cf0")
        style.map("Primary.TButton", background=[("active", "#1a6fd0")])
        style.configure("Danger.TButton", foreground="white", background="#f6465d")
        style.map("Danger.TButton", background=[("active", "#c4384a")])
        style.configure("Success.TButton", foreground="white", background="#0ecb81")
        style.map("Success.TButton", background=[("active", "#0a9e65")])
        style.configure("H1.TLabel", font=("微软雅黑", 16, "bold"))
        style.configure("H2.TLabel", font=("微软雅黑", 11))

        self._build_menu()
        self._build_ui()
        self._setup_drag_drop()
        self._process_log_queue()

    # ═══════════════ 菜单 ═══════════════

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # 文件
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="📁 添加文件", command=self._add_files, accelerator="Ctrl+O")
        file_menu.add_command(label="📂 添加文件夹", command=self._add_folder, accelerator="Ctrl+F")
        file_menu.add_separator()
        file_menu.add_command(label="🗑️ 清空列表", command=self._clear_list)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit, accelerator="Ctrl+Q")
        menubar.add_cascade(label="文件", menu=file_menu)

        # 转换
        conv_menu = tk.Menu(menubar, tearoff=0)
        conv_menu.add_command(label="🚀 开始转换", command=self._start_conversion, accelerator="Ctrl+R")
        conv_menu.add_command(label="⏹️ 停止转换", command=self._stop_conversion)
        conv_menu.add_separator()
        conv_menu.add_command(label="🔄 刷新文件列表", command=self._refresh_list)
        menubar.add_cascade(label="转换", menu=conv_menu)

        # 设置
        set_menu = tk.Menu(menubar, tearoff=0)
        set_menu.add_command(label="选择输出目录", command=self._choose_output)
        bitrate_menu = tk.Menu(set_menu, tearoff=0)
        for b in ["128k", "192k", "256k", "320k"]:
            bitrate_menu.add_command(label=b, command=lambda v=b: self.bitrate_var.set(v))
        set_menu.add_cascade(label="比特率", menu=bitrate_menu)
        set_menu.add_checkbutton(label="转换后删除源文件", variable=self.remove_orig)
        menubar.add_cascade(label="设置", menu=set_menu)

        # 帮助
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="📖 使用说明", command=self._show_help)
        help_menu.add_command(label="ℹ️ 关于", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)

        # 快捷键
        self.root.bind("<Control-o>", lambda e: self._add_files())
        self.root.bind("<Control-f>", lambda e: self._add_folder())
        self.root.bind("<Control-r>", lambda e: self._start_conversion())
        self.root.bind("<Control-q>", lambda e: self.root.quit())

    # ═══════════════ 界面 ═══════════════

    def _build_ui(self):
        # ─── 顶栏 ───
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=10, pady=8)

        ttk.Label(top, text="🎵 音频转换器", style="H1.TLabel").pack(side="left")
        ttk.Label(top, text="NCM / FLAC / KGM / MGG / QMC → MP3", style="H2.TLabel",
                  foreground="#707a8a").pack(side="left", padx=12)

        self.count_label = ttk.Label(top, text="共 0 个文件", foreground="#2d8cf0",
                                      font=("微软雅黑", 10, "bold"))
        self.count_label.pack(side="right")

        # ─── 拖拽提示区 ───
        self.drop_frame = ttk.LabelFrame(self.root, text="📥 拖拽区域", padding=15)
        self.drop_frame.pack(fill="x", padx=10, pady=(0, 5))

        self.drop_label = ttk.Label(self.drop_frame,
            text="将 NCM / FLAC / KGM / MGG / QMC / MFLAC 文件或文件夹拖拽到这里\n也可点击下方按钮添加",
            foreground="#707a8a", font=("微软雅黑", 10),
            justify="center", anchor="center")
        self.drop_label.pack(fill="x", pady=5)

        # 按钮栏
        btn_bar = ttk.Frame(self.drop_frame)
        btn_bar.pack(pady=3)
        ttk.Button(btn_bar, text="📁 添加文件", command=self._add_files).pack(side="left", padx=3)
        ttk.Button(btn_bar, text="📂 添加文件夹", command=self._add_folder).pack(side="left", padx=3)
        ttk.Button(btn_bar, text="🗑️ 清空", style="Danger.TButton",
                   command=self._clear_list).pack(side="left", padx=3)

        # ─── 文件列表 ───
        list_frame = ttk.LabelFrame(self.root, text="文件列表", padding=3)
        list_frame.pack(fill="both", expand=True, padx=10, pady=3)

        columns = ("#", "文件名", "类型", "大小", "状态")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                  height=10, selectmode="extended")
        for col in columns:
            self.tree.heading(col, text=col)

        self.tree.column("#", width=35, anchor="center")
        self.tree.column("文件名", width=380)
        self.tree.column("类型", width=70, anchor="center")
        self.tree.column("大小", width=90, anchor="e")
        self.tree.column("状态", width=180, anchor="center")

        scroll_y = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll_y.pack(side="right", fill="y")

        # ─── 设置栏 ───
        set_bar = ttk.Frame(self.root)
        set_bar.pack(fill="x", padx=10, pady=3)

        ttk.Label(set_bar, text="输出:").pack(side="left")
        self.out_entry = ttk.Entry(set_bar, textvariable=self.output_dir, width=35)
        self.out_entry.pack(side="left", padx=4)
        ttk.Button(set_bar, text="浏览", command=self._choose_output).pack(side="left")

        ttk.Label(set_bar, text=" 比特率:").pack(side="left", padx=(15, 3))
        ttk.Combobox(set_bar, textvariable=self.bitrate_var,
                      values=["128k", "192k", "256k", "320k"],
                      width=6, state="readonly").pack(side="left")

        ttk.Checkbutton(set_bar, text="删除源文件",
                         variable=self.remove_orig).pack(side="left", padx=10)

        ttk.Button(set_bar, text="🚀 开始转换", style="Primary.TButton",
                   command=self._start_conversion).pack(side="right", padx=3)

        # ─── 进度条 ───
        prog_frame = ttk.Frame(self.root)
        prog_frame.pack(fill="x", padx=10, pady=3)

        self.progress = ttk.Progressbar(prog_frame, mode="determinate", length=0)
        self.progress.pack(fill="x", side="left", expand=True)

        self.prog_label = ttk.Label(prog_frame, text="就绪", width=20, anchor="e")
        self.prog_label.pack(side="right", padx=5)

        # ─── 彩色日志 ───
        log_frame = ttk.LabelFrame(self.root, text="运行日志", padding=3)
        log_frame.pack(fill="x", padx=10, pady=(0, 5))

        self.log = ColoredLog(log_frame, height=8, bg="#1e2329",
                               fg="#a0a0a0", wrap="none", state="disabled")
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=log_scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        log_scroll.pack(side="right", fill="y")

        self.log.write("🟢 程序已启动 | 支持拖拽文件或文件夹\n", "SYSTEM")

    # ═══════════════ 拖拽 ═══════════════

    def _setup_drag_drop(self):
        # 注册拖拽目标
        self.root.drop_target_register(DND_FILES)
        self.root.dnd_bind("<<Drop>>", self._on_drop)
        # 也让标签和frame接收拖拽
        self.drop_frame.drop_target_register(DND_FILES)
        self.drop_frame.dnd_bind("<<Drop>>", self._on_drop)
        self.drop_label.drop_target_register(DND_FILES)
        self.drop_label.dnd_bind("<<Drop>>", self._on_drop)

    def _on_drop(self, event):
        """处理拖拽文件"""
        import re
        # tkinterdnd2传入的data包含文件路径，{path1 path2}格式
        raw = event.data
        self.log.write(f"📥 检测到拖拽: {raw[:80]}...\n", "INFO")

        # 解析路径 (支持空格路径)
        files = re.findall(r'\{([^}]*)\}|(\S+)', raw)
        paths = [a or b for a, b in files]

        added = 0
        for p in paths:
            p = p.strip('"\' ')
            if not p:
                continue
            if os.path.isdir(p):
                added += self._scan_folder(p)
            elif os.path.isfile(p):
                if self._add_file(p):
                    added += 1

        if added:
            self.log.write(f"✅ 已添加 {added} 个文件\n", "INFO")
            self._update_count()
        else:
            self.log.write("⚠️ 未找到可处理的音频文件\n", "WARN")

    # ═══════════════ 文件操作 ═══════════════

    def _add_files(self):
        files = filedialog.askopenfilenames(
            title="选择音频文件",
            filetypes=[
                ("音频文件", "*.flac *.ncm *.wav *.aac *.ogg *.wma *.ape *.m4a *.opus *.kgm *.mgg *.qmc0 *.qmc3 *.qmcflac *.qmcogg *.mflac"),
                ("NCM 格式", "*.ncm"),
                ("FLAC", "*.flac"),
                ("KGM 格式", "*.kgm"),
                ("MGG 格式", "*.mgg"),
                ("QMC0/QMC3 格式", "*.qmc0 *.qmc3"),
                ("QMCflac/QMCogg/MFLAC 格式", "*.qmcflac *.qmcogg *.mflac"),
                ("所有文件", "*.*"),
            ]
        )
        count = 0
        for f in files:
            if self._add_file(f):
                count += 1
        if count:
            self.log.write(f"✅ 添加 {count} 个文件\n", "INFO")
            self._update_count()

    def _add_folder(self):
        folder = filedialog.askdirectory(title="选择文件夹")
        if folder:
            count = self._scan_folder(folder)
            if count:
                self.log.write(f"✅ 从文件夹添加 {count} 个文件\n", "INFO")
                self._update_count()
            else:
                self.log.write(f"⚠️ 文件夹中未找到音频文件\n", "WARN")

    def _scan_folder(self, folder):
        """递归扫描文件夹"""
        exts = {".ncm", ".flac", ".wav", ".aac", ".ogg", ".wma", ".ape", ".m4a", ".opus",
                ".kgm", ".mgg", ".qmc0", ".qmc3", ".qmcflac", ".qmcogg", ".mflac"}
        count = 0
        for root_dir, _, files in os.walk(folder):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in exts:
                    if self._add_file(os.path.join(root_dir, f)):
                        count += 1
        return count

    def _add_file(self, filepath):
        filepath = os.path.normpath(filepath)
        for item in self.tree.get_children():
            if self.tree.item(item)["values"][0] == filepath:
                return False

        ext = os.path.splitext(filepath)[1].upper()[1:]
        size = os.path.getsize(filepath)
        size_str = self._fmt_size(size)

        self.tree.insert("", "end", iid=filepath, values=(
            filepath, os.path.basename(filepath), ext, size_str, "⏳ 等待中"
        ))
        return True

    def _clear_list(self):
        if not self.tree.get_children():
            return
        if messagebox.askyesno("确认", "清空文件列表？"):
            for item in self.tree.get_children():
                self.tree.delete(item)
            self._update_count()
            self.log.write("🗑️ 列表已清空\n", "INFO")

    def _update_count(self):
        count = len(self.tree.get_children())
        self.count_label.config(text=f"共 {count} 个文件")

    def _refresh_list(self):
        self._update_count()

    def _choose_output(self):
        folder = filedialog.askdirectory(title="选择输出目录",
                                          initialdir=self.output_dir.get())
        if folder:
            self.output_dir.set(folder)

    def _fmt_size(self, size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def _set_status(self, item, text):
        if self.tree.exists(item):
            vals = list(self.tree.item(item)["values"])
            vals[4] = text
            self.tree.item(item, values=vals)

    # ═══════════════ 转换核心 ═══════════════

    def _start_conversion(self):
        if self.converting:
            self.log.write("⚠️ 转换正在进行中...\n", "WARN")
            return

        files = self.tree.get_children()
        if not files:
            self.log.write("⚠️ 请先添加文件\n", "WARN")
            return

        out_dir = self.output_dir.get()
        try:
            os.makedirs(out_dir, exist_ok=True)
        except Exception as e:
            self.log.write(f"❌ 无法创建输出目录: {e}\n", "ERROR")
            return

        self.converting = True
        self.progress["maximum"] = len(files)
        self.progress["value"] = 0

        thread = threading.Thread(target=self._convert_all,
                                   args=(list(files), out_dir), daemon=True)
        thread.start()

    def _stop_conversion(self):
        if not self.converting:
            self.log.write("⚠️ 当前无进行中的转换\n", "WARN")
            return
        # 简单地标记停止 - 当前文件转换完就停
        self.converting = False
        self.log.write("⏹️ 转换即将停止...\n", "WARN")

    def _convert_all(self, files, out_dir):
        total = len(files)
        bitrate = self.bitrate_var.get()
        success_count = 0
        fail_count = 0

        for idx, item in enumerate(files):
            if not self.converting or not self.tree.exists(item):
                break

            filepath = item
            ext = os.path.splitext(filepath)[1].lower()
            base = os.path.basename(filepath)

            self.log.write(f"[{idx+1}/{total}] 处理: {base}\n", "INFO")
            self._set_status(item, "⏳ 处理中...")
            self.prog_label.config(text=f"{idx+1}/{total}")
            self.progress["value"] = idx + 1

            try:
                if ext == ".ncm":
                    ok = self._convert_ncm(filepath, out_dir, bitrate, item)
                elif ext in (".kgm", ".mgg"):
                    ok = self._convert_encrypted(filepath, out_dir, bitrate, item, "kgm_mgg")
                elif ext in (".qmc0", ".qmc3", ".qmcflac", ".qmcogg", ".mflac"):
                    ok = self._convert_encrypted(filepath, out_dir, bitrate, item, "qmc")
                elif ext == ".mp3":
                    import shutil
                    out = os.path.join(out_dir, base)
                    shutil.copy2(filepath, out)
                    self._set_status(item, "✅ 已复制")
                    self.log.write(f"  → {base} (已是MP3)\n", "INFO")
                    ok = True
                else:
                    ok = self._convert_ffmpeg(filepath, out_dir, bitrate, item)

                if ok:
                    success_count += 1
                else:
                    fail_count += 1

            except Exception as e:
                self._set_status(item, "❌ 异常")
                self.log.write(f"  → 异常: {e}\n", "ERROR")
                traceback.print_exc()
                fail_count += 1

            self.root.update_idletasks()

        self.converting = False
        total_done = success_count + fail_count
        self.log.write(f"\n{'='*40}\n", "SYSTEM")
        self.log.write(f"📊 完成 {total_done}/{total} 个 | "
                       f"✅成功 {success_count} | ❌失败 {fail_count}\n", "SYSTEM")
        self.prog_label.config(text="完成")

        if fail_count > 0:
            messagebox.showwarning("转换完成",
                f"共处理 {total_done}/{total} 个文件\n"
                f"✅ 成功: {success_count}\n"
                f"❌ 失败: {fail_count}\n\n"
                f"输出目录: {out_dir}")
        else:
            messagebox.showinfo("转换完成",
                f"全部 {success_count} 个文件转换成功!\n\n"
                f"输出目录: {out_dir}")

    def _convert_ncm(self, filepath, out_dir, bitrate, item):
        """解密 NCM 文件"""
        basename = os.path.splitext(os.path.basename(filepath))[0]
        audio_data, fmt, song_info = parse_ncm(filepath)
        out_path = os.path.join(out_dir, f"{basename}.{fmt}")

        # 写音频
        with open(out_path, "wb") as f:
            f.write(audio_data)

        # 嵌入元数据
        if song_info.get("name") or song_info.get("cover"):
            try:
                from mutagen.mp3 import MP3
                from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB
                audio_tag = MP3(out_path)
                audio_tag.add_tags()
                if song_info.get("name"):
                    audio_tag.tags.add(TIT2(encoding=3, text=song_info["name"]))
                if song_info.get("artist"):
                    audio_tag.tags.add(TPE1(encoding=3, text=song_info["artist"]))
                if song_info.get("album"):
                    audio_tag.tags.add(TALB(encoding=3, text=song_info["album"]))
                if song_info.get("cover"):
                    mime = "image/jpeg"
                    if song_info["cover"][:4] == b"\x89PNG":
                        mime = "image/png"
                    audio_tag.tags.add(
                        APIC(encoding=3, mime=mime, type=3,
                             desc="Cover", data=song_info["cover"]))
                audio_tag.save()
            except Exception:
                pass

        # 如果是FLAC需要二次转MP3
        if fmt != "mp3":
            final = os.path.join(out_dir, f"{basename}.mp3")
            success, _, msg = flac_to_mp3(out_path, final, bitrate)
            try:
                os.remove(out_path)
            except:
                pass
            if not success:
                self._set_status(item, "❌ 转码失败")
                self.log.write(f"  → 转MP3失败: {msg}\n", "ERROR")
                return False
            out_path = final

        size = os.path.getsize(out_path) / 1024 / 1024
        tag = f" ({song_info['name']})" if song_info.get("name") else ""
        self._set_status(item, "✅ 成功")
        self.log.write(f"  → {os.path.basename(out_path)}{tag} ({size:.1f}MB)\n", "INFO")
        return True

    def _convert_encrypted(self, filepath, out_dir, bitrate, item, enc_type):
        """解密 KGM/MGG/QMC 等加密格式"""
        basename = os.path.splitext(os.path.basename(filepath))[0]
        
        if enc_type == "kgm_mgg":
            audio_data, fmt, info = decrypt_kgm_mgg(filepath)
            tag_name = info.get("original_ext", "加密").upper()
        elif enc_type == "qmc":
            audio_data, fmt, info = decrypt_qmc(filepath)
            tag_name = info.get("original_ext", "QMC").upper()
        else:
            return False
        
        out_path = os.path.join(out_dir, f"{basename}.{fmt}")
        
        # 写解密后的音频
        with open(out_path, "wb") as f:
            f.write(audio_data)
        
        self.log.write(f"  → 解密完成 ({fmt.upper()})\n", "INFO")
        
        # 如果不是MP3，需要二次转码
        if fmt != "mp3" and fmt.lower() != "mp3":
            final = os.path.join(out_dir, f"{basename}.mp3")
            success, _, msg = flac_to_mp3(out_path, final, bitrate)
            try:
                os.remove(out_path)
            except:
                pass
            if not success:
                self._set_status(item, "❌ 转码失败")
                self.log.write(f"  → 转MP3失败: {msg}\n", "ERROR")
                return False
            out_path = final
        
        size = os.path.getsize(out_path) / 1024 / 1024
        self._set_status(item, "✅ 成功")
        ext_info = f" ({tag_name}→{fmt.upper()})" if tag_name else ""
        self.log.write(f"  → {os.path.basename(out_path)}{ext_info} ({size:.1f}MB)\n", "INFO")
        return True

    def _convert_ffmpeg(self, filepath, out_dir, bitrate, item):
        """ffmpeg 转MP3"""
        basename = os.path.splitext(os.path.basename(filepath))[0]
        out_path = os.path.join(out_dir, f"{basename}.mp3")
        success, _, msg = flac_to_mp3(filepath, out_path, bitrate)

        if success:
            size = os.path.getsize(out_path) / 1024 / 1024
            self._set_status(item, "✅ 成功")
            self.log.write(f"  → {basename}.mp3 ({size:.1f}MB)\n", "INFO")
            return True
        else:
            self._set_status(item, "❌ 失败")
            self.log.write(f"  → {msg}\n", "ERROR")
            return False

    # ═══════════════ 日志队列 ═══════════════

    def _process_log_queue(self):
        try:
            while True:
                msg, tag = self.log_queue.get_nowait()
                self.log.write(msg, tag)
        except queue.Empty:
            pass
        self.root.after(100, self._process_log_queue)

    # ═══════════════ 帮助 ───

    def _show_help(self):
        messagebox.showinfo("使用说明",
            "🎵 音频格式转换器 v3.0\n\n"
            "📥 拖拽导入:\n"
            "  直接将文件或文件夹拖入窗口\n\n"
            "🔄 支持的格式:\n"
            "  ■ NCM 格式: .ncm\n"
            "  ■ KGM/MGG 格式: .kgm, .kgma, .mgg\n"
            "  ■ QMC 格式: .qmc0, .qmc3, .qmcflac, .qmcogg, .mflac\n"
            "  ■ 标准音频: FLAC, WAV, AAC, OGG,\n"
            "              WMA, APE, M4A, Opus\n\n"
            "📝 转换说明:\n"
            "  NCM/KGM/MGG/QMC → 先解密再转MP3\n"
            "  其他格式 → ffmpeg 直接转MP3\n\n"
            "⌨️ 快捷键:\n"
            "  Ctrl+O  添加文件\n"
            "  Ctrl+F  添加文件夹\n"
            "  Ctrl+R  开始转换\n"
            "  Ctrl+Q  退出\n\n"
            "📁 输出目录可自定义\n"
            "🎚️ 比特率建议 320k 最佳质量")

    def _show_about(self):
        messagebox.showinfo("关于",
            "🎵 音频格式转换器 v3.0\n\n"
            "支持格式:\n"
            "  NCM | KGM / MGG\n"
            "  QMC0 / QMC3 / QMCflac / QMCogg / MFLAC\n"
            "  FLAC/WAV/AAC/OGG/WMA/APE/M4A/Opus\n\n"
            "引擎: FFmpeg + Python 解密库\n"
            "界面: Tkinter + tkinterdnd2\n"
            "算法: ncmdump / unlock-music 逆向")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = AudioConverterApp()
    app.run()
