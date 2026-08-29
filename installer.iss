#define MyAppName "NIS Data Center Planner"
#define MyAppVersion "1.5.0"
#define MyAppPublisher "NIS"
#define MyAppExeName "NISDataCenterPlanner.exe"

[Setup]
AppId={{D8424284-A6EE-46C8-8976-79A4CE15DD24}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\NIS Data Center Planner
DefaultGroupName=NIS Data Center Planner
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=NIS_Data_Center_Planner_Setup_v{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayName={#MyAppName}
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Languages]
Name: "danish"; MessagesFile: "compiler:Languages\Danish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Opret genvej på skrivebordet"; GroupDescription: "Genveje:"; Flags: unchecked

[Files]
Source: "dist\NISDataCenterPlanner\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\NIS Data Center Planner"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\NIS Data Center Planner"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Start NIS Data Center Planner"; Flags: nowait postinstall skipifsilent
