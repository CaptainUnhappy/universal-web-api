@echo off
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%venv\Scripts\python.exe"
set "VENV_PYTHONW=%SCRIPT_DIR%venv\Scripts\pythonw.exe"
set "START_BAT=%SCRIPT_DIR%start.bat"
set "GUI_SCRIPT=%SCRIPT_DIR%app_gui.py"

echo ============================================================
echo   正在初始化 Universal Web-API 运行环境...
echo ============================================================
echo.

:: ============================================================
:: 1. 检查虚拟环境，没有则先启动 start.bat 安装
:: ============================================================
if not exist "%VENV_PYTHON%" (
    echo [提示] 未检测到虚拟环境，正在启动 start.bat 安装...
    if not exist "%START_BAT%" (
        echo [错误] 未找到 start.bat: %START_BAT%
        pause
        exit /b 1
    )
    start "Universal Web-API 服务" "%START_BAT%"
    echo [等待] 等待虚拟环境安装完成...
    :wait_venv
    timeout /t 3 /nobreak >nul
    if not exist "%VENV_PYTHON%" goto wait_venv
    echo [就绪] 虚拟环境已就绪
    echo.
)

:: ============================================================
:: 2. 安装/检查所需依赖模块
:: ============================================================
"%VENV_PYTHON%" -c "import requests" 2>nul
if errorlevel 1 (
    echo [安装] 正在安装 requests 模块...
    "%VENV_PYTHON%" -m pip install requests -q
)

:: ============================================================
:: 3. 检查 API 服务是否已启动，未启动则自动拉起 start.bat
:: ============================================================
echo [检查] API 服务是否运行中...
"%VENV_PYTHON%" -c "import requests; requests.get('http://localhost:8199/health', timeout=2)" 2>nul
if errorlevel 1 (
    echo [提示] API 服务未运行，正在启动 start.bat...
    if not exist "%START_BAT%" (
        echo [错误] 未找到 start.bat: %START_BAT%
        pause
        exit /b 1
    )
    tasklist /fi "windowtitle eq Universal Web-API 服务" 2>nul | find "cmd.exe" >nul
    if errorlevel 1 start "Universal Web-API 服务" "%START_BAT%"
    echo [等待] 等待 API 服务就绪...
    :wait_api
    timeout /t 3 /nobreak >nul
    "%VENV_PYTHON%" -c "import requests; requests.get('http://localhost:8199/health', timeout=2)" 2>nul
    if errorlevel 1 goto wait_api
    echo [就绪] API 服务已启动
) else (
    echo [就绪] API 服务已在运行
)
echo.

:: ============================================================
:: 4. 启动集成 GUI 界面
:: ============================================================
echo [启动] 正在打开集成控制中心...
if exist "%VENV_PYTHONW%" (
    start "" "%VENV_PYTHONW%" "%GUI_SCRIPT%"
) else (
    start "" "%VENV_PYTHON%" "%GUI_SCRIPT%"
)

exit
