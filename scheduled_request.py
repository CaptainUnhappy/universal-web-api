"""
scheduled_request.py - 定时发起带图片的 API 请求

流程：
  1. 设置定时间隔（默认 10 分钟）
  2. 选择图片（文件夹列表 或 剪切板）
  3. 立即提交一次，之后按间隔循环提交同一张图片
  4. 运行中输入 stop → 停止当前产品，回到步骤 2 选新图片
  5. 关闭窗口 / Ctrl+C → 完全退出
"""

import sys
import time
import tempfile
import threading
import requests
import schedule
from pathlib import Path
from datetime import datetime, timedelta

# ================= 配置 =================

API_URL    = "http://127.0.0.1:8199/tab/1/v1/chat/completions"
PROMPT_FILE = Path(__file__).parent / "prompt.md"
IMAGE_DIR   = Path(__file__).parent / "image"

# ================= 工具函数 =================

def load_prompt() -> str:
    if not PROMPT_FILE.exists():
        print(f"[错误] prompt.md 不存在: {PROMPT_FILE}")
        sys.exit(1)
    content = PROMPT_FILE.read_text(encoding="utf-8").strip()
    if not content:
        print("[错误] prompt.md 内容为空")
        sys.exit(1)
    return content


def list_images() -> list[Path]:
    IMAGE_DIR.mkdir(exist_ok=True)
    exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    files = [f for f in IMAGE_DIR.iterdir()
             if f.is_file() and f.suffix.lower() in exts
             and not f.name.startswith("clipboard_")]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files


def grab_clipboard_image() -> Path | None:
    try:
        from PIL import ImageGrab
        img = ImageGrab.grabclipboard()
        if img is None:
            print("  [提示] 剪切板中没有图片")
            return None
        if isinstance(img, list):
            import shutil
            exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
            for p in img:
                src = Path(p)
                if src.suffix.lower() in exts:
                    dest = IMAGE_DIR / src.name
                    # 文件名冲突时加时间戳后缀
                    if dest.exists():
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                        dest = IMAGE_DIR / f"{src.stem}_{ts}{src.suffix}"
                    shutil.copy2(str(src), str(dest))
                    size_kb = dest.stat().st_size / 1024
                    print(f"  [剪切板] 已复制到 image/: {dest.name} ({size_kb:.1f} KB)")
                    return dest
            print("  [提示] 剪切板中没有图片文件")
            return None
        # 截图 → 保存为临时 PNG
        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", prefix="clipboard_",
            dir=str(IMAGE_DIR), delete=False
        )
        tmp.close()
        img.save(tmp.name, "PNG")
        size_kb = Path(tmp.name).stat().st_size / 1024
        print(f"  [剪切板] 截图已保存: {Path(tmp.name).name} ({size_kb:.1f} KB)")
        return Path(tmp.name)
    except Exception as e:
        print(f"  [剪切板] 读取失败: {e}")
        return None


def has_clipboard_image() -> bool:
    try:
        from PIL import ImageGrab
        clip = ImageGrab.grabclipboard()
        if clip is None:
            return False
        if isinstance(clip, list):
            exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
            return any(Path(p).suffix.lower() in exts for p in clip)
        return True
    except Exception:
        return False


# ================= 步骤 1：设置间隔 =================

def ask_interval() -> int:
    """询问定时间隔，默认 10 分钟"""
    print("\n" + "=" * 54)
    print("  [步骤 1/2]  设置定时间隔")
    print("=" * 54)
    print("  直接回车 = 默认 10 分钟")
    while True:
        raw = input("  请输入间隔分钟数 [10]: ").strip()
        if raw == "":
            print("  → 使用默认值：10 分钟")
            return 10
        if raw.isdigit() and int(raw) > 0:
            minutes = int(raw)
            print(f"  → 每 {minutes} 分钟提交一次")
            return minutes
        print("  [提示] 请输入正整数")


# ================= 步骤 2：选择图片 =================

def ask_images() -> list[Path] | None:
    """
    让用户选择一张或多张图片（逗号/空格分隔多个编号）。
    返回 Path 列表 → 继续执行；返回 None → 用户输入 q 退出程序
    """
    files = list_images()
    has_clip = has_clipboard_image()

    print("\n" + "=" * 54)
    print("  [步骤 2/2]  选择产品图片")
    print("=" * 54)

    if files:
        for i, f in enumerate(files, 1):
            mtime = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size_kb = f.stat().st_size / 1024
            print(f"  {i:2d}. [{mtime}] {f.name:<38s} ({size_kb:.1f} KB)")
    else:
        print("  （image/ 文件夹中暂无图片）")

    print("-" * 54)
    if has_clip:
        print("   c       使用剪切板图片")
    print("   1 2 3   多选（空格或逗号分隔），轮询提交")
    print("   q       退出程序")
    print("=" * 54)

    while True:
        choice = input("  请输入编号: ").strip().lower()

        if choice == "q":
            return None

        if choice == "c":
            img = grab_clipboard_image()
            if img:
                return [img]
            continue

        # 解析多个编号（支持空格、逗号、中文逗号）
        tokens = [t for t in choice.replace("，", ",").replace(",", " ").split()]
        if tokens and all(t.isdigit() for t in tokens):
            selected = []
            invalid = []
            for t in tokens:
                idx = int(t)
                if 1 <= idx <= len(files):
                    p = files[idx - 1]
                    if p not in selected:
                        selected.append(p)
                else:
                    invalid.append(t)
            if invalid:
                print(f"  [提示] 编号 {' '.join(invalid)} 不存在，请重新输入")
                continue
            if selected:
                print(f"  → 已选择 {len(selected)} 张: {', '.join(p.name for p in selected)}")
                return selected

        hint = f"1-{len(files)}、" if files else ""
        clip_hint = "c、" if has_clip else ""
        print(f"  [提示] 请输入 {hint}{clip_hint}q")


# ================= 发送请求 =================

def send_request(image_path: Path, prompt: str, counter: int) -> None:
    abs_path = str(image_path.absolute())
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

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 第 {counter} 次提交 → {image_path.name}")

    try:
        resp = requests.post(API_URL, json=payload, timeout=180)
        resp.raise_for_status()
        content = (
            resp.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "（无回复内容）")
        )
        print("-" * 54)
        print(content)
        print("-" * 54)

    except requests.exceptions.Timeout:
        print("[超时] API 超过 3 分钟未响应，等待下次重试")
    except requests.exceptions.ConnectionError:
        print(f"[错误] 无法连接 API 服务: {API_URL}，等待下次重试")
    except requests.exceptions.HTTPError as e:
        print(f"[错误] HTTP {e.response.status_code}: {e.response.text[:200]}，等待下次重试")
    except Exception as e:
        print(f"[错误] {e}，等待下次重试")


# ================= 定时循环（后台线程） =================

class SubmitLoop:
    """
    在后台线程中按固定间隔轮询提交多张图片，每张独立提交。
    主线程通过 stop_event 通知停止。
    """

    def __init__(self, images: list[Path], interval_minutes: int):
        self.images   = images
        self.interval = interval_minutes
        self.stop_event = threading.Event()
        self._thread  = None
        self._counter = 0        # 总提交次数
        self._img_idx = 0        # 当前轮到第几张

    def _next_image(self) -> Path:
        img = self.images[self._img_idx % len(self.images)]
        self._img_idx += 1
        return img

    def _run(self):
        # 立即执行第一次
        self._counter += 1
        try:
            send_request(self._next_image(), load_prompt(), self._counter)
        except Exception as e:
            print(f"[错误] 意外异常: {e}，等待下次重试")
        self._print_next_time()

        while not self.stop_event.wait(timeout=self.interval * 60):
            self._counter += 1
            try:
                send_request(self._next_image(), load_prompt(), self._counter)
            except Exception as e:
                print(f"[错误] 意外异常: {e}，等待下次重试")
            if not self.stop_event.is_set():
                self._print_next_time()

        print("\n[循环] 已停止")

    def _print_next_time(self):
        next_t = datetime.now() + timedelta(minutes=self.interval)
        next_img = self.images[self._img_idx % len(self.images)].name
        print(f"[循环] 下次提交: {next_t.strftime('%H:%M:%S')}  "
              f"下一张: {next_img}  输入 stop 切换产品图片")

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)


# ================= 主流程 =================

def main():
    print("=" * 54)
    print("   Universal Web-API  定时批量图片请求工具")
    print("=" * 54)

    # 步骤 1：设置间隔（全局，只问一次）
    interval = ask_interval()

    while True:
            # 步骤 2：选择图片
        images = ask_images()
        if images is None:
            print("\n[退出] 程序结束")
            break

        # 启动定时循环
        names = ", ".join(p.name for p in images)
        print(f"\n[开始] 共 {len(images)} 张图片轮询: {names}")
        print(f"       间隔: {interval} 分钟，每次提交一张")
        print("       运行中输入 stop 停止当前产品，选择新图片")
        print("       关闭窗口 / Ctrl+C 完全退出\n")

        loop = SubmitLoop(images, interval)
        loop.start()

        # 主线程等待用户输入 stop
        try:
            while True:
                cmd = input().strip().lower()
                if cmd == "stop":
                    print("[停止] 正在停止当前循环...")
                    loop.stop()
                    break
        except KeyboardInterrupt:
            print("\n[退出] 用户中断，程序结束")
            loop.stop()
            break


if __name__ == "__main__":
    main()
