@echo off
echo =========================================
echo       ALICE Development Launcher
echo =========================================
echo.
echo Launching Flask API Backend...
start "ALICE API Server" cmd /c "python -m server.main_webui"

echo Launching Web Browser to the Launcher UI...
timeout /t 5 /nobreak > nul
start http://localhost:5000/

echo.
echo NOTE: Once you add a Windows Defender exclusion for this folder, 
echo you can run 'cargo build' in the src-tauri folder to generate ALICE.exe!
echo =========================================
pause
