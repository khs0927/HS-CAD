#ifndef MyAppVersion
  #define MyAppVersion "0.2.0"
#endif

#define MyAppName "HS-CAD"
#define MyAppPublisher "HS-CAD"
#define MyAppExeName "HS-CAD.exe"

[Setup]
AppId={{73A28CF8-1A83-43BE-90BC-A9D0C6579CF7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=HS-CAD-Setup-{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕 화면 바로가기 만들기"; GroupDescription: "추가 바로가기:"; Flags: unchecked
Name: "path"; Description: "사용자 PATH에 HS-CAD 추가"; GroupDescription: "명령줄 사용:"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\INSTALL_WINDOWS.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--help"; WorkingDir: "{userdocs}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Parameters: "--help"; WorkingDir: "{userdocs}"; Tasks: desktopicon

[Registry]
Root: HKA; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Check: NeedsAddPath(ExpandConstant('{app}')); Tasks: path; Flags: preservestringtype

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "doctor"; Description: "설치 환경 진단 실행"; Flags: postinstall nowait skipifsilent unchecked

[Code]
function NeedsAddPath(Param: string): Boolean;
var
  ExistingPath: string;
begin
  if not RegQueryStringValue(HKA, 'Environment', 'Path', ExistingPath) then
    ExistingPath := '';
  Result := Pos(';' + Uppercase(Param) + ';', ';' + Uppercase(ExistingPath) + ';') = 0;
end;
