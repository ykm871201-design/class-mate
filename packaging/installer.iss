; 학급 편성 도우미 (Class Mate) 설치 파일 — Inno Setup 6
; 빌드:  ISCC.exe /DAppVersion=1.0.0 packaging\installer.iss   (먼저 PyInstaller 로 dist\ClassMate 를 만들어야 함)
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "학급 편성 도우미 (Class Mate)"
#define AppExe "ClassMate.exe"

[Setup]
AppId={{8E3C5B2A-7D41-4F7B-9C2E-3A1D6B0F9E21}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Class Mate
AppPublisherURL=https://github.com/ykm871201-design/class-mate
AppSupportURL=https://github.com/ykm871201-design/class-mate/issues
DefaultDirName={autopf}\ClassMate
DefaultGroupName=학급 편성 도우미
DisableProgramGroupPage=yes
; 관리자 권한 없이 사용자 계정에 설치 (학교 PC 고려). 필요하면 설치 중 '모든 사용자'로 바꿀 수 있음
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=ClassMate-Setup-{#AppVersion}
SetupIconFile=classmate.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
InfoAfterFile=after_install.txt
CloseApplications=yes

[Languages]
#if FileExists(AddBackslash(CompilerPath) + "Languages\Korean.isl")
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
#endif
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로 가기 만들기"; GroupDescription: "추가 작업:"

[Files]
Source: "..\dist\ClassMate\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\samples\*"; DestDir: "{app}\samples"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; DestName: "사용설명서.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\학급 편성 도우미"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{group}\예시 엑셀 파일"; Filename: "{app}\samples"
Name: "{group}\사용 설명서"; Filename: "{app}\사용설명서.txt"
Name: "{group}\학급 편성 도우미 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\학급 편성 도우미"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "지금 학급 편성 도우미 실행"; Flags: nowait postinstall skipifsilent
