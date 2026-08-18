# Desktop Monkey Pet

Windows desktop pet prototype based on the supplied photo.

## Features
- Transparent, always-on-top desktop pets.
- Multiple independent pets with random behavior.
- Gravity, jumping, landing and simple obstacle interaction.
- Uses visible top-level Windows rectangles as platforms/edges.
- Right-click a pet to play `assets/dad.wav`.
- System tray menu for spawning pets and exiting.
- PyInstaller build script for a single-folder Windows build.

## Assets
- `assets/person.png`: transparent cutout derived from the supplied photo.
- `assets/dad.wav`: replace the placeholder with the user's audio recording.

## Run on Windows
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/main.py
```

## Build EXE
```powershell
.\build.ps1
```
The output is placed under `dist\DesktopMonkeyPet\`.

## Notes
The first prototype intentionally uses the real photo cutout rather than generating a new face or identity. The crawling effect is implemented as animation: alternating tilt, bobbing, short jumps, edge interaction and random direction changes.

The Windows obstacle model is heuristic: it reads visible top-level window rectangles and treats their top edges as walkable surfaces. Some applications with custom-rendered or protected windows may not expose useful rectangles.
