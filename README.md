# DesktopMonkeyPet v2

This version fixes the "EXE runs but no monkey appears" problem by:

- using a dedicated visible tray icon
- using a visible fallback character if `assets/character.png` cannot load
- writing `DesktopMonkeyPet.log`
- adding safer startup/error handling
- keeping the supplied character image path at `assets/character.png`
- keeping `assets/dad.wav` reserved for future right-click audio
- retaining multiple pets, random movement, jumping, window-top platforms and basic flocking

## Important

Keep your real `assets/character.png` from the existing repository. This ZIP intentionally does not overwrite it.

Replace `assets/dad.wav` later when you have the "叫爸爸" recording.

## Build

GitHub Actions builds `DesktopMonkeyPet-windows-v2`.

If the EXE still has a problem, run it from PowerShell or send `DesktopMonkeyPet.log`.
