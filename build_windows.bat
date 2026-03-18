@echo off
setlocal

pyinstaller --noconfirm --clean --onefile --windowed --name LookingGlassLwsGenerator LwsGeneratorGUI.py
if errorlevel 1 exit /b 1

pyinstaller --noconfirm --clean --onefile --windowed --name LookingGlassQuiltMaker QuiltMakerGUI.py
if errorlevel 1 exit /b 1

echo.
echo Finished. Windows executables are in the dist folder.
