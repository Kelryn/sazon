; Instalador de Menu + Alcampo para Windows (Inno Setup) — Fase 8.
;
; Requiere haber construido antes el .exe:
;     .venv\Scripts\pyinstaller --clean --noconfirm menu-app.spec
; y tener instalado Inno Setup (https://jrsoftware.org/isinfo.php). Luego:
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
; Produce:  dist\MenuAlcampo-Setup.exe

#define AppName "Sazon"
; AppVersion se puede pasar desde CI: ISCC /DAppVersion=X.Y.Z (ver .github/workflows).
#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#define AppExe "Sazon.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\Sazon
DefaultGroupName=Sazon
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=Sazon-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
; No requiere admin: instala en la carpeta del usuario.
PrivilegesRequired=lowest
WizardStyle=modern
; Al actualizar, cierra Sazon si esta abierto (para reemplazar el .exe en uso) y lo
; vuelve a abrir al terminar. Necesario para el auto-update desde la propia app.
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "dist\{#AppExe}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir Menu + Alcampo"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Los datos del usuario (catalogo, config y planes) viven en %LOCALAPPDATA%\Sazon.
; Se dejan por defecto; descomenta para borrarlos al desinstalar:
; Type: filesandordirs; Name: "{localappdata}\Sazon"
