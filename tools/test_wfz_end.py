#!/usr/bin/env python3
"""
test_wfz_end.py - the end-of-WFZ cutscene with Mario (hook H20), in BlastEm.

    python -I tools/test_wfz_end.py [rom]

Warps to WFZ, puts Mario on the last platform, spawns the cutscene object
(ObjB2 subtype $54) with controls locked as the level does, and checks that
Mario's sprite is his own (no Sonic frame), that he hops onto the Tornado and
lands on it, and that he is still on it later. Also checks the fireball
tiles' VRAM slot is the one Mario's DPLC never reaches. Screenshots:
tools/out/wfz_end/. Exit code 1 on any failure.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from blastem_gdb import BlastEm, S2, boot_to_level  # noqa: E402

OUT = os.path.join(HERE, "out", "wfz_end")
os.makedirs(OUT, exist_ok=True)
rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
emu = BlastEm(rom)
S = emu.sym
MC = S("MainCharacter")
DYN, DYN_END = S("Dynamic_Object_RAM"), S("Dynamic_Object_RAM_End")
failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def mario():
    b = emu.read(MC, 0x40)
    w = lambda o: int.from_bytes(b[o:o + 2], "big")
    return dict(x=w(8), y=w(0xC), frame=b[0x1A], anim=b[0x1C], status=b[0x22], routine=b[0x24], objctl=b[0x2A])


try:
    boot_to_level(emu)
    emu.w16(S("Current_ZoneAndAct"), 0x0600)
    emu.w16(S("Level_Inactive_flag"), 1)
    for _ in range(3000):
        emu.frame()
        if emu.r8(S("Game_Mode")) == 0x0C and emu.r8(MC) == S("ObjID_Mario") and emu.r8(MC + 0x24) == 2:
            break
    emu.frames(60)
    emu.write(MC + 0x30, b"\x7f\xff")
    emu.w16(MC + 8, 0x2E10); emu.w16(MC + 0xC, 0x500)    # above the last platform (floor at y ~$5F1)
    emu.w8(MC + 0x22, emu.r8(MC + 0x22) | 2)
    for _ in range(2000):
        emu.frame()
        if emu.r16(S("Camera_X_pos")) >= 0x2D00 and not emu.r8(MC + 0x22) & 2:
            break
    emu.frames(30)
    m = mario()
    print(f"  Mario at {m['x']:#x},{m['y']:#x} status {m['status']:#x}")
    emu.screenshot(os.path.join(OUT, "start.png"))

    s = next(s for s in range(DYN, DYN_END, 0x40) if emu.r8(s) == 0)
    emu.write(s, bytes(0x40))
    emu.w8(s + 0x28, 0x54)                                 # subtype: WFZ end
    emu.w16(s + 8, 0x2E58); emu.w16(s + 0xC, 0x66C)
    emu.w8(s, 0xB2)
    emu.w8(S("Control_Locked"), 1)

    gfx = S("MarioFrame_GfxBase")
    states, sonic_frames, landed_at, hop_seen = [], set(), None, False
    for i in range(1400):
        if i < 600 and emu.r8(s + 0x25) == 4:
            emu.w16(S("Camera_BG_X_offset"), 0x380)       # the plane comes (as the level's scrolling does)
        emu.frame()
        st = emu.r8(s + 0x25)
        m = mario()
        if not states or states[-1] != st:
            states.append(st)
            print(f"  f{i}: cutscene state {st:#x}, Mario {m['x']:#x},{m['y']:#x}, Tornado "
                  f"{emu.r16(s + 8):#x},{emu.r16(s + 0xC):#x}")
        if st in (2, 4, 6) and m["frame"] == 1:
            sonic_frames.add(i)
        if st == 8:
            hop_seen = hop_seen or emu.r8(S("Mario_TornadoHop")) != 0
            if i % 6 == 0:
                print(f"    hop f{i}: Mario {m['x']:#x},{m['y']:#x} Tornado {emu.r16(s + 8):#x},{emu.r16(s + 0xC):#x}")
        if st == 0xA and landed_at is None:
            landed_at = i
            emu.screenshot(os.path.join(OUT, "landed.png"))
        if st == 6 and i % 20 == 0:
            emu.screenshot(os.path.join(OUT, "waiting.png"))
        if m["routine"] >= 6:
            break
    m = mario()
    check(not sonic_frames, f"Mario never shows Sonic's frame 1 while waiting ({len(sonic_frames)} frames)")
    check(hop_seen, "Mario hops (Mario_TornadoHop)")
    check(landed_at is not None, f"Mario lands on the Tornado (states {[hex(x) for x in states]})")
    check(m["routine"] == 2 and m["objctl"] == 0 and states[-1] >= 0xC,
          f"after landing: alive, own movement back, the Tornado flies on (routine {m['routine']}, "
          f"obj_control {m['objctl']:#x}, state {states[-1]:#x})")
    emu.screenshot(os.path.join(OUT, "riding.png"))
    check(S("ArtTile_MarioFireball") == 0x780 + 0x1B and S("MarioFrame_MaxTiles") <= 0x1B,
          f"fireball tiles at {S('ArtTile_MarioFireball'):#x}, past Mario's largest frame ({S('MarioFrame_MaxTiles')} tiles)")
finally:
    emu.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
