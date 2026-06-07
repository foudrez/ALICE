[Setup]
AppName=ALICE
AppVersion=1.0.0
DefaultDirName={autopf}\ALICE
DefaultGroupName=ALICE
OutputDir=.\installer
OutputBaseFilename=ALICE_Setup
Compression=lzma
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
PrivilegesRequired=admin

[Files]
; Tauri executable (assuming you have compiled it and placed it in the root as ALICE.exe)
Source: "ALICE.exe"; DestDir: "{app}"; Flags: ignoreversion
; WebUI folder (needed if Tauri is configured to load from it at runtime, though Tauri usually bundles this. If bundled, omit this line)
; Python backend and resources
Source: "main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "webui.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "setup_env.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.yaml"; DestDir: "{app}"; Flags: ignoreversion
; Assuming directories like memory, prompts, etc. need to be included
Source: "memory\*"; DestDir: "{app}\memory"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "prompts\*"; DestDir: "{app}\prompts"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "tools\*"; DestDir: "{app}\tools"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ALICE"; Filename: "{app}\alice.exe"
Name: "{autodesktop}\ALICE"; Filename: "{app}\alice.exe"

[Run]
; Run the setup environment script after installation finishes to download heavy AI dependencies
Filename: "{app}\setup_env.bat"; Description: "Download and setup AI Environment (Micromamba, PyTorch)"; Flags: postinstall waituntilterminated
; Optionally launch the app immediately after setup
Filename: "{app}\alice.exe"; Description: "Launch ALICE"; Flags: postinstall nowait
