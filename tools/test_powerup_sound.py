#!/usr/bin/env python3
"""
test_powerup_sound.py - check that Mario's power-up sound plays SMB1's pitches.

    python -I tools/test_powerup_sound.py [rom]

Boots to EHZ1 as Mario, gives him 10 rings (Mario_UpdatePower plays
SndID_MarioPowerUp), then reads the sound driver's PSG3 SFX track in Z80 RAM
every frame. The divider the driver writes to the PSG is the track's
frequency + detune; the distinct values, in order, must equal the PSG dividers
tools/nes_sfx2smps.py derives from SMB1's PowerUpGrabFreqData (27 tones).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blastem_gdb import BlastEm, S2, boot_to_level  # noqa: E402

rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
sfx = open(os.path.join(S2, "sound", "sfx", "D2 - Mario Power Up.asm")).read()
# expected dividers, from the converter's comments ("NES timer $0D5" -> N = t + 1)
expected = [int(t, 16) + 1 for t in re.findall(r"NES timer \$([0-9A-F]+)", sfx)]

emu = BlastEm(rom)
S = emu.sym
Z80 = 0xA00000
TRACK = Z80 + S("zSFX_PSG3")
seen, playing_frames = [], 0
try:
    boot_to_level(emu)
    emu.frames(20)
    emu.w16(S("Ring_count"), 10)
    for i in range(90):
        emu.frame()
        t = emu.read(TRACK, 0x1A)
        if t[0] & 0x80:                                     # track is playing
            playing_frames += 1
            det = t[0x19] - 0x100 if t[0x19] & 0x80 else t[0x19]
            n = (t[0x0E] << 8 | t[0x0D]) + det
            if not seen or seen[-1] != n or (len(seen) < len(expected) and expected[len(seen)] == n
                                              and expected[len(seen) - 1] == n):
                seen.append(n)
finally:
    emu.close()

# collapse repeats the same way as the expected list (consecutive equal tones are possible)
def runs(v):
    return [x for i, x in enumerate(v) if i == 0 or v[i - 1] != x]

ok = runs(seen) == runs(expected)
print("expected:", runs(expected))
print("played:  ", runs(seen))
print(f"track played for {playing_frames} frames (SMB1: 54)")
print("PASS" if ok and 50 <= playing_frames <= 58 else "FAIL")
sys.exit(0 if ok and 50 <= playing_frames <= 58 else 1)
