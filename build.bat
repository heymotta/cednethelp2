@echo off
echo ===================================================
echo     CedNet Help - Gerador de Executavel (.exe)
echo ===================================================
echo.

echo Instalando/Verificando PyInstaller...
pip install pyinstaller

echo.
echo Gerando arquivo executavel (.exe) com elevacao de Administrador (UAC)...
python -m PyInstaller --noconfirm --onedir --windowed --uac-admin --name "CedNet_Help" --collect-all customtkinter main.py

echo.
echo ===================================================
echo   CONCLUIDO! 
echo   O executavel foi gerado na pasta: dist\CedNet_Help\CedNet_Help.exe
echo   (Configurado para solicitar privilégios de Administrador automaticamente)
echo ===================================================
pause
