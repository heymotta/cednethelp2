@echo off
echo ===================================================
echo     CedNet Help - Gerador de Executaveis (.exe)
echo ===================================================
echo.

echo Instalando/Verificando PyInstaller...
pip install pyinstaller

echo.
echo ===================================================
echo  [1/2] Compilando CedNet Help...
echo ===================================================
python -m PyInstaller --noconfirm --onedir --windowed --uac-admin --name "CedNet_Help" --collect-all customtkinter main.py

echo.
echo ===================================================
echo  [2/2] Compilando CedNet Updater...
echo ===================================================
cd updater
python -m PyInstaller --noconfirm --onedir --windowed --name "CedNet_Updater" --collect-all customtkinter updater_main.py
cd ..

echo.
echo Copiando CedNet_Updater para a pasta do CedNet Help...
xcopy /E /I /Y "updater\dist\CedNet_Updater" "dist\CedNet_Help\CedNet_Updater"

echo.
echo Copiando version.json para a pasta dist...
copy /Y "version.json" "dist\CedNet_Help\version.json"

echo.
echo ===================================================
echo   CONCLUIDO!
echo   CedNet Help:    dist\CedNet_Help\CedNet_Help.exe
echo   CedNet Updater: dist\CedNet_Help\CedNet_Updater\CedNet_Updater.exe
echo ===================================================
pause
