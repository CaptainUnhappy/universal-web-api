@echo off
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%venv\Scripts\python.exe"
set "SCHEDULED_SCRIPT=%SCRIPT_DIR%scheduled_request.py"
set "AUTO_DESCRIBE_SCRIPT=%SCRIPT_DIR%auto_describe.py"
set "START_BAT=%SCRIPT_DIR%start.bat"

:: ============================================================
:: 选择模式
:: ============================================================
echo ============================================================
echo   Universal Web-API 工具选择
echo ============================================================
echo.
echo   请选择模式:
echo.
echo   1. 定时图片请求（定时向AI发送图片）
echo   2. 自动描述图片（自动描述图片并生成新图片）
echo.
echo ============================================================

:select_mode
set /p MODE_CHOICE="请输入选项 [1/2]: "
if "%MODE_CHOICE%"=="1" goto mode_scheduled
if "%MODE_CHOICE%"=="2" goto mode_auto_describe
echo [提示] 请输入 1 或 2
goto select_mode

:mode_scheduled
title Universal Web-API 定时图片请求
set "SCRIPT=%SCHEDULED_SCRIPT%"
set "MODE_NAME=定时图片请求"
goto start_script

:mode_auto_describe
title Universal Web-API 自动描述图片
set "SCRIPT=%AUTO_DESCRIBE_SCRIPT%"
set "MODE_NAME=自动描述图片"
goto start_script

:start_script

echo.
echo ============================================================
echo   Universal Web-API %MODE_NAME%工具
echo ============================================================
echo.

:: ============================================================
:: 检查虚拟环境，没有则先启动 start.bat 安装
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
:: 安装 schedule / requests（如已安装则跳过）
:: ============================================================
"%VENV_PYTHON%" -c "import schedule" 2>nul
if errorlevel 1 (
    echo [安装] 正在安装 schedule 模块...
    "%VENV_PYTHON%" -m pip install schedule -q
    if errorlevel 1 (
        echo [错误] schedule 安装失败，请检查网络或手动运行:
        echo        %VENV_PYTHON% -m pip install schedule
        pause
        exit /b 1
    )
    echo [完成] schedule 已安装
    echo.
)

"%VENV_PYTHON%" -c "import requests" 2>nul
if errorlevel 1 (
    echo [安装] 正在安装 requests 模块...
    "%VENV_PYTHON%" -m pip install requests -q
)

:: ============================================================
:: 检查 API 服务是否已启动，未启动则自动拉起 start.bat
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
    :: 若 start.bat 窗口已经开着（安装虚拟环境时拉起的），不重复启动
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
:: 运行主脚本（异常退出自动重启）
:: ============================================================
:run
"%VENV_PYTHON%" "%SCRIPT%"
echo.
echo [警告] 程序意外退出，3 秒后自动重启...
timeout /t 3 /nobreak >nul
goto run
