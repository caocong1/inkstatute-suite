; inkstatute_installer.iss — Inno Setup script for InkStatute Windows installer (PKG-01)
;
; Produces a single-exe installer that:
; - Installs to %LOCALAPPDATA%\InkStatute
; - Creates Start Menu and Desktop shortcuts
; - Bundles Flutter app + DSH engine + portable Python + scripts + presets
; - Clean uninstaller with runtime data retention prompt

#ifndef APP_VERSION
  #define APP_VERSION "0.1.0"
#endif

[Setup]
AppName=墨律 InkStatute
AppVersion={#APP_VERSION}
AppPublisher=InkStatute
AppPublisherURL=https://inkstatute.example
DefaultDirName={localappdata}\InkStatute
DefaultGroupName=墨律 InkStatute
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=InkStatute-Setup-{#APP_VERSION}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\app\inkstatute.exe

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"; Flags: unchecked

[Files]
; Flutter app build
Source: "staging\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs createallsubdirs
; DSH engine
Source: "staging\engine\*"; DestDir: "{app}\engine"; Flags: recursesubdirs createallsubdirs
; Portable Python
Source: "staging\python\*"; DestDir: "{app}\python"; Flags: recursesubdirs createallsubdirs
; Track-changes script
Source: "staging\scripts\*"; DestDir: "{app}\scripts"; Flags: recursesubdirs createallsubdirs
; Presets
Source: "staging\presets\*"; DestDir: "{app}\presets"; Flags: recursesubdirs createallsubdirs
; Content pack
Source: "staging\content\*"; DestDir: "{app}\content"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\墨律 InkStatute"; Filename: "{app}\app\inkstatute.exe"
Name: "{group}\卸载墨律"; Filename: "{uninstallexe}"
Name: "{commondesktop}\墨律 InkStatute"; Filename: "{app}\app\inkstatute.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\app\inkstatute.exe"; Description: "立即启动墨律"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Clean uninstall — runtime data (sessions, settings) is retained by default
; User can manually delete {localappdata}\InkStatute after uninstall

[UninstallDelete]
; Only delete installed files, not runtime data
Type: filesandordirs; Name: "{app}\app"
Type: filesandordirs; Name: "{app}\engine"
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\scripts"
Type: filesandordirs; Name: "{app}\presets"
Type: filesandordirs; Name: "{app}\content"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
  begin
    // Notify user that runtime data is retained
    MsgBox(
      '墨律已卸载。' + #13#10 +
      '会话数据和设置保留在：' + #13#10 +
      ExpandConstant('{localappdata}\InkStatute') + #13#10 +
      '如需完全删除，请手动删除该目录。',
      mbInformation, MB_OK);
  end;
end;
