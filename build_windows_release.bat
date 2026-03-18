@echo off
setlocal

cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if %errorlevel%==0 (
        set "PYTHON_CMD=python"
    ) else (
        echo Python 3.9+ is required to build the Windows EXEs.
        echo Install Python from https://www.python.org/downloads/windows/ and rerun this file.
        exit /b 1
    )
)

%PYTHON_CMD% -m venv .venv
if errorlevel 1 exit /b 1

call .venv\Scripts\activate.bat
if errorlevel 1 exit /b 1

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

pip install -r requirements-build.txt
if errorlevel 1 exit /b 1

call build_windows.bat
if errorlevel 1 exit /b 1

echo.
echo Build complete.
echo EXEs:
echo   dist\LookingGlassLwsGenerator.exe
echo   dist\LookingGlassQuiltMaker.exe
