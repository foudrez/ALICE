@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo ALICE V-Pet - Portable Environment Setup (Windows)
echo ========================================================

set "ENV_DIR=%~dp0env"
set "MAMBA_EXE=%ENV_DIR%\micromamba.exe"

if not exist "%ENV_DIR%" (
    mkdir "%ENV_DIR%"
)

if not exist "%MAMBA_EXE%" (
    echo [System] Downloading Micromamba portable...
    curl -L "https://micro.mamba.pm/api/micromamba/win-64/latest" -o "%ENV_DIR%\micromamba.tar.bz2"
    
    echo [System] Extracting Micromamba...
    tar -xf "%ENV_DIR%\micromamba.tar.bz2" -C "%ENV_DIR%"
    move "%ENV_DIR%\Library\bin\micromamba.exe" "%MAMBA_EXE%"
    rmdir /S /Q "%ENV_DIR%\Library"
    rmdir /S /Q "%ENV_DIR%\info"
    del "%ENV_DIR%\micromamba.tar.bz2"
)

echo [System] Creating Python 3.10 environment in .\env...
"%MAMBA_EXE%" create -p "%ENV_DIR%" python=3.10 -c conda-forge -y

echo [System] Installing requirements from requirements.txt...
"%MAMBA_EXE%" run -p "%ENV_DIR%" pip install -r "%~dp0requirements.txt"

echo ========================================================
echo [System] Setup Complete! The ALICE environment is ready.
echo ========================================================
pause
