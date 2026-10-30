#!/usr/bin/env python3
"""
test_hangbar.py - letting go of hang bars (H37) in BlastEm.

    python -I tools/test_hangbar.py [rom]

Spawns a WFZ handle (ObjD9) on Mario in EHZ1; he grabs it. C and A don't
release him (Mario's jump is B only); B does, as his own standing jump
(SMB1 jump speed, Player_State 1), and holding B gives the
full held-jump height - far above the -$300 hop S2 gives Sonic (~20 px).
A tapped B gives a shorter jump (variable height). Exit code 1 on failure.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blastem_gdb import BlastEm, boot_to_level, S2  # noqa: E402

rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
emu = BlastEm(rom)
S = emu.sym
MC = S("MainCharacter")
failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def hang():
    """A fresh ObjD9 on Mario's position; wait until he hangs from it."""
    for slot in range(0x10, 0x80):
        a = S("Object_RAM") + slot * 0x40
        if emu.r8(a) == S("ObjID_PostCredits") or emu.r8(a) == 0xD9:
            emu.write(a, bytes(0x40))
    emu.frames(30)
    for slot in range(0x20, 0x80):
        a = S("Object_RAM") + slot * 0x40
        if emu.r8(a) == 0:
            break
    emu.write(a, bytes(0x40))
    emu.w8(a, 0xD9)
    emu.w16(a + 8, emu.r16(MC + 8))
    emu.w16(a + 0xC, emu.r16(MC + 0xC))
    for _ in range(10):
        emu.frame()
        if emu.r8(MC + 0x2A) == 1:
            return True
    return False


def release(spec_frames):
    """Inputs per frame; returns (released frame, first y_vel, rise in px, Player_State, sound)."""
    y0 = emu.r16(MC + 0xC)
    released, yv, apex, state, sfx = None, None, y0, None, set()
    for i, spec in enumerate(spec_frames):
        emu.frame(spec)
        sfx.add(emu.r8(S("Sound_Queue") + 2))
        if released is None and emu.r8(MC + 0x2A) == 0:
            released = i
        if released is not None:
            if yv is None:
                emu.frame(spec)                            # (RAM shows the previous frame's logic)
                yv = s16(emu.r16(MC + 0x12))
                state = emu.r8(S("Player_State"))
            apex = min(apex, emu.r16(MC + 0xC))
    return released, yv, y0 - apex, state, sfx


try:
    boot_to_level(emu, 0)
    emu.frames(60)
    emu.w8(MC + 0x30, 0x7F)                                # invulnerable
    check(hang(), "Mario grabs the handle (obj_control 1)")
    r, *_ = release(["c"] * 5 + [None] * 5 + ["a"] * 5)
    check(r is None and emu.r8(MC + 0x2A) == 1, "C and A don't let go")
    r, yv, rise, state, sfx = release(["b"] * 45 + [None] * 15)
    check(r is not None, "B lets go")
    check(yv is not None and abs(yv - (-0x400 * S("Mario_YScale") >> 8)) <= 0x40 and state == 1,
          f"a real jump: y_vel {yv} (SMB1 standing jump {-0x400 * S('Mario_YScale') >> 8}), Player_State {state}")
    check(rise > 60, f"holding B: a full jump ({rise} px; S2's -$300 hop gives ~20)")
    # (the jump sound comes from InitJS like every jump; the driver empties
    # Sound_Queue during V-int, before the test could read it)
    emu.frames(60)
    check(hang(), "grabs a new handle")
    r, yv, short, state, _ = release(["b"] * 3 + [None] * 57)
    check(r is not None and 0 < short < rise, f"a tapped B: a shorter jump ({short} px)")
finally:
    emu.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
