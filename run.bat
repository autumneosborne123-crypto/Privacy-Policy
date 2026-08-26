@echo off
cd /d "%~dp0"
:start
echo [%date% %time%] Starting FlowerBot...
"%~dp0.venv\Scripts\python.exe" "%~dp0main.py"
if errorlevel 2 exit /b 0
echo [%date% %time%] FlowerBot crashed or stopped. Restarting in 5 seconds...
timeout /t 5
goto start
