# HandGestureMouse - Windows PyInstaller build helper.
#
# Usage (from the project root):
#     powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
#     powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -OneFile
#     powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -SkipTests
#
# The script creates/updates a virtual environment, installs dependencies,
# ensures the MediaPipe model is present, runs the test suite, then builds the
# application with PyInstaller.

param(
    [switch]$OneFile,
    [switch]$SkipTests,
    [string]$Python = "py"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location -LiteralPath $Root
Write-Host "Project root: $Root"

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creating virtual environment..."
    & $Python -m venv .venv
}

Write-Host "Installing dependencies..."
& $VenvPython -m pip install --upgrade pip
& $VenvPython -m pip install -r requirements.txt
& $VenvPython -m pip install pyinstaller pytest pytest-cov

Write-Host "Ensuring MediaPipe model is present..."
& $VenvPython scripts\download_model.py

Write-Host "Generating application icon..."
& $VenvPython scripts\make_icon.py

if (-not $SkipTests) {
    Write-Host "Running tests..."
    & $VenvPython -m pytest -q
    if ($LASTEXITCODE -ne 0) {
        throw "Tests failed; aborting build."
    }
}

# Toggle ONE_FILE inside the spec when requested.
$SpecPath = Join-Path $Root "packaging\HandGestureMouse.spec"
$SpecText = Get-Content -LiteralPath $SpecPath -Raw
if ($OneFile) {
    $SpecText = $SpecText -replace "ONE_FILE = False", "ONE_FILE = True"
} else {
    $SpecText = $SpecText -replace "ONE_FILE = True", "ONE_FILE = False"
}
Set-Content -LiteralPath $SpecPath -Value $SpecText

Write-Host "Building with PyInstaller..."
& $VenvPython -m PyInstaller "packaging\HandGestureMouse.spec" --noconfirm --clean

Write-Host ""
Write-Host "Build complete."
if ($OneFile) {
    Write-Host "Single-file executable: dist\HandGestureMouse.exe"
} else {
    Write-Host "Folder build: dist\HandGestureMouse\HandGestureMouse.exe"
}