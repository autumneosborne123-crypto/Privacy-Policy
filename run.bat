@echo off
:start
echo [%date% %time%] Starting FlowerBot...
.venv\Scripts\python.exe main.py
echo [%date% %time%] FlowerBot crashed or stopped. Restarting in 5 seconds...
timeout /t 5
goto start
