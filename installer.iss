; ============================================================
; CedNet Help - Receita de Instalação Inno Setup (installer.iss)
; Compila a pasta dist/CedNet_Help em um instalador profissional Windows.
; ============================================================

#define MyAppName "CedNet Help"
#define MyAppVersion "1.6.1"
#define MyAppPublisher "CedNet"
#define MyAppURL "https://github.com/heymotta/cednethelp2"
#define MyAppExeName "CedNet_Help.exe"

[Setup]
; Informações do Aplicativo
AppId={{C3D4E5F6-7A8B-9C0D-1E2F-3A4B5C6D7E8F}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Diretório padrão de instalação no Windows (C:\Arquivos de Programas\CedNet Help)
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Arquivo executável de saída e ícone do instalador
OutputDir=dist_setup
OutputBaseFilename=CedNet_Help_Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64

SolidCompression=yes
WizardStyle=modern

; Solocita privilégios de Administrador na instalação
PrivilegesRequired=admin

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Copia recursivamente todos os arquivos compilados da pasta dist/CedNet_Help
Source: "dist\CedNet_Help\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
