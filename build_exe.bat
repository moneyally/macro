@echo off
cd /d "%~dp0"
echo ============================================
echo    Macro PRO  -  build EXE
echo ============================================
echo.

set "PY="
py -3 --version >nul 2>&1
if %errorlevel%==0 set "PY=py -3"
if defined PY goto gotpy
python --version >nul 2>&1
if %errorlevel%==0 set "PY=python"
if defined PY goto gotpy
python3 --version >nul 2>&1
if %errorlevel%==0 set "PY=python3"
if defined PY goto gotpy
goto nopy

:gotpy
echo Using: %PY%
%PY% --version
echo.
echo [1/4] installing packages...
%PY% -m pip install --upgrade pip
%PY% -m pip install --upgrade pynput pyautogui pillow pyinstaller

echo.
echo [2/4] making icon...
%PY% make_icon.py

echo.
echo [3/4] building exe (1-3 min)...
%PY% -m PyInstaller --onefile --noconsole --name MacroPRO --icon icon.ico --collect-submodules pynput --clean run.py

echo.
echo [4/4] checking...
if exist "dist\MacroPRO.exe" goto done
echo [X] build FAILED. read red errors above.
goto end

:done
echo [OK] DONE!  dist\MacroPRO.exe
start "" explorer dist
goto end

:nopy
echo [X] Python not installed.
echo     https://www.python.org/downloads/  (check "Add python.exe to PATH")

:end
echo.
pause
