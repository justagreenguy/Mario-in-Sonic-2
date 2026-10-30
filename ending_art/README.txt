Ending art for the Mario build - edit these in Aseprite, then re-import.

1. Open a .aseprite file here, draw on the "Art" layer, save (keep it .aseprite,
   Indexed colour mode, and don't resize the canvas).
2. From the so-retro folder:   python -I tools/ending_art.py import
   It rebuilds the game data, checks it fits in VRAM, and writes previews to
   tools/out/ending_art/.
3. Rebuild the ROM (s2disasm-master: build_tools/Lua/lua.exe build.lua).

Files
  photo1-4      The four flashback pictures (96x72). Each has its own 16 colours:
                change them freely in the palette. Colour 0 is transparent.
  closeup       The big Tornado flying at the camera (184x120).
  sprite_07-0B  The player on the small Tornado as it turns towards the camera.
                The Tornado itself is on the locked "Reference" layer.
  sprite_0C-0E  The player jumping at the camera, over the close-up.
  luigi/        Luigi's own copies of sprite_07-0E (the game shows them when
                you play as Luigi). They started as Mario's frames recoloured
                like the in-game Luigi (white cap and overalls, green shirt);
                edit them like the Mario ones. In Luigi's palette, line 0
                colour 2 is his green instead of dark blue.
                To remake them from your current Mario frames (this
                OVERWRITES your Luigi edits):
                   python -I tools/ending_art.py luigi --force
                The photos and the close-up are shared by both.

The close-up and sprites use the game's 4 palette lines (64 colours: index =
line*16 + colour). Those colours are shared with other sprites, so palette
edits there are ignored. Each 8x8 block (counted from the canvas' top-left
corner) can only use colours from one line in the game. You don't have to
get the line right: import picks, per block, the line closest to the colours
you drew, moves each pixel to the nearest colour on it, and lists every block
it changed (check those in the previews). Index 16, 32 and 48 are transparent
like index 0.

Layers: every visible layer is imported except "Reference" (the parts that
stay, e.g. the small Tornado) and "Original" (Sonic, hidden, for comparison).
You can add your own layers; hide any you don't want imported.

Limits: close-up 170 different 8x8 tiles (repeats and mirror images are
free); sprite frames 317 non-empty 8x8 tiles for all eight together (Mario's
and Luigi's sets each have the full 317). Import says how much is used.

To start a file over from Sonic 2's original: delete it and run
   python -I tools/ending_art.py export
