import os
import subprocess
from flask import Flask, render_template_string, send_from_directory, abort
from threading import Timer

app = Flask(__name__)

# --- 配置区 ---
# 请修改为您存放图片的文件夹绝对路径
TARGET_ALBUM_DIR = os.path.abspath(r"C:\Projects\universal-web-api\download_images") 
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}

# --- 增强版相册 UI 模板 (包含灯箱预览和键盘支持) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 相册管理器 - 预览模式</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .img-card:hover .overlay { opacity: 1; }
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #1a1a1a; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 4px; }
        #lightbox { display: none; }
        #lightbox.active { display: flex; }
    </style>
</head>
<body class="bg-[#0f0f0f] text-gray-100 min-h-screen">
    <div class="max-w-7xl mx-auto p-6">
        <header class="flex justify-between items-center mb-10 border-b border-white/10 pb-6">
            <div>
                <h1 class="text-3xl font-extrabold tracking-tight text-white">本地图片资产</h1>
                <p class="text-gray-400 mt-2 flex items-center text-sm">
                    <span class="inline-block w-2 h-2 bg-green-500 rounded-full mr-2"></span>
                    键盘操作：使用 <span class="mx-1 px-1 bg-gray-700 rounded text-xs">←</span> <span class="mx-1 px-1 bg-gray-700 rounded text-xs">→</span> 切换图片
                </p>
            </div>
            <div class="text-right text-xs text-gray-500 font-mono">
                {{ count }} ITEMS | LOCKED
            </div>
        </header>

        <!-- 图片网格 -->
        <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-6">
            {% for file in files %}
            <div onclick="openLightbox({{ loop.index0 }})" 
                 class="img-card group relative aspect-square bg-gray-800 rounded-xl overflow-hidden shadow-lg border border-white/5 cursor-pointer transition-all hover:scale-[1.02]">
                <img src="/image/{{ file.name }}" class="w-full h-full object-cover" loading="lazy">
                <div class="overlay opacity-0 absolute inset-0 bg-gradient-to-t from-black/80 via-transparent transition-opacity p-4 flex flex-col justify-end">
                    <p class="text-xs truncate text-white">{{ file.name }}</p>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- 全屏灯箱预览层 -->
    <div id="lightbox" class="fixed inset-0 bg-black/95 z-50 flex-col items-center justify-center p-4">
        <!-- 关闭按钮 -->
        <button onclick="closeLightbox()" class="absolute top-6 right-6 text-white text-4xl hover:text-gray-400">&times;</button>
        
        <!-- 主图 -->
        <div class="relative w-full h-full flex items-center justify-center">
            <img id="lightbox-img" src="" class="max-w-full max-h-full object-contain shadow-2xl transition-all duration-300">
            
            <!-- 左右切换指示器 (仅视觉) -->
            <div class="absolute inset-y-0 left-0 w-20 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity">
                <button onclick="prevImage()" class="bg-white/10 p-4 rounded-full text-3xl">❮</button>
            </div>
            <div class="absolute inset-y-0 right-0 w-20 flex items-center justify-center opacity-0 hover:opacity-100 transition-opacity">
                <button onclick="nextImage()" class="bg-white/10 p-4 rounded-full text-3xl">❯</button>
            </div>
        </div>

        <!-- 底部信息 -->
        <div id="lightbox-info" class="mt-4 text-center text-gray-400 text-sm font-mono"></div>
    </div>

    <script>
        // 将后端传递的文件列表转换为 JS 数组
        const images = {{ files|tojson }};
        let currentIndex = 0;

        const lightbox = document.getElementById('lightbox');
        const lightboxImg = document.getElementById('lightbox-img');
        const lightboxInfo = document.getElementById('lightbox-info');

        function openLightbox(index) {
            currentIndex = index;
            updateLightbox();
            lightbox.classList.add('active');
            document.body.style.overflow = 'hidden'; // 禁止背景滚动
        }

        function closeLightbox() {
            lightbox.classList.remove('active');
            document.body.style.overflow = 'auto';
        }

        function updateLightbox() {
            const file = images[currentIndex];
            lightboxImg.src = '/image/' + file.name;
            lightboxInfo.innerText = `${currentIndex + 1} / ${images.length} - ${file.name}`;
        }

        function nextImage() {
            currentIndex = (currentIndex + 1) % images.length;
            updateLightbox();
        }

        function prevImage() {
            currentIndex = (currentIndex - 1 + images.length) % images.length;
            updateLightbox();
        }

        // 键盘事件监听
        document.addEventListener('keydown', (e) => {
            if (!lightbox.classList.contains('active')) return;
            
            if (e.key === 'ArrowRight') {
                nextImage();
            } else if (e.key === 'ArrowLeft') {
                prevImage();
            } else if (e.key === 'Escape') {
                closeLightbox();
            }
        });

        // 点击背景关闭
        lightbox.addEventListener('click', (e) => {
            if (e.target === lightbox || e.target.parentElement === lightbox) {
                closeLightbox();
            }
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    files = []
    if not os.path.exists(TARGET_ALBUM_DIR):
        return f"Error: Directory {TARGET_ALBUM_DIR} not found"

    for entry in os.scandir(TARGET_ALBUM_DIR):
        if entry.is_file():
            ext = os.path.splitext(entry.name)[1].lower()
            if ext in ALLOWED_EXTENSIONS:
                files.append({"name": entry.name})
    
    files.sort(key=lambda x: x['name'])
    return render_template_string(HTML_TEMPLATE, files=files, path=TARGET_ALBUM_DIR, count=len(files))

@app.route('/image/<filename>')
def serve_image(filename):
    if ".." in filename or "/" in filename or "\\" in filename:
        abort(403)
    return send_from_directory(TARGET_ALBUM_DIR, filename)

def open_browser():
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    ]
    chrome_exe = next((p for p in chrome_paths if os.path.exists(p)), "chrome")
    url = "http://127.0.0.1:5003"
    subprocess.Popen([chrome_exe, f"--app={url}", "--window-size=1200,900"])

if __name__ == "__main__":
    Timer(1.5, open_browser).start()
    app.run(host='127.0.0.1', port=5003, debug=False)