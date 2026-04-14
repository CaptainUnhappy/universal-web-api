@echo off
chcp 65001 >nul
title %~1
:loop
"%~2" "%~3"
echo.
echo [警告] 程序意外退出，3 秒后自动重启...
timeout /t 3 /nobreak >nul
goto loop
