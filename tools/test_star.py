#!/usr/bin/env python3
"""
test_star.py - Mario's star flash (palette cycle while invincible), EHZ1.

    python -I tools/test_star.py [rom]

Gives Mario invincibility and samples palette line 0 entries $3/$A/$C/$F
every frame: they must cycle through four colour sets (the first being
Mario's own), change every 2 frames, every 4 in the last 2 seconds, and be
restored exactly when invincibility ends. Screenshots: tools/out/star/.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from blastem_gdb import BlastEm, S2, boot_to_level  # noqa: E402

OUT = os.path.join(HERE, "out", "star")
os.makedirs(OUT, exist_ok=True)
rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
emu = BlastEm(rom)
S = emu.sym
MC = S("MainCharacter")
PAL = S("Normal_palette")
ENTRIES = [0x3, 0xA, 0xC, 0xF]
failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def colours():
    p = emu.read(PAL, 0x20)
    return tuple(int.from_bytes(p[e * 2:e * 2 + 2], "big") for e in ENTRIES)


def changes(seq):
    idx = [i for i in range(1, len(seq)) if seq[i] != seq[i - 1]]
    return [b - a for a, b in zip(idx, idx[1:])]


try:
    boot_to_level(emu)
    emu.frames(30)
    original = colours()
    emu.w8(MC + 0x2B, emu.r8(MC + 0x2B) | 2)           # invincible
    emu.w16(MC + 0x32, 4 * 60)                         # 4 seconds
    seq = []
    for i in range(4 * 60 + 20):
        emu.frame("right" if (i // 60) % 2 == 0 else "left")
        seq.append(colours())
        if i in (30, 31, 32, 33):
            emu.screenshot(os.path.join(OUT, f"star_{i}.png"))
    early, late = seq[:100], seq[4 * 60 - 100:4 * 60 - 10]
    sets = set(seq[:4 * 60])
    check(len(sets) == 4 and original in sets, f"4 colour sets, one of them Mario's own ({len(sets)} sets)")
    ce, cl = changes(early), changes(late)
    check(ce and all(c == 2 for c in ce), f"changes every 2 frames early on ({sorted(set(ce))})")
    check(cl and all(c == 4 for c in cl), f"changes every 4 frames in the last 2 seconds ({sorted(set(cl))})")
    check(seq[-1] == original and not (emu.r8(MC + 0x2B) & 2), "Mario's colours restored when the star ends")
finally:
    emu.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
