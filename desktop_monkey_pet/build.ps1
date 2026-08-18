$ErrorActionPreference = 'Stop'
python -m pip install -r requirements.txt
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
if (Test-Path build) { Remove-Item -Recurse -Force build }
pyinstaller --noconfirm --clean --windowed --name DesktopMonkeyPet `
  --add-data "assets;assets" `
  src/main.py
Write-Host "Build complete: dist\DesktopMonkeyPet\DesktopMonkeyPet.exe"
