@echo off
REM ═══════════════════════════════════════════════════════════════
REM  PACIFIC CLI — Local Windows MSIX Build Script
REM
REM  Prerequisites:
REM    - Python 3.10+
REM    - pip install -e ".[winstore]"
REM    - pip install pyinstaller
REM    - Windows 10 SDK (for makeappx.exe)
REM
REM  Usage:
REM    build\build_msix.bat [version]
REM    build\build_msix.bat 1.0.2.0
REM
REM  Output:
REM    dist\pacific.exe
REM    dist\Pacific-<version>-x64.msix
REM ═══════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion

set VERSION=%1
if "%VERSION%"=="" set VERSION=1.0.1.0

echo.
echo ═══════════════════════════════════════════════════
echo   PACIFIC CLI — MSIX Build
echo   Version:  %VERSION%
echo   Store ID: 9NMR6VG01Q0B
echo ═══════════════════════════════════════════════════
echo.

cd /d "%~dp0\.."

REM ── Step 1: Verify source ──────────────────────────────────────
echo [1/6] Verifying source...
python -c "from pacific.cli import cli; print(f'  OK: {len(list(cli.commands.keys()))} commands')"
if errorlevel 1 (
    echo ❌ Source verification failed
    exit /b 1
)
python -c "from pacific.store_license import STORE_APP_ID; print(f'  OK: Store ID {STORE_APP_ID}')"
echo.

REM ── Step 2: Obfuscate source ──────────────────────────────────
echo [2/7] Obfuscating source code...
set STAGING=build\obfuscated_staging
if exist "%STAGING%" rmdir /s /q "%STAGING%"
xcopy pacific "%STAGING%\pacific\" /s /e /q >nul
copy pacific_app.py "%STAGING%\pacific_app.py" >nul
python build\obfuscate.py "%STAGING%\pacific"
if errorlevel 1 (
    echo ❌ Obfuscation failed
    exit /b 1
)
echo   ✅ Source obfuscated
echo.

REM ── Step 3: Build EXE ─────────────────────────────────────────
echo [3/7] Building pacific.exe...
pyinstaller build\pacific_windows.spec ^
    --distpath dist\ ^
    --workpath build\temp\ ^
    --clean ^
    --noconfirm ^
    --paths "%STAGING%"
if errorlevel 1 (
    echo ❌ PyInstaller build failed
    exit /b 1
)

if not exist "dist\pacific.exe" (
    echo ❌ pacific.exe not found
    exit /b 1
)
echo   ✅ dist\pacific.exe
echo.

REM ── Step 4: Smoke test ────────────────────────────────────────
echo [4/7] Smoke test...
dist\pacific.exe --version >nul 2>&1
if errorlevel 1 (
    echo   ⚠ --version failed (may be OK for MSIX context)
) else (
    echo   ✅ --version works
)
echo.

REM ── Step 5: Prepare MSIX layout ──────────────────────────────
echo [5/7] Preparing MSIX layout...
set LAYOUT=build\msix_layout
if exist "%LAYOUT%" rmdir /s /q "%LAYOUT%"
mkdir "%LAYOUT%"
mkdir "%LAYOUT%\assets"

copy dist\pacific.exe "%LAYOUT%\" >nul

REM Stamp version into manifest
powershell -Command "(Get-Content 'AppxManifest.xml') -replace 'Version=\"[^\"]*\"', 'Version=\"%VERSION%\"' | Set-Content '%LAYOUT%\AppxManifest.xml'"

REM Copy or generate assets
if exist "assets\StoreLogo.png" (
    echo   Using real assets...
    xcopy assets\* "%LAYOUT%\assets\" /s /q >nul
) else (
    echo   Generating placeholder assets...
    python build\generate_store_assets.py "%LAYOUT%\assets"
)
echo   ✅ Layout ready
echo.

REM ── Step 6: Find makeappx.exe ───────────────────────────────
echo [6/7] Building MSIX...
set MAKEAPPX=
for /f "tokens=*" %%i in ('dir /b /s "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\makeappx.exe" 2^>nul') do (
    set MAKEAPPX=%%i
)
if "%MAKEAPPX%"=="" (
    echo ❌ makeappx.exe not found — install Windows 10 SDK
    echo    https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/
    exit /b 1
)
echo   Using: %MAKEAPPX%

set MSIX_NAME=Pacific-%VERSION%-x64.msix
"%MAKEAPPX%" pack /d "%LAYOUT%" /p "dist\%MSIX_NAME%" /o
if errorlevel 1 (
    echo ❌ MSIX pack failed
    exit /b 1
)
echo   ✅ dist\%MSIX_NAME%
echo.

REM ── Step 7: Summary ───────────────────────────────────────
echo [7/7] Done!
echo.
echo ═══════════════════════════════════════════════════
echo   ✅ BUILD COMPLETE
echo.
echo   EXE:   dist\pacific.exe
echo   MSIX:  dist\%MSIX_NAME%
echo.
echo   Next steps:
echo     1. Test: dist\pacific.exe --help
echo     2. Upload dist\%MSIX_NAME% to Partner Center
echo        https://partner.microsoft.com
echo     3. Submit for certification
echo.
echo   Store URL (after certification):
echo     https://apps.microsoft.com/detail/9NMR6VG01Q0B
echo ═══════════════════════════════════════════════════
echo.

pause
