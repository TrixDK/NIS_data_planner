param(
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectDir

python -m PyInstaller --noconfirm --clean NISDataCenterPlanner.spec

if ($SkipInstaller) {
    Write-Host "EXE build complete: dist\NISDataCenterPlanner\NISDataCenterPlanner.exe"
    exit 0
}

$compilerCandidates = @(
    $env:ISCC_PATH,
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    (Join-Path $projectDir "_tools\Inno Setup 6\ISCC.exe"),
    (Join-Path $projectDir "_tools\InnoExtracted605\app\ISCC.exe")
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

if (-not $compilerCandidates) {
    throw "Inno Setup compiler was not found. Set ISCC_PATH or install Inno Setup 6."
}

& $compilerCandidates[0] (Join-Path $projectDir "installer.iss")
Write-Host "Installer build complete: installer_output\NIS_Data_Center_Planner_Setup_v1.5.0.exe"
