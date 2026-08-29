# Build og releases

## Lokal Windows-build

1. Installer Python 3.13 og Inno Setup 6.
2. Opret et virtuelt miljø.
3. Installer `requirements.txt` og `requirements-build.txt`.
4. Kør `powershell -ExecutionPolicy Bypass -File .\build_windows.ps1`.

Den fastlåste PySide6-version i `requirements.txt` er bevidst valgt, så den pakkede
Windows-app bruger en afprøvet og reproducerbar Qt/DLL-kombination.

Resultater:

- Program: `dist\NISDataCenterPlanner\NISDataCenterPlanner.exe`
- Installer: `installer_output\NIS_Data_Center_Planner_Setup_v1.5.0.exe`

## GitHub-opdateringer

1. Opret et GitHub-repository og push projektet.
2. Skriv repository-navnet som `ejer/repository` under **Om og opdateringer** i appen.
3. Opret og push et tag, fx `v1.5.0`.
4. GitHub Actions bygger Windows-installeren og opretter en GitHub Release.

Ved næste version opdateres versionsnummeret i:

- `version_info.py`
- `windows_version_info.txt`
- `installer.iss`
