"""
auto_describe.py - 自动描述图片并生成新图片

流程：
  1. 设置定时间隔（默认 5 分钟）
  2. 检测"自动描述"文件夹中的图片（不检测子文件夹）
  3. 第一步：对未描述的图片调用豆包API获取描述，写入data.json
  4. 第二步：将描述 + prompt.md 发送到gemini生成新图片
  5. 循环检测
"""

import sys
import time
import json
import base64
import requests
import schedule
from pathlib import Path
from datetime import datetime, timedelta
from threading import Event

# ================= 配置 =================

AUTO_DESCRIBE_DIR = Path(__file__).parent / "自动描述"
DATA_FILE = AUTO_DESCRIBE_DIR / "data.json"
PROMPT_FILE = AUTO_DESCRIBE_DIR / "prompt.md"

# 不同模型使用不同的tab URL
DOUBAO_API_URL = "http://127.0.0.1:8199/tab/1/v1/chat/completions"  # 豆包
GEMINI_API_URL = "http://127.0.0.1:8199/tab/2/v1/chat/completions"  # Gemini

# 豆包模型（用于图片描述）
DOUBAO_MODEL = "doubao"
# Gemini模型（用于生成图片）
GEMINI_MODEL = "gemini"

# 默认间隔（分钟）
DEFAULT_INTERVAL = 5


# ================= 工具函数 =================

def load_prompts() -> tuple[str, str]:
    """从 prompt.md 中加载豆包和 Gemini 的提示词。"""
    if not PROMPT_FILE.exists():
        print(f"[错误] prompt.md 不存在: {PROMPT_FILE}")
        return "", ""

    content = PROMPT_FILE.read_text(encoding="utf-8").strip()
    if not content:
        return "", ""

    sections: list[str] = []
    current: list[str] = []

    for line in content.splitlines():
        if line.startswith("#"):
            if current:
                section = "\n".join(current).strip()
                if section:
                    sections.append(section)
                current = []
            continue
        current.append(line)

    if current:
        section = "\n".join(current).strip()
        if section:
            sections.append(section)

    if len(sections) < 2:
        print(f"[错误] prompt.md 至少需要 2 个以 # 分隔的段落: {PROMPT_FILE}")
        return "", ""

    return sections[0], sections[1]


def list_images() -> list[Path]:
    """列出"自动描述"文件夹中的图片（不检测子文件夹）"""
    AUTO_DESCRIBE_DIR.mkdir(exist_ok=True)
    exts = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
    files = [f for f in AUTO_DESCRIBE_DIR.iterdir()
             if f.is_file() and f.suffix.lower() in exts]
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    return files


def load_data() -> dict:
    """加载data.json"""
    if not DATA_FILE.exists():
        return {}
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_data(data: dict) -> None:
    """保存data.json"""
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_image_description(image_path: Path, prompt: str) -> str | None:
    """
    调用豆包API获取图片描述
    """
    print(f"[豆包] 正在获取图片描述: {image_path.name}")

    # 使用文件路径方式（不要用base64，会导致tab失效）
    abs_path = str(image_path.absolute())

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {
                    "url": abs_path
                }
            }
        ]
    }]

    payload = {
        "model": DOUBAO_MODEL,
        "messages": messages,
        "stream": False
    }

    try:
        resp = requests.post(DOUBAO_API_URL, json=payload, timeout=180)
        resp.raise_for_status()
        result_json = resp.json()
        content = (
            result_json
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
        )
        print(f"[豆包] 描述获取成功: {content[:100]}...")
        return content
    except requests.exceptions.Timeout:
        print("[错误] 豆包API超时")
        return None
    except requests.exceptions.ConnectionError:
        print(f"[错误] 无法连接API服务: {DOUBAO_API_URL}")
        return None
    except Exception as e:
        print(f"[错误] {e}")
        return None


def generate_image(description: str, prompt: str) -> str | None:
    """
    调用gemini API生成图片描述的图片
    """
    print(f"[Gemini] 正在生成图片...")

    # 构建消息：将描述和prompt结合
    combined_prompt = f"{prompt}\n{description}"

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": combined_prompt}
        ]
    }]

    payload = {
        "model": GEMINI_MODEL,
        "messages": messages,
        "stream": False
    }

    try:
        resp = requests.post(GEMINI_API_URL, json=payload, timeout=300)
        resp.raise_for_status()
        content = (
            resp.json()
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
        )
        print(f"[Gemini] 生成成功: {content[:100]}...")
        return content
    except requests.exceptions.Timeout:
        print("[错误] Gemini API超时")
        return None
    except requests.exceptions.ConnectionError:
        print(f"[错误] 无法连接API服务: {GEMINI_API_URL}")
        return None
    except Exception as e:
        print(f"[错误] {e}")
        return None


# ================= 步骤 1：设置并启动 =================

def get_existing_description(data: dict, image_name: str) -> str:
    """返回已保存的有效描述；空值或异常结构视为不存在"""
    item = data.get(image_name)
    if not isinstance(item, dict):
        return ""
    description = item.get("description", "")
    if not isinstance(description, str):
        return ""
    return description.strip()

def ask_interval() -> int:
    """询问定时间隔，默认 5 分钟"""
    print("\n" + "=" * 54)
    print("  [步骤 1/1]  设置定时间隔并启动")
    print("=" * 54)
    print(f"  图片目录: {AUTO_DESCRIBE_DIR}")
    print(f"  数据文件: {DATA_FILE}")
    print(f"  Prompt文件: {PROMPT_FILE}")
    print("-" * 54)
    print("  直接回车 = 默认 5 分钟")
    while True:
        raw = input("  请输入间隔分钟数 [5]: ").strip()
        if raw == "":
            print("  → 使用默认值：5 分钟")
            return 5
        if raw.isdigit() and int(raw) > 0:
            minutes = int(raw)
            print(f"  → 每 {minutes} 分钟检测一次")
            return minutes
        print("  [提示] 请输入正整数")

# ================= 主处理流程 =================

def process_images():
    """处理图片：获取描述 + 生成图片"""
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ===== 开始检测 =====")

    # 确保目录存在
    AUTO_DESCRIBE_DIR.mkdir(exist_ok=True)

    # 加载数据
    data = load_data()

    # 列出所有图片
    images = list_images()

    if not images:
        print("[提示] 没有找到图片")
        return

    # 加载 prompt
    doubao_prompt, gemini_prompt = load_prompts()

    # 处理每张图片
    for image_path in images:
        image_name = image_path.name
        print(f"\n--- 处理: {image_name} ---")

        # 第一步：获取图片描述
        description = get_existing_description(data, image_name)
        if not description:
            print(f"[步骤1] 需要获取描述")
            description = get_image_description(image_path, doubao_prompt)
            if description:
                data[image_name] = {
                    "description": description,
                    "timestamp": datetime.now().isoformat()
                }
                save_data(data)
                print(f"[步骤1] 描述已保存")
            else:
                print(f"[步骤1] 获取描述失败，跳过")
                continue
        else:
            print(f"[步骤1] 已有描述: {description[:50]}...")

        # 第二步：生成图片
        if description and gemini_prompt:
            print(f"[步骤2] 正在生成图片...")
            result = generate_image(description, gemini_prompt)
            if result:
                # 可以选择保存结果或直接输出
                print(f"[步骤2] 生成结果: {result[:100]}...")
            else:
                print(f"[步骤2] 生成失败")
        else:
            if not description:
                print(f"[步骤2] 跳过：无描述")
            if not gemini_prompt:
                print(f"[步骤2] 跳过：无prompt")

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ===== 检测完成 =====")


# ================= 定时循环 =================

class AutoDescribeLoop:
    """自动描述循环"""

    def __init__(self, interval_minutes: int):
        self.interval = interval_minutes
        self.stop_event = Event()
        self._counter = 0

    def _run(self):
        while not self.stop_event.is_set():
            self._counter += 1
            process_images()

            # 等待下一次执行
            if self.stop_event.wait(timeout=self.interval * 60):
                break

            # 打印下次执行时间
            next_t = datetime.now() + timedelta(minutes=self.interval)
            print(f"[循环] 下次检测: {next_t.strftime('%H:%M:%S')}")

        print("\n[循环] 已停止")

    def start(self):
        import threading
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()

    def stop(self):
        self.stop_event.set()


# ================= 主流程 =================

def main():
    print("=" * 54)
    print("   Universal Web-API  自动描述图片工具")
    print("=" * 54)

    # 检查目录
    if not AUTO_DESCRIBE_DIR.exists():
        AUTO_DESCRIBE_DIR.mkdir(exist_ok=True)
        print(f"[提示] 已创建目录: {AUTO_DESCRIBE_DIR}")
        print(f"[提示] 请在目录中放入图片和prompt.md文件")

    # 检查prompt文件
    if not PROMPT_FILE.exists():
        print(f"[提示] 未找到prompt.md，将使用默认提示词")

    # 步骤 1：设置间隔
    interval = ask_interval()

    # 启动循环
    print(f"\n[开始] 每 {interval} 分钟检测一次")
    print("       运行中输入 stop 停止")
    print("       关闭窗口 / Ctrl+C 完全退出\n")

    loop = AutoDescribeLoop(interval)
    loop.start()

    # 主线程等待用户输入
    try:
        while True:
            cmd = input().strip().lower()
            if cmd == "stop":
                print("[停止] 正在停止...")
                loop.stop()
                break
    except KeyboardInterrupt:
        print("\n[退出] 用户中断，程序结束")
        loop.stop()


if __name__ == "__main__":
    main()
