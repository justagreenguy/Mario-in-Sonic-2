#!/usr/bin/env python3
"""
luigi_palette.py - frees a palette line 0 entry for Luigi's green.

    python -I tools/luigi_palette.py

S2's palette line 0 (SonicAndTails.bin) has no green, and every entry is used
by some object drawn with line 0. Entry LUIGI_SLOT ($2, Sonic's darkest blue)
is the one the fewest objects use, so it becomes Luigi's green, and every
object art drawn with line 0 has its LUIGI_SLOT pixels moved to the next blue
(LUIGI_SLOT_MERGE, $3): shield, monitors, signpost, some badniks and bosses.
Sonic's and Tails' own art isn't touched (they aren't playable any more).

Outputs (never edit by hand):
  s2disasm-master/art/nemesis/luigi/*.nem   re-encoded copies of those arts; with
                                            marioMode, s2.asm's labels point at them
                                            (mario/mario_art.asm includes them)
  s2disasm-master/mario/luigi_palette.asm   Luigi's green for the normal palette
                                            and the three underwater palettes
  s2disasm-master/mario/luigi_slot_arts.asm the replaced arts' labels (included by
                                            mario/mario_art.asm)

The palettes themselves are not edited: while Luigi is playing, Mario_PalPointers
(mario_polish.asm) makes PalLoad_* load Luigi's copies of Pal_BGND and the
underwater palettes, which differ only in entry LUIGI_SLOT. Mario keeps the
original colour there (no art uses it any more).

Which arts: every Nemesis art that a level PLC loads at an ArtTile_* that the
code only ever draws with palette line 0 (make_art_tile(..., 0, ...)), and that
has LUIGI_SLOT pixels. The script fails if such an art is also drawn with
another line, since moving a pixel would change its colour there.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from nemesis import compress, decompress          # noqa: E402
import chr2md                                      # noqa: E402

S2 = chr2md.S2
LUIGI_SLOT = chr2md.LUIGI_SLOT
LUIGI_SLOT_MERGE = chr2md.LUIGI_SLOT_MERGE

# Arts that are drawn with line 0 but never with the level palettes Luigi changes.
NOT_IN_LEVELS = {
    "ArtNem_SpecialBack",       # Special Stage (unreachable in Mario's mode; own palette)
}

UNDERWATER = [("CPZ", "CPZ underwater.bin"), ("ARZ", "ARZ underwater.bin"), ("HPZ", "HPZ underwater.bin")]


def palette_words(name, line=0):
    d = open(os.path.join(S2, "art", "palettes", name), "rb").read()
    return [(d[line * 32 + i * 2] << 8) | d[line * 32 + i * 2 + 1] for i in range(16)]


def channels(w):
    return [(w >> s) & 0xE for s in (0, 4, 8)]           # R, G, B nibbles (even)


def word(rgb):
    r, g, b = (max(0, min(14, int(round(c / 2.0)) * 2)) for c in rgb)
    return (b << 8) | (g << 4) | r


def luigi_green():
    """Nearest Genesis colour to SMB1's Luigi green ($19 in PlayerColors)."""
    colors = open(os.path.join(chr2md.SMB, "engine", "screen", "routine", "colors.asm")).read().splitlines()
    pc = chr2md.parse_db_block(colors, "PlayerColors")
    nes = pc[4 + 3]                                     # Luigi row: bg, $30, $27, $19
    rgb = [(chr2md.NES_RGB[nes] >> s) & 255 for s in (16, 8, 0)]
    return word([c / (255 / 7) * 2 for c in rgb]), nes


def solve(a, b):
    """Least squares a x = b for a small dense system (normal equations)."""
    n = len(a[0])
    ata = [[sum(r[i] * r[j] for r in a) for j in range(n)] for i in range(n)]
    atb = [sum(r[i] * y for r, y in zip(a, b)) for i in range(n)]
    for i in range(n):                                  # Gauss-Jordan with a tiny ridge
        ata[i][i] += 1e-6
    for i in range(n):
        p = max(range(i, n), key=lambda k: abs(ata[k][i]))
        ata[i], ata[p] = ata[p], ata[i]
        atb[i], atb[p] = atb[p], atb[i]
        for k in range(n):
            if k != i:
                f = ata[k][i] / ata[i][i]
                ata[k] = [x - f * y for x, y in zip(ata[k], ata[i])]
                atb[k] -= f * atb[i]
    return [atb[i] / ata[i][i] for i in range(n)]


def underwater_green(green, name):
    """The underwater palettes are hand-tinted versions of line 0. Fit each
    output channel as a linear function of the normal R, G, B (entries 2-15,
    the ones that are real colours) and apply it to Luigi's green."""
    normal = palette_words("SonicAndTails.bin")
    under = palette_words(name)
    rows = [channels(normal[i]) + [1] for i in range(2, 16)]
    out = []
    for ch in range(3):
        coef = solve(rows, [channels(under[i])[ch] for i in range(2, 16)])
        out.append(sum(c * x for c, x in zip(coef, channels(green) + [1])))
    return word(out)


def level_line0_arts():
    asm = open(os.path.join(S2, "s2.asm"), encoding="latin-1").read()
    files = dict(re.findall(r'^(ArtNem_\w+):\s*BINCLUDE\s*"([^"]+)"', asm, re.M))
    lines = {}
    for t, l in re.findall(r"make_art_tile\((ArtTile_\w+)\s*(?:[+-][^,]*)?,\s*(\d)\s*,", asm):
        lines.setdefault(t, set()).add(int(l))
    arts = {}
    for tile, art in re.findall(r"^\s*plreq\s+(ArtTile_\w+)\s*,\s*(ArtNem_\w+)", asm, re.M):
        if 0 in lines.get(tile, ()) and art in files and art not in NOT_IN_LEVELS:
            arts.setdefault(art, set()).update(lines[tile])
    return files, arts


def main():
    files, arts = level_line0_arts()
    out_dir = os.path.join(S2, "art", "nemesis", "luigi")
    os.makedirs(out_dir, exist_ok=True)
    replaced = []
    for art in sorted(arts):
        data = decompress(open(os.path.join(S2, files[art]), "rb").read())
        n = sum((b >> 4) == LUIGI_SLOT for b in data) + sum((b & 15) == LUIGI_SLOT for b in data)
        if not n:
            continue
        if arts[art] != {0}:
            sys.exit(f"{art} uses colour ${LUIGI_SLOT:X} and is also drawn with lines {sorted(arts[art])}")
        new = bytes((((LUIGI_SLOT_MERGE if b >> 4 == LUIGI_SLOT else b >> 4) << 4) |
                     (LUIGI_SLOT_MERGE if b & 15 == LUIGI_SLOT else b & 15)) for b in data)
        fname = os.path.basename(files[art])
        open(os.path.join(out_dir, fname), "wb").write(compress(new))
        replaced.append((art, files[art], "art/nemesis/luigi/" + fname, n))
        print(f"{art:28s} {n:5d} px  {fname}")

    green, nes = luigi_green()
    under = [(z, underwater_green(green, f)) for z, f in UNDERWATER]
    path = os.path.join(S2, "mario", "luigi_palette.asm")
    with open(path, "w", newline="\n") as fh:
        fh.write("; Generated by tools/luigi_palette.py - do not edit by hand.\n")
        fh.write(f"; Palette line 0 entry ${LUIGI_SLOT:X} is Luigi's green (only while Luigi plays); the object\n")
        fh.write(f"; arts that used it now use ${LUIGI_SLOT_MERGE:X} (mario/luigi_slot_arts.asm).\n\n")
        fh.write(f"LuigiPalSlot\t\t= ${LUIGI_SLOT:X}\t; palette line 0 entry\n")
        fh.write(f"LuigiGreen\t\t= ${green:04X}\t; nearest to SMB1's Luigi green (NES ${nes:02X})\n")
        for z, w in under:
            fh.write(f"LuigiGreen_{z}_U\t= ${w:04X}\t; {z} underwater palette (fitted to its tint of line 0)\n")
    arts_path = os.path.join(S2, "mario", "luigi_slot_arts.asm")
    with open(arts_path, "w", newline="\n") as fh:
        fh.write("; Generated by tools/luigi_palette.py - do not edit by hand.\n")
        fh.write(f"; Object arts drawn with palette line 0, with their ${LUIGI_SLOT:X} pixels moved to ${LUIGI_SLOT_MERGE:X}\n")
        fh.write("; (entry $%X is Luigi's green). With marioMode, s2.asm keeps the originals as\n" % LUIGI_SLOT)
        fh.write("; <label>_S2, unused, so that nothing before the Mario code moves.\n")
        fh.write("; (each starts even: NemDec reads the header with move.w)\n")
        for art, old, new, n in replaced:
            fh.write(f"\teven\n{art}:\tBINCLUDE\t\"{new}\"\t; {n} px; was {old}\n")
        fh.write("\teven\n")
    print(f"green ${green:04X}; underwater " + ", ".join(f"{z} ${w:04X}" for z, w in under))
    print(f"{len(replaced)} arts re-encoded; wrote {os.path.relpath(path, chr2md.ROOT)}, "
          f"{os.path.relpath(arts_path, chr2md.ROOT)}")


if __name__ == "__main__":
    main()
