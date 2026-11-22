@echo off
rem Debug runner for PandaDesktopPet with console output; pauses interactively on exit
cd /d "%~dp0"
echo ===================================================
echo  PandaDesktopPet (Console Debug Mode)
echo ===================================================
echo.
tasklist /FI "IMAGENAME eq PandaDesktopPet.exe" 2>nul | find /I "PandaDesktopPet.exe" >nul
if not errorlevel 1 goto already_running
if not exist "work\asset_registry.json" if not exist "build\assets.pak" goto missing_assets
where python >nul 2>nul
if errorlevel 1 goto missing_python
set "PANDA_DUPLICATE_EXIT_CODE=3"
python -B -X utf8 app\main.py
set "PANDA_EXIT=%ERRORLEVEL%"
if "%PANDA_EXIT%"=="3" goto already_running
if not "%PANDA_EXIT%"=="0" (
    echo.
    echo [ERROR] PandaDesktopPet exited abnormally ^(Exit code: %PANDA_EXIT%^).
)
echo.
echo [INFO] PandaDesktopPet exited ^(Exit code: %PANDA_EXIT%^).
if not defined CI pause
exit /b %PANDA_EXIT%

:missing_assets
echo [ERROR] Runtime artwork assets are missing ^(work\asset_registry.json or build\assets.pak not found^).
echo [INFO] This code-only checkout omits runtime artwork. See ASSETS_REQUIRED.md, or download the portable ZIP / Setup.exe from Releases.
if not defined CI pause
exit /b 2

:missing_python
echo [ERROR] Python executable was not found in PATH. Install Python 3.11+ and run: pip install -r requirements.txt
if not defined CI pause
exit /b 1

:already_running
echo.
echo [WARN] An existing PandaDesktopPet instance may already be running. Exit it from the system tray and retry.
echo.
if not defined CI pause
exit /b 3
