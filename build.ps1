$ErrorActionPreference = 'Stop'
py -m pip install -r requirements.txt
pyinstaller --noconfirm --clean --windowed --name DesktopMonkeyPet --add-data "assets;assets" src/main.py
Write-Host "EXE: dist\DesktopMonkeyPet\DesktopMonkeyPet.exe"
