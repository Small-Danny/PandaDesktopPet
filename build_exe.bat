@echo off
rem Build the portable PandaDesktopPet folder (dist\PandaDesktopPet\PandaDesktopPet.exe) with PyInstaller
cd /d "%~dp0"
if not exist "work\asset_registry.json" (
    echo [ERROR] Runtime artwork assets are missing ^(work\asset_registry.json not found^).
    echo [INFO] Cannot package EXE from a code-only checkout without approved work\ assets. See ASSETS_REQUIRED.md.
    if not defined CI pause
    exit /b 2
)
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python executable was not found in PATH.
    if not defined CI pause
    exit /b 1
)
echo [1/4] Checking build requirements...
python -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
    python -m pip install -r requirements-build.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install build requirements.
        if not defined CI pause
        exit /b 1
    )
)
echo [2/4] Building PandaDesktopPet...
python -B -X utf8 -m PyInstaller --noconfirm --clean PandaDesktopPet.spec
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo [ERROR] Build failed with error code %RC%.
    if not defined CI pause
    exit /b %RC%
)
echo [3/4] Verifying exact source bytes and packed assets.pak integrity...
python -B -X utf8 tools\build_provenance.py dist\PandaDesktopPet
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo [ERROR] Build verification failed. Do not distribute this folder.
    if not defined CI pause
    exit /b %RC%
)
echo [4/4] Build bytes verified. Portable folder: %CD%\dist\PandaDesktopPet
echo [INFO] Runtime acceptance is separate from this build verification.
if not defined CI pause
exit /b 0
