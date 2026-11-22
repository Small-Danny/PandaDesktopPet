@echo off
rem Launch PandaDesktopPet silently without keeping a console window open
cd /d "%~dp0"
if exist "dist\PandaDesktopPet\PandaDesktopPet.exe" (
    start "" "dist\PandaDesktopPet\PandaDesktopPet.exe"
    exit /b %ERRORLEVEL%
)
if not exist "work\asset_registry.json" if not exist "build\assets.pak" (
    echo [ERROR] Runtime artwork assets are missing ^(work\asset_registry.json or build\assets.pak not found^).
    echo [INFO] This code-only checkout omits runtime artwork. See ASSETS_REQUIRED.md, or download the portable ZIP / Setup.exe from Releases.
    if not defined CI pause
    exit /b 2
)
where pythonw >nul 2>nul
if errorlevel 1 (
    echo [ERROR] pythonw was not found in PATH. Install Python 3.11+ or use the portable EXE.
    if not defined CI pause
    exit /b 1
)
start "" pythonw -B -X utf8 app\main.py
set "RC=%ERRORLEVEL%"
exit /b %RC%
