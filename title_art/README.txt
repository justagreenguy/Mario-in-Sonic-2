Title screen art for the Mario build - edit these in Aseprite, then re-import.

1. Open a .aseprite file here, draw, save (keep it .aseprite, Indexed colour
   mode, and don't resize the canvas).
2. From the so-retro folder:   python -I tools/title_art.py import
   It rebuilds the game data, checks VRAM and the hardware sprite limits,
   and renders the finished screen to tools/out/title_art/scene.png.
3. Rebuild the ROM (s2disasm-master: build_tools/Lua/lua.exe build.lua).

banner.aseprite (the whole 320x224 screen)
  Art         The banner. It sits in front of the background and BEHIND the
              characters.
  Top         Drawn IN FRONT of the characters (S2 uses it for the top of the
              emblem over Sonic's head). Uses sprites, so keep it small.
  TM          Only shown on overseas consoles. Leave it empty for no TM.
  Cut         Hidden, but imported anyway. Paint over the places where the
              banner should cover the characters (S2 uses it so the emblem's
              middle hides part of Sonic). Any colour works; it's a mask.
              Costs sprites too.
  Background, Characters, Copyright
              References only (Characters is hidden: switch it on to see the
              final pose). "(c) 1992 SEGA" is drawn over the banner there.

sprite_XX.aseprite (draw on "Art")
  05 06 07    Sonic's slot rising from behind the banner; 12 = his final pose,
  09          his hand (a separate sprite; the "Body" layer shows where it goes).
  00-03       Tails' slot rising; 04 = final pose; 13 = his hand.
  "Scene" (hidden) shows the rest of the screen around the frame.

Palette (64 colours = 4 lines of 16; index = line*16 + colour)
  Line 0 = Sonic's slot, line 1 = Tails' slot and the stars, line 2 = the
  background (fixed), line 3 = banner and the highlighted menu text. You may
  change colours in any file's palette; a change applies to every file. The
  entries the menu, the copyright text and the stars use are locked (import
  says so and keeps the original):
    line 0: you can change 2 3 4 5 8 9 10 11 12 13 14 15
    line 1: you can change 1 2 7 8 9 10 12 13 14 15
    line 3: you can change 2 3 9 11 14 15
  Each 8x8 block uses one line in the game. You don't have to get it right:
  - If a block's colours (as you see them) aren't all on one line, import
    copies the missing ones into unused, unlocked entries of line 0, 1 or 3
    and says which ("spare palette entries filled").
  - It then picks the closest line per block and the nearest colour on it. It
    only lists the blocks whose colours really changed ("check these").
  Index 16, 32, 48 are transparent like 0.
  The lines come on at different times in the intro: line 1 from the start,
  line 3 fades in with the emblem, line 0 when the characters rise, line 2
  only at the background flash. So import never puts the characters on line 2,
  and puts the banner, Top and TM on line 3 whenever it can (it warns if a
  banner block had to go on another line).

subtitle.txt
  Text written under the banner in S2's own menu font (costs no VRAM): the
  text, its tile row and column, and the palette line. Import adds it to the
  banner (it replaces whatever banner art is in those 8x8 cells and warns if
  there was any). Letters A-Z, digits, spaces and . : only.

Intro gotcha: until the falling star (about 8 seconds in) the characters are
hidden below screen line 112, so they seem to rise from behind the banner.

To start a file over from Sonic 2's original: delete it and run
   python -I tools/title_art.py export
