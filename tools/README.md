# Development tools

Run these commands from the project folder with Python 3 (the scripts were developed with Python 3.12). They use the standard library; no pip packages are required. Build the ROM first when using verification or emulator tests.

## ROM art verification

```powershell
python -I tools/verify_mario_art.py tools/chr2md.py s2disasm-master/s2built.bin s2disasm-master/s2.lst
```

This decodes Mario and fireball frames from the ROM and compares them with the SMB1 sprite composition. It does not launch an emulator.

## Emulator regression scripts

The `test_*.py` files are standalone scripts, not a pytest suite. They launch the bundled Windows BlastEm through its GDB stub on port 1234, using symbols in `s2disasm-master/s2.lst`. Run one at a time and leave that port free. Screenshot captures need an unobscured emulator window on an interactive Windows desktop.

For example:

```powershell
python -I tools/test_options.py
python -I tools/test_phase3.py
python -I tools/test_luigi.py
python -I tools/test_phase9.py
```

The phase scripts cover menus and basic movement (2), SMB1 physics comparisons (3), terrain/animation (4), power states and damage (5), fireballs (6), presentation/swimming (7), and Mario Mode (9). Named scripts cover Bowser, breakable objects, hang bars, Luigi, options, power-up sound and pauses, star power, the Wing Fortress ending, and the post-credits scene.

Screenshots and logs are generated in `tools/out/` and are disposable. Earlier phase numbers describe the implementation history; the scripts remain useful regression checks.

## Asset pipelines

| Script | Purpose |
| --- | --- |
| `chr2md.py` | Convert SMB1 character CHR art into Mega Drive tiles, mappings, and DPLCs |
| `luigi_palette.py` | Generate Luigi art and palettes |
| `title_art.py` | Export/import title-screen Aseprite art and render previews |
| `ending_art.py` | Export/import ending Aseprite art and render previews |
| `postcredits_art.py` | Generate post-credits text and Peach art |
| `levsel_art.py` | Generate the modified level-select tilemap |
| `nes_sfx2smps.py` | Convert NES sound effects into SMPS data |
| `nemesis.py` | Nemesis compression/decompression used by the art tools |

Read each script's docstring before running it: generators overwrite their game-ready output. Normal builds use the checked-in converted assets. In the art tools, `export --force` replaces editable art with the original Sonic 2 versions; use `import` to apply your edits.

## Play-session utilities

`watch_session.py` records live play through BlastEm; `analyze_session.py` summarizes the resulting CSV. `blastem_gdb.py` provides the shared debugger and scripted controller API. `smb1_ref.py` supplies a Python physics reference for comparisons. `fusion_test.ps1` is an older manual-testing alternative with a machine-specific Fusion path; the automated scripts use BlastEm.
