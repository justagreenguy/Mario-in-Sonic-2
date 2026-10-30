# Mario in Sonic 2

A Sega Mega Drive / Genesis ROM hack that brings Mario and Luigi into Sonic the Hedgehog 2's zones. Mario's movement is translated from Super Mario Bros.' 6502 code into 68000 assembly, with adaptations for Sonic 2's slopes, loops, springs, and other level mechanics.

## Features

- Play as Mario or Luigi, with Luigi's distinct movement and jump behavior.
- Small, Super, and Fire forms, bouncing fireballs, stomps, and swimming.
- Two difficulty settings: **Hybrid Mode** and **Mario Mode**.
- Custom title and ending art, a Bowser encounter, and a post-credits scene.
- Built-in level select through the options menu.

## Build

On Windows, the required Lua interpreter, assembler, and compression tools are included. No Python installation or original ROM is needed to build the checked-in source.

From the project folder in PowerShell:

```powershell
cd s2disasm-master
& .\build_tools\Lua\lua.exe build.lua
```

Alternatively, open `s2disasm-master/build.bat`. A successful build produces **`s2disasm-master/s2built.bin`**, a 2 MiB ROM. Open it in a Mega Drive / Genesis emulator. A Windows BlastEm distribution is included in `blastem-win64-1.0.0/`.

```powershell
# From the project folder:
& .\blastem-win64-1.0.0\blastem.exe .\s2disasm-master\s2built.bin
```

The build scripts also support other platforms using Lua 5.3 or later and compatible native tools; Windows is the documented and verified workflow here. See the [upstream build notes](s2disasm-master/readme.md) for the base disassembly.

## Play

Choose **MARIO GAME** or **LUIGI GAME** on the title screen. In **OPTIONS**, select **HYBRID MODE** (the default) or **MARIO MODE** under DIFFICULTY. To use level select, choose a character in the LEVEL SELECT box and press Start on that box.

| Genesis input | Action |
| --- | --- |
| D-pad | Move; Down crouches when big |
| A | Hold to run; press to throw a fireball in Fire form |
| B | Jump; hold for a higher jump |
| C | Swim while underwater |
| Start | Start / pause |

These are controller inputs; keyboard bindings depend on the emulator.

Hybrid Mode combines Mario's power states with Sonic-style ring protection. Mario Mode uses stricter damage rules: small characters die without a shield even when carrying rings, and a hit while big removes rings and shrinks the character. Shields still absorb a hit.

## Project layout

| Path | Contents |
| --- | --- |
| `s2disasm-master/` | Sonic 2 source, game assets, and bundled build tools |
| `s2disasm-master/mario/` | Mario/Luigi gameplay, physics, Bowser, and presentation code |
| `smb1-disasm-master/` | SMB1 reference source and CHR graphics used by the conversion tools |
| `title_art/` | Editable title-screen Aseprite sources |
| `ending_art/` | Editable ending Aseprite sources, including Luigi variants |
| `tools/` | Art converters, ROM verification, and emulator regression scripts |
| `blastem-win64-1.0.0/` | Bundled Windows emulator and its third-party notices |
| `docs/development-history.md` | Archived implementation notes and historical test results |

## Art and development

The game-ready converted art is checked in, so a normal ROM build does not need to regenerate it. To edit the title or ending, use the existing Aseprite sources and import them from the project folder:

```powershell
python -I tools/title_art.py import
python -I tools/ending_art.py import
```

Then rebuild the ROM. The importers write previews under `tools/out/`; those files are ignored by Git. Detailed editing rules are in [title_art/README.txt](title_art/README.txt) and [ending_art/README.txt](ending_art/README.txt).

Python tools use the standard library. See [tools/README.md](tools/README.md) for verification commands and development utilities.

## Credits and notices

This project builds on the Sonic Retro Sonic 2 disassembly and the Super Mario Bros. disassembly included here. Sonic the Hedgehog and its original game content belong to Sega; Mario, Luigi, and Super Mario Bros. content belong to Nintendo. This is an unofficial fan project.

The base disassembly's [notice](s2disasm-master/readme.md) prohibits commercial use. Third-party tools retain their own notices, including [BlastEm's license](blastem-win64-1.0.0/COPYING.txt), [SDL's license](blastem-win64-1.0.0/SDL-LICENSE.txt), and [GLEW's license](blastem-win64-1.0.0/GLEW-LICENSE.txt). No blanket license is granted over the combined game code and assets.
