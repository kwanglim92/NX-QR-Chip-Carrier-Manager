; Inno Setup 스크립트 — MC QR Code Chip Carrier Manager
;
; 빌드 순서:
;   1) build.bat 실행 → dist\McQrManager\  생성
;   2) iscc installer.iss → Output\McQrManager-Setup-x.y.z.exe  생성
;
; 요구사항:
;   - Inno Setup 6.x  (https://jrsoftware.org/isdl.php)
;   - iscc 가 PATH 에 있거나 전체 경로로 실행

#define MyAppName        "MC QR Code Chip Carrier Manager"
#define MyAppVersion     "2.1.0"
#define MyAppExeName     "McQrManager.exe"
#define MyAppId          "{{2991A86F-058F-4349-9F44-1116B5C4F102}"
; AppId: MC 브랜드 2.0.0 신규 GUID. 재발급 금지 — 이후 업그레이드 감지 기준.
; 참고: 구 NX 1.0.0 AppId(A8F2D4E5-B612-4B19-8C3E-7F5D9A0E4B21)와 분리되어
;        두 제품이 별도 설치·언인스톨로 관리됩니다.

#ifnexist "dist\McQrManager\McQrManager.exe"
#error "dist\McQrManager\McQrManager.exe not found. Run build.bat before compiling installer.iss."
#endif

#ifnexist "dist\McQrManager\python311.dll"
#error "dist\McQrManager\python311.dll not found. Do not package build\McQrManager; run build.bat and package dist\McQrManager."
#endif

#ifnexist "dist\McQrManager\third_party\tesseract\tesseract.exe"
#error "Portable Tesseract is missing from dist\McQrManager\third_party\tesseract. Check PyInstaller build output."
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
DefaultDirName={autopf}\McQrManager
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=McQrManager-Setup-{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 사용자 권한으로 설치 가능 (관리자 권한 불필요)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=commandline dialog
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}
; 기존 설치본을 감지해 업그레이드
CloseApplications=yes
CloseApplicationsFilter=*.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "korean";  MessagesFile: "compiler:Languages\Korean.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; dist\McQrManager\ 전체를 설치 디렉터리로 복사
; third_party/tesseract/** 를 포함한 모든 하위 파일 보존
Source: "dist\McQrManager\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}";        Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}";  Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 설치 경로 안에 빌드 후 생긴 임시 파일 정리 (로그 등)
Type: filesandordirs; Name: "{app}\build.log"
Type: filesandordirs; Name: "{app}\build_log.txt"

; 참고:
; - 데이터베이스는 %LOCALAPPDATA%\MCQRCodeChipCarrier\chip_carrier.db 에 있어
;   언인스톨 시 자동 삭제되지 않음 (의도된 동작 — 사용자 데이터 보존).
; - 재설치 시 DB의 ocr_roi 설정이 유지되어 해상도별 프로파일이 그대로 사용됨.
; - Tesseract DLL 의존성은 third_party\tesseract\ 안에 자체 포함되어 있어
;   VC++ Redistributable 별도 설치 불필요 (UB Mannheim 빌드 기준).
; - 이전 NX 1.0.0 사용자는 1.0.0 에서 Export 번들 생성 → 2.0.0 에서 Import
;   로 데이터 이관 가능 (DB 경로가 NXQRChipCarrierManager → MCQRCodeChipCarrier
;   로 변경되어 자동 이관되지 않음).
