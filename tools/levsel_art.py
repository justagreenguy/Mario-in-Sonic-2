#!/usr/bin/env python3
"""
levsel_art.py - the Mario build's level select map (H34).

    python -I tools/levsel_art.py

Decodes S2's level select foreground map (mappings/misc/Level Select.eni,
Enigma, base 0, 40x28), replaces the SPECIAL STAGE entry's text (row 15,
columns 22-35: the 14 cells LevelSelect_MarkFields highlights) with CREDITS,
and writes mappings/misc/mario/Level Select.eni. s2.asm's MenuScreen_LevelSelect
loads it as MapEng_MarioLevSel (mario/mario_polish.asm) under marioMode.
The menu font: A-Z are tiles $1E-$37 on palette line 0; a blank cell is $4000.
Never hand-edit the output; rerun this.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from ending_art import enigma_decode, enigma_encode  # noqa: E402

S2 = os.path.join(os.path.dirname(HERE), "s2disasm-master")
SRC = os.path.join(S2, "mappings", "misc", "Level Select.eni")
DST = os.path.join(S2, "mappings", "misc", "mario", "Level Select.eni")

W, H = 40, 28
ROW, COL, CELLS = 15, 22, 14          # LevSel_MarkTable entry $14: line $F, column $2C/2
BLANK = 0x4000
TEXT = "CREDITS"


def glyph(ch):
    return BLANK if ch == " " else 0x1E + ord(ch) - ord("A")


def main():
    words = enigma_decode(open(SRC, "rb").read(), 0)
    assert len(words) == W * H, len(words)
    old = words[ROW * W + COL:ROW * W + COL + CELLS]
    expect = [glyph(c) for c in "SPECIAL STAGE".ljust(CELLS)]
    assert old == expect, "unexpected text at the SPECIAL STAGE entry: " + " ".join(f"{w:x}" for w in old)
    words[ROW * W + COL:ROW * W + COL + CELLS] = [glyph(c) for c in TEXT.ljust(CELLS)]
    data = enigma_encode(words, 0)
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(DST, "wb") as f:
        f.write(data)
    print(f"wrote {os.path.relpath(DST, S2)} ({len(data)} bytes; S2's is {os.path.getsize(SRC)})")


if __name__ == "__main__":
    main()
