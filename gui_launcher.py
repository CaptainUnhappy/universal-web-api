import tkinter as tk
from tkinter import messagebox
import subprocess
import sys
from pathlib import Path

# 获取当前脚本所在目录
SCRIPT_DIR = Path(__file__).parent.absolute()
VENV_PYTHON = SCRIPT_DIR / "venv" / "Scripts" / "python.exe"
SCHEDULED_SCRIPT = SCRIPT_DIR / "scheduled_request.py"
AUTO_DESCRIBE_SCRIPT = SCRIPT_DIR / "auto_describe.py"

def get_wrapper_bat():
    """生成用于在控制台中循环运行脚本的批处理文件"""
    bat_path = SCRIPT_DIR / "run_wrapper.bat"
    if not bat_path.exists():
        bat_content = """@echo off
chcp 65001 >nul
title %~1
:loop
"%~2" "%~3"
echo.
echo [警告] 程序意外退出，3 秒后自动重启...
timeout /t 3 /nobreak >nul
goto loop
"""
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
    return bat_path

def run_in_console(title, script_path):
    """在一个新的CMD窗口中运行指定脚本"""
    bat_path = get_wrapper_bat()
    # 使用 start "" 避免标题解析错误，参数依次传递给 run_wrapper.bat
    cmd = f'start "" cmd /c "{bat_path}" "{title}" "{VENV_PYTHON}" "{script_path}"'
    subprocess.Popen(cmd, shell=True)

def run_mode_1():
    run_in_console("Universal Web-API 定时图片请求", SCHEDULED_SCRIPT)

def run_mode_2():
    run_in_console("Universal Web-API 自动描述图片", AUTO_DESCRIBE_SCRIPT)

def run_mode_3():
    # 1. 后台静默运行模式2
    log_file = SCRIPT_DIR / "auto_describe.log"
    CREATE_NO_WINDOW = 0x08000000
    
    with open(log_file, "a", encoding="utf-8") as f:
        # 传入 --auto 参数启动，并在后台无窗口执行
        subprocess.Popen(
            [str(VENV_PYTHON), str(AUTO_DESCRIBE_SCRIPT), "--auto"],
            stdout=f, stderr=f,
            creationflags=CREATE_NO_WINDOW
        )
    
    # 2. 前台开启模式1的控制台
    run_in_console("Universal Web-API 定时图片请求 (+后台自动描述)", SCHEDULED_SCRIPT)
    
    messagebox.showinfo(
        "混合模式已启动", 
        "✅ [前台] 定时图片请求 (模式 1) 控制台已打开。\n\n"
        "✅ [后台] 自动描述图片 (模式 2) 已在后台静默运行。\n\n"
        "如需查看模式 2 的运行日志，请打开目录下的 auto_describe.log 文件。"
    )

def create_gui():
    root = tk.Tk()
    root.title("Universal Web-API 工具箱")
    
    # 设置窗口大小并居中显示
    window_width = 420
    window_height = 340
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = int((screen_width/2) - (window_width/2))
    y = int((screen_height/2) - (window_height/2))
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    # 界面边距
    root.configure(padx=25, pady=20)
    
    # 标题部分
    tk.Label(root, text="✨ Universal Web-API", font=("Microsoft YaHei", 16, "bold")).pack(pady=(0, 5))
    tk.Label(root, text="请选择要启动的功能模式", font=("Microsoft YaHei", 10), fg="gray").pack(pady=(0, 20))
    
    btn_font = ("Microsoft YaHei", 10)
    
    # 按钮 1
    btn1 = tk.Button(root, text="📷 模式 1: 定时图片请求\n(需人工选择图片，定时轮询提交)", 
                     font=btn_font, command=run_mode_1, height=2, bg="#f5f5f5")
    btn1.pack(fill=tk.X, pady=6)
    
    # 按钮 2
    btn2 = tk.Button(root, text="🤖 模式 2: 自动描述图片\n(全自动处理，监控文件夹并生成)", 
                     font=btn_font, command=run_mode_2, height=2, bg="#f5f5f5")
    btn2.pack(fill=tk.X, pady=6)
    
    # 按钮 3
    btn3 = tk.Button(root, text="🚀 模式 3: 混合测试\n(模式1弹窗控制 + 模式2后台静默)", 
                     font=btn_font, command=run_mode_3, height=2, bg="#e1f5fe")
    btn3.pack(fill=tk.X, pady=6)
    
    # 底部提示
    tk.Label(root, text="关闭此控制面板不会影响已启动的任务", font=("Microsoft YaHei", 8), fg="#999").pack(side=tk.BOTTOM, pady=(15, 0))
    
    root.mainloop()

if __name__ == "__main__":
    create_gui()
