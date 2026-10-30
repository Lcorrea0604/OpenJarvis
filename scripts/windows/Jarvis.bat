@echo off
rem Inicia JARVIS en modo manos libres (escucha siempre; se activa con "Jarvis")
rem y abre el HUD animado en una ventana aparte.
rem Lo usan el acceso directo del escritorio y el inicio automatico de Windows.
title JARVIS
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
cd /d "%~dp0..\.."
uv run jarvis chat --hands-free --hud
if errorlevel 1 (
    echo.
    echo JARVIS se cerro con un error. Revisa el mensaje de arriba.
    pause
)
