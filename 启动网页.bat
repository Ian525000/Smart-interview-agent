@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto venv
if exist "venv\Scripts\python.exe" goto other_venv
where python >nul 2>&1
if not errorlevel 1 goto python
where py >nul 2>&1
if not errorlevel 1 goto py
echo Python was not found. Install Python or activate your Python environment.
pause
exit /b 1

:venv
".venv\Scripts\python.exe" start_local.py
goto done
:other_venv
"venv\Scripts\python.exe" start_local.py
goto done
:python
python start_local.py
goto done
:py
py -3 start_local.py
:done
if errorlevel 1 pause
endlocal
