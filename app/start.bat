@echo off
chcp 65001 >nul
cd /d "%~dp0.."
echo.
echo   AI 财务经营分析助手
echo   启动后浏览器打开： http://127.0.0.1:8000
echo   按 Ctrl+C 停止服务
echo.
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
pause
