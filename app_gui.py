import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import sys
import json
import time
import threading
import requests
import os
from pathlib import Path
from datetime import datetime, timedelta
from PIL import Image, ImageTk

# ================= 配置与路径 =================
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PYTHON = SCRIPT_DIR / "venv" / "Scripts" / "python.exe"

# 模式 1 配置
MODE1_API_URL = "http://127.0.0.1:8199/tab/1/v1/chat/completions"
IMAGE_DIR = SCRIPT_DIR / "image"
MODE1_PROMPT_FILE = SCRIPT_DIR / "prompt.md"

# 模式 2 配置
AUTO_DESCRIBE_DIR = SCRIPT_DIR / "自动描述"
DATA_FILE = AUTO_DESCRIBE_DIR / "data.json"
MODE2_PROMPT_FILE = AUTO_DESCRIBE_DIR / "prompt.md"
DOUBAO_API_URL = "http://127.0.0.1:8199/tab/3/v1/chat/completions"
GEMINI_API_URL = "http://127.0.0.1:8199/tab/2/v1/chat/completions"

SHUTDOWN_URL = "http://127.0.0.1:8199/api/system/shutdown"

class UniversalWebAPIApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Universal Web-API 集成控制面板")
        self.root.geometry("900x750")
        
        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 状态变量
        self.mode1_running = False
        self.mode2_running = False
        self.logs_visible = False

        # 模式 1 线程变量
        self.mode1_thread = None
        self.mode1_stop_event = threading.Event()
        self.m1_image_vars = {}
        self.m1_selection_lock = threading.Lock()
        self.m1_runtime_images = []
        self.m1_thumbnail_photos = {}
        self.m1_row_widgets = {}
        self.m1_processing_image = None
        self.m1_next_image = None
        self.m1_result_image = None
        self.m1_result_success = None
        self.btn_m1_select_all = None
        self.btn_m1_refresh = None

        # 模式 2 线程变量
        self.mode2_thread = None
        self.mode2_stop_event = threading.Event()

        self.setup_styles()
        self.setup_ui()

    def on_closing(self):
        if messagebox.askokcancel("退出", "确定要退出并关闭所有服务（包括浏览器和 API）吗？"):
            self.log("正在关闭服务...")
            # 1. 尝试优雅关闭 API 服务 (它会尝试关闭浏览器)
            try:
                requests.post(SHUTDOWN_URL, timeout=2)
            except:
                pass
            
            # 2. 等待一会，然后暴力清理残留的浏览器进程
            # 查找并关闭监听在 BROWSER_PORT 的进程 (通常是 Chrome)
            try:
                # 获取配置中的端口
                port = 9222
                # 尝试从系统命令查找占用端口的 PID 并终止
                cleanup_cmd = f'for /f "tokens=5" %a in (\'netstat -aon ^| findstr ":{port}" ^| findstr "LISTENING"\') do taskkill /f /pid %a'
                subprocess.Popen(cleanup_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                pass

            # 3. 停止 GUI 内部线程
            self.mode1_stop_event.set()
            self.mode2_stop_event.set()
            
            self.root.destroy()
            # 确保主进程也退出，触发 start.bat 的退出逻辑
            os._exit(0)

    def open_folder(self, path):
        """打开文件夹"""
        p = Path(path)
        if not p.exists():
            p.mkdir(parents=True, exist_ok=True)
        os.startfile(str(p.absolute()))

    def setup_styles(self):
        style = ttk.Style()
        # 使用 Tkinter 兼容的字符串格式，避免解析错误
        font_main = "{Microsoft YaHei} 10"
        font_bold = "{Microsoft YaHei} 12 bold"
        
        style.configure("TButton", font=font_main)
        style.configure("Header.TLabel", font=font_bold)
        style.configure("Action.TButton", foreground="white", background="#2196F3")

    def setup_ui(self):
        # 主容器
        self.main_container = ttk.Frame(self.root, padding="10")
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # 顶部标题
        header = ttk.Label(self.main_container, text="✨ Universal Web-API 集成控制中心", style="Header.TLabel")
        header.pack(pady=(0, 10))

        # 选项卡控件
        self.notebook = ttk.Notebook(self.main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # --- 选项卡 1: 定时图片请求 ---
        self.tab1 = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab1, text=" 📷 定时图片请求 (模式 1) ")
        self.setup_tab1()

        # --- 选项卡 2: 自动描述图片 ---
        self.tab2 = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(self.tab2, text=" 🤖 自动描述生成 (模式 2) ")
        self.setup_tab2()

        # --- 底部日志区域 (默认隐藏) ---
        self.log_frame = ttk.LabelFrame(self.main_container, text="运行日志", padding="5")
        self.log_area = scrolledtext.ScrolledText(self.log_frame, height=8, font=("Consolas", 9), state='disabled')
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        self.btn_toggle_logs = ttk.Button(self.main_container, text="显示运行日志 ▼", command=self.toggle_logs)
        self.btn_toggle_logs.pack(pady=5)

    def toggle_logs(self):
        if self.logs_visible:
            self.log_frame.pack_forget()
            self.btn_toggle_logs.configure(text="显示运行日志 ▼")
        else:
            self.log_frame.pack(fill=tk.X, side=tk.BOTTOM, before=self.btn_toggle_logs)
            self.btn_toggle_logs.configure(text="隐藏运行日志 ▲")
        self.logs_visible = not self.logs_visible

    def log(self, message, is_error=False):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{timestamp}] {message}\n"
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, formatted_msg)
        if is_error:
            # 如果是错误，确保日志可见
            if not self.logs_visible:
                self.toggle_logs()
            # 标记红色
            self.log_area.tag_add("error", "end-2c linestart", "end-1c")
            self.log_area.tag_config("error", foreground="red")
        self.log_area.configure(state='disabled')
        self.log_area.see(tk.END)

    # ================= 模式 1 UI =================
    def setup_tab1(self):
        selection_panel = ttk.LabelFrame(self.tab1, text="图片选择", padding="10")
        selection_panel.pack(fill=tk.BOTH, expand=True)

        top_controls = ttk.Frame(selection_panel)
        top_controls.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(top_controls, text="间隔 (分钟):").pack(side=tk.LEFT)
        self.m1_interval = ttk.Spinbox(top_controls, from_=1, to=1440, width=10)
        self.m1_interval.set(5)
        self.m1_interval.pack(side=tk.LEFT, padx=(6, 12))

        self.btn_m1_start = ttk.Button(top_controls, text="▶ 启动定时提交", command=self.toggle_mode1)
        self.btn_m1_start.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_m1_refresh = ttk.Button(top_controls, text="刷新列表", command=self.refresh_m1_images, width=10)
        self.btn_m1_refresh.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(top_controls, text="📁 打开文件夹", command=lambda: self.open_folder(IMAGE_DIR), width=12).pack(side=tk.LEFT)

        self.m1_status_var = tk.StringVar(value="就绪")
        ttk.Label(selection_panel, textvariable=self.m1_status_var, foreground="#4b5563").pack(anchor=tk.W, pady=(0, 8))

        list_panel = ttk.LabelFrame(selection_panel, text="2. 选择图片", padding="8")
        list_panel.pack(fill=tk.BOTH, expand=True)

        img_header = ttk.Frame(list_panel)
        img_header.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(img_header, text="勾选后参与轮询").pack(side=tk.LEFT, anchor=tk.W)
        self.btn_m1_select_all = ttk.Button(img_header, text="全选", width=6, command=self.select_all_m1_images)
        self.btn_m1_select_all.pack(side=tk.RIGHT)

        img_list_container = ttk.Frame(list_panel)
        img_list_container.pack(fill=tk.BOTH, expand=True)

        self.m1_img_canvas = tk.Canvas(img_list_container, width=300, height=420, highlightthickness=1, highlightbackground="#d9d9d9")
        self.m1_img_scrollbar = ttk.Scrollbar(img_list_container, orient=tk.VERTICAL, command=self.m1_img_canvas.yview)
        self.m1_img_checks_frame = ttk.Frame(self.m1_img_canvas)
        self.m1_img_checks_frame.bind(
            "<Configure>",
            lambda e: self.m1_img_canvas.configure(scrollregion=self.m1_img_canvas.bbox("all"))
        )
        self.m1_img_canvas_window = self.m1_img_canvas.create_window((0, 0), window=self.m1_img_checks_frame, anchor="nw")
        self.m1_img_canvas.bind(
            "<Configure>",
            lambda e: self.m1_img_canvas.itemconfigure(self.m1_img_canvas_window, width=e.width)
        )
        self.m1_img_canvas.configure(yscrollcommand=self.m1_img_scrollbar.set)
        self.m1_img_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.m1_img_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.refresh_m1_images()

    def refresh_m1_images(self):
        selected_names = {
            name for name, var in self.m1_image_vars.items()
            if var.get()
        }
        self.m1_image_vars = {}
        self.m1_thumbnail_photos = {}
        self.m1_row_widgets = {}

        for child in self.m1_img_checks_frame.winfo_children():
            child.destroy()

        if not IMAGE_DIR.exists(): IMAGE_DIR.mkdir(exist_ok=True)
        exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
        images = [f.name for f in IMAGE_DIR.iterdir() if f.is_file() and f.suffix.lower() in exts]
        for img in sorted(images):
            var = tk.BooleanVar(value=img in selected_names)
            self.m1_image_vars[img] = var
            row = tk.Frame(
                self.m1_img_checks_frame,
                bg="#ffffff",
                highlightthickness=1,
                highlightbackground="#d8dee6",
                highlightcolor="#d8dee6",
                bd=0,
                padx=6,
                pady=4
            )
            row.pack(fill=tk.X, padx=6, pady=3)

            check = tk.Checkbutton(
                row,
                variable=var,
                command=self.on_m1_selection_changed,
                bg="#ffffff",
                activebackground="#ffffff",
                selectcolor="#ffffff",
                bd=0,
                highlightthickness=0
            )
            check.pack(side=tk.LEFT, padx=(0, 6))

            name_label = tk.Label(
                row,
                text=img,
                anchor="w",
                bg="#ffffff",
                padx=2
            )
            name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

            thumb_label = tk.Label(row, text="无预览", anchor=tk.CENTER, width=56, height=56, bg="#ffffff")
            thumb_label.pack(side=tk.RIGHT, padx=(8, 0))
            self._set_m1_thumbnail(img, thumb_label)
            self.m1_row_widgets[img] = {
                "row": row,
                "check": check,
                "name": name_label,
                "thumb": thumb_label,
            }

        self.on_m1_selection_changed()

    def select_all_m1_images(self):
        for var in self.m1_image_vars.values():
            var.set(True)
        self.on_m1_selection_changed()

    def get_selected_m1_images(self):
        return [name for name, var in self.m1_image_vars.items() if var.get()]

    def on_m1_selection_changed(self):
        selected = self.get_selected_m1_images()
        with self.m1_selection_lock:
            self.m1_runtime_images = list(selected)
        if self.m1_next_image and self.m1_next_image not in selected:
            self.m1_next_image = selected[0] if selected else None
        self._refresh_m1_row_styles()

    def get_m1_runtime_images(self):
        with self.m1_selection_lock:
            return list(self.m1_runtime_images)

    def _set_m1_thumbnail(self, image_name, label):
        image_path = IMAGE_DIR / image_name
        try:
            with Image.open(image_path) as img:
                preview = img.copy()
            preview.thumbnail((56, 56))
            photo = ImageTk.PhotoImage(preview)
            self.m1_thumbnail_photos[image_name] = photo
            label.configure(image=photo, text="")
        except Exception as e:
            label.configure(image="", text="预览失败")

    def _refresh_m1_row_styles(self):
        for image_name, widgets in self.m1_row_widgets.items():
            bg = "#ffffff"
            border = "#d8dee6"

            if image_name == self.m1_result_image:
                bg = "#e8f7ea" if self.m1_result_success else "#fdecec"

            if image_name == self.m1_processing_image:
                bg = "#eaf4ff"

            if image_name == self.m1_next_image:
                border = "#3b82f6"

            widgets["row"].configure(bg=bg, highlightbackground=border, highlightcolor=border)
            widgets["check"].configure(bg=bg, activebackground=bg, selectcolor=bg)
            widgets["name"].configure(bg=bg)
            widgets["thumb"].configure(bg=bg)

    def _set_m1_processing_state(self, image_name):
        self.m1_processing_image = image_name
        self.m1_next_image = None
        self._refresh_m1_row_styles()

    def _set_m1_result_state(self, image_name, success, next_image=None):
        self.m1_processing_image = None
        self.m1_result_image = image_name
        self.m1_result_success = bool(success)
        self.m1_next_image = next_image
        self._refresh_m1_row_styles()

    def _clear_m1_running_marker(self):
        self.m1_processing_image = None
        self.m1_next_image = None
        self._refresh_m1_row_styles()

    def _set_m1_selection_enabled(self, enabled):
        state = tk.NORMAL if enabled else tk.DISABLED
        for widgets in self.m1_row_widgets.values():
            widgets["check"].configure(state=state)
        if self.btn_m1_select_all is not None:
            self.btn_m1_select_all.configure(state=state)
        if self.btn_m1_refresh is not None:
            self.btn_m1_refresh.configure(state=state)

    def toggle_mode1(self):
        if not self.mode1_running:
            selected_images = self.get_selected_m1_images()
            if not selected_images:
                messagebox.showwarning("提示", "请先选择至少一张图片")
                return

            interval = int(self.m1_interval.get())
            
            self.mode1_running = True
            self.btn_m1_start.configure(text="⏹ 停止提交")
            self.mode1_stop_event.clear()
            self._set_m1_selection_enabled(False)
            self.on_m1_selection_changed()
            self.update_m1_response("")
            self.append_m1_status(f"[开始] 共 {len(selected_images)} 张图片轮询: {', '.join(selected_images)}")
            self.append_m1_status(f"       间隔: {interval} 分钟，每次提交一张")
            
            self.mode1_thread = threading.Thread(
                target=self.mode1_loop, 
                args=(interval,),
                daemon=True
            )
            self.mode1_thread.start()
            self.log(f"模式 1 已启动: {len(selected_images)} 张图片, 间隔 {interval} 分钟")
        else:
            self.mode1_running = False
            self.mode1_stop_event.set()
            self.btn_m1_start.configure(text="▶ 启动定时提交")
            self._set_m1_selection_enabled(True)
            self.log("模式 1 正在停止...")

    def mode1_loop(self, interval):
        counter = 0
        img_idx = 0
        while not self.mode1_stop_event.is_set():
            images = self.get_m1_runtime_images()
            if not images:
                self.root.after(0, lambda: self.append_m1_status("[等待] 当前未勾选任何图片，请重新勾选后继续"))
                if self.mode1_stop_event.wait(timeout=1):
                    break
                continue

            counter += 1
            current_img = images[img_idx % len(images)]
            img_idx += 1
            
            self.log(f"[模式 1] 第 {counter} 次提交: {current_img}")
            self.root.after(0, lambda img=current_img: self._set_m1_processing_state(img))
            self.root.after(0, lambda c=counter, img=current_img: self.append_m1_status(
                f"[{datetime.now().strftime('%H:%M:%S')}] 第 {c} 次提交 -> {img}"
            ))
            self.root.after(0, lambda img=current_img: self.append_m1_status(f"正在处理图片: {img}"))
            
            request_ok = False
            try:
                prompt = MODE1_PROMPT_FILE.read_text(encoding="utf-8").strip()
                abs_path = str((IMAGE_DIR / current_img).absolute())
                
                payload = {
                    "model": "web-browser",
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": abs_path}}
                        ]
                    }],
                    "stream": False
                }
                
                resp = requests.post(MODE1_API_URL, json=payload, timeout=180)
                resp.raise_for_status()
                request_ok = True
                self.root.after(0, lambda: self.append_m1_status("提交成功"))
                self.log(f"[模式 1] 提交成功")
                
            except Exception as e:
                self.root.after(0, lambda err=str(e): self.append_m1_status(f"[错误] {err}"))
                self.log(f"[模式 1 错误] {str(e)}", is_error=True)
            
            next_images = self.get_m1_runtime_images()
            next_img = next_images[img_idx % len(next_images)] if next_images else "（等待勾选图片）"
            self.root.after(0, lambda img=current_img, ok=request_ok, nxt=(next_images[img_idx % len(next_images)] if next_images else None): self._set_m1_result_state(img, ok, nxt))
            next_time = datetime.now().replace(microsecond=0) + timedelta(minutes=interval)
            self.root.after(
                0,
                lambda nt=next_time.strftime('%H:%M:%S'), ni=next_img: self.append_m1_status(
                    f"[循环] 下次提交: {nt}  下一张: {ni}"
                )
            )

            # 等待
            if self.mode1_stop_event.wait(timeout=interval * 60):
                break
        self.root.after(0, self._clear_m1_running_marker)
        self.root.after(0, lambda: self._set_m1_selection_enabled(True))
        self.root.after(0, lambda: self.append_m1_status("[循环] 已停止"))
        self.log("模式 1 已完全停止")

    def update_m1_response(self, text):
        if hasattr(self, "m1_status_var"):
            self.m1_status_var.set(text)

    def append_m1_status(self, text):
        if hasattr(self, "m1_status_var"):
            self.m1_status_var.set(text)

    # ================= 模式 2 UI =================
    def setup_tab2(self):
        top_bar = ttk.Frame(self.tab2)
        top_bar.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(top_bar, text="检测间隔 (分钟):").pack(side=tk.LEFT)
        self.m2_interval = ttk.Spinbox(top_bar, from_=1, to=1440, width=5)
        self.m2_interval.set(5)
        self.m2_interval.pack(side=tk.LEFT, padx=5)

        self.btn_m2_start = ttk.Button(top_bar, text="▶ 启动自动检测", command=self.toggle_mode2)
        self.btn_m2_start.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(top_bar, text="📁 打开文件夹", command=lambda: self.open_folder(AUTO_DESCRIBE_DIR)).pack(side=tk.LEFT)

        # 状态列表
        columns = ("filename", "status", "time")
        self.m2_tree = ttk.Treeview(self.tab2, columns=columns, show='headings')
        self.m2_tree.heading("filename", text="文件名")
        self.m2_tree.heading("status", text="当前状态")
        self.m2_tree.heading("time", text="最后处理时间")
        self.m2_tree.column("filename", width=300)
        self.m2_tree.column("status", width=150)
        self.m2_tree.column("time", width=150)
        self.m2_tree.pack(fill=tk.BOTH, expand=True)

        # 定时刷新列表
        self.refresh_m2_status()

    def refresh_m2_status(self):
        # 清空
        for item in self.m2_tree.get_children():
            self.m2_tree.delete(item)
            
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for filename, info in data.items():
                        status_map = {
                            "done": "✅ 完成",
                            "describing": "⏳ 正在获取描述...",
                            "described": "📝 已获取描述",
                            "generating": "🎨 正在生成图片...",
                            "failed_describe": "❌ 描述失败",
                            "failed_generate": "❌ 生成失败"
                        }
                        status_text = status_map.get(info.get("status"), "❓ 未知")
                        last_time = info.get("generate_at") or info.get("describe_at") or "-"
                        if last_time != "-":
                            last_time = last_time.split(".")[0].replace("T", " ")
                        self.m2_tree.insert("", tk.END, values=(filename, status_text, last_time))
            except:
                pass
        
        # 每 10 秒刷新一次显示
        self.root.after(10000, self.refresh_m2_status)

    def toggle_mode2(self):
        if not self.mode2_running:
            interval = int(self.m2_interval.get())
            self.mode2_running = True
            self.btn_m2_start.configure(text="⏹ 停止检测")
            self.mode2_stop_event.clear()
            
            self.mode2_thread = threading.Thread(
                target=self.mode2_loop,
                args=(interval,),
                daemon=True
            )
            self.mode2_thread.start()
            self.log(f"模式 2 已启动: 监控目录 {AUTO_DESCRIBE_DIR}, 间隔 {interval} 分钟")
        else:
            self.mode2_running = False
            self.mode2_stop_event.set()
            self.btn_m2_start.configure(text="▶ 启动自动检测")
            self.log("模式 2 正在停止...")

    def mode2_loop(self, interval):
        while not self.mode2_stop_event.is_set():
            self.log("[模式 2] 正在扫描文件夹...")
            try:
                # 调用现有的 process_next_image 逻辑（为了不重复写，这里直接调用重构后的函数）
                self.execute_mode2_logic()
            except Exception as e:
                self.log(f"[模式 2 错误] {str(e)}", is_error=True)
            
            if self.mode2_stop_event.wait(timeout=interval * 60):
                break
        self.log("模式 2 已完全停止")

    def execute_mode2_logic(self):
        # 简化版 Mode 2 核心逻辑，不带 input 交互
        if not AUTO_DESCRIBE_DIR.exists(): AUTO_DESCRIBE_DIR.mkdir(exist_ok=True)
        
        # 加载数据和 Prompt
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f: data = json.load(f)
        except: data = {}
        
        with open(MODE2_PROMPT_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip().split("#")
            # 过滤空段落并确保至少有两段
            sections = [s.strip() for s in content if s.strip()]
            if len(sections) < 2:
                self.log("[模式 2] prompt.md 格式不正确，至少需要两个 # 段落", is_error=True)
                return
            doubao_p, gemini_p = sections[0], sections[1]

        exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
        images = [f for f in AUTO_DESCRIBE_DIR.iterdir() if f.is_file() and f.suffix.lower() in exts]
        
        processed_any = False
        for img_path in sorted(images, key=lambda x: x.stat().st_mtime, reverse=True):
            name = img_path.name
            record = data.get(name, {"status": "pending"})
            
            if record.get("status") == "done": continue
            
            processed_any = True
            self.log(f"[模式 2] 处理图片: {name}")
            
            # 1. 描述
            if record.get("status") in ["pending", "failed_describe"]:
                record["status"] = "describing"
                data[name] = record
                self.save_mode2_data(data)
                
                desc = self.get_desc(img_path, doubao_p)
                if desc:
                    record["description"] = desc
                    record["describe_at"] = datetime.now().isoformat()
                    record["status"] = "described"
                else:
                    record["status"] = "failed_describe"
                
                data[name] = record
                self.save_mode2_data(data)
                if record["status"] == "failed_describe": break

            # 2. 生成
            if record.get("status") == "described":
                record["status"] = "generating"
                data[name] = record
                self.save_mode2_data(data)
                
                result = self.gen_img(record["description"], gemini_p)
                if result:
                    record["result"] = result
                    record["generate_at"] = datetime.now().isoformat()
                    record["status"] = "done"
                else:
                    record["status"] = "failed_generate"
                
                data[name] = record
                self.save_mode2_data(data)
            
            # 每次轮询只处理一张图片以防阻塞
            break
            
        if not processed_any:
            self.log("[模式 2] 没有待处理的图片")

    def save_mode2_data(self, data):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_desc(self, path, prompt):
        try:
            payload = {
                "model": "doubao",
                "messages": [{"role": "user", "content": [{"type":"text","text":prompt}, {"type":"image_url","image_url":{"url":str(path.absolute())}}]}],
                "stream": False
            }
            resp = requests.post(DOUBAO_API_URL, json=payload, timeout=180)
            return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            self.log(f"[豆包错误] {str(e)}", is_error=True)
            return None

    def gen_img(self, desc, prompt):
        try:
            payload = {
                "model": "gemini",
                "messages": [{"role": "user", "content": [{"type":"text","text":f"{prompt}\n{desc}"}]}],
                "stream": False
            }
            resp = requests.post(GEMINI_API_URL, json=payload, timeout=300)
            return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            self.log(f"[Gemini 错误] {str(e)}", is_error=True)
            return None

if __name__ == "__main__":
    root = tk.Tk()
    app = UniversalWebAPIApp(root)
    root.mainloop()
