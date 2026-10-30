#!/usr/bin/env python3
"""
test_bowser.py - the WFZ Bowser fight (Phase 7.5) in BlastEm.

    python -I tools/test_bowser.py [rom]

Run A: Mario enters the arena from the left; the fight starts (laser walls,
Robotnik, Bowser, the axe); Bowser paces, jumps, breathes flames and throws
hammers; the castle theme (MusID_BowserCastle) reaches the Z80 driver and its PSG1
track loops; touching Bowser hurts. Mario touches the axe: Bowser's bridge
collapses, he falls, explosions, then ObjC5's ending (camera floor $720,
controls back, walls gone).
Run B: fireballs take Bowser's 5 hit points; he falls upside down; the level
only ends at the axe.
Screenshots: tools/out/bowser/. Exit code 1 on any failure.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from blastem_gdb import BlastEm, S2, boot_to_level  # noqa: E402

OUT = os.path.join(HERE, "out", "bowser")
os.makedirs(OUT, exist_ok=True)
rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def run(fireballs):
    emu = BlastEm(rom)
    S = emu.sym
    MC = S("MainCharacter")
    OBJ, OBJ_END = S("Object_RAM"), S("Dynamic_Object_RAM_End")
    BOWSER, MISC = S("ObjID_Bowser"), S("ObjID_BowserMisc")

    def objs(oid, sub=None):
        out = []
        for s in range(OBJ, OBJ_END, 0x40):
            b = emu.read(s, 0x40)
            if b[0] == oid and (sub is None or b[0x28] == sub):
                out.append((s, b))
        return out

    def w(b, o):
        return int.from_bytes(b[o:o + 2], "big")

    def mario():
        b = emu.read(MC, 0x40)
        return dict(x=w(b, 8), y=w(b, 0xC), routine=b[0x24], status=b[0x22])

    def god():
        emu.write(MC + 0x30, b"\x00\x7f")

    try:
        boot_to_level(emu)
        emu.w16(S("Current_ZoneAndAct"), 0x0600)
        emu.w16(S("Level_Inactive_flag"), 1)
        for _ in range(3000):
            emu.frame()
            if emu.r8(S("Game_Mode")) == 0x0C and emu.r8(MC) == S("ObjID_Mario") and emu.r8(MC + 0x24) == 2:
                break
        emu.frames(60)
        god()
        # just inside the arena's left edge, short of the trigger at $2B10 (from $2AC0 a
        # wall is in the way); the level event loads the boss art at camera $2880/$400
        emu.w16(MC + 8, 0x2B00); emu.w16(MC + 0xC, 0x4C0)
        emu.w8(MC + 0x22, emu.r8(MC + 0x22) | 2)
        for _ in range(2500):
            emu.frame()
            god()
            if emu.r16(S("Camera_X_pos")) >= 0x2A00 and not emu.r8(MC + 0x22) & 2:
                break
        emu.frames(60)
        m = mario()
        print(f"  Mario at {m['x']:#x},{m['y']:#x}; arena objects: {len(objs(BOWSER))}")
        if fireballs:
            emu.w16(S("Ring_count"), 30)
            for _ in range(300):
                emu.frame(); god()
                if emu.r8(S("PlayerStatus")) == 2 and not emu.r8(S("Mario_PowerTask")):
                    break
        # walk in: the fight starts
        started, arena = False, objs(BOWSER)
        walking = True
        for i in range(400):
            emu.frame("right" if walking else None); god()
            if walking and any(o[0x25] >= 4 for _, o in objs(BOWSER)):
                walking = False                            # triggered: stop well short of Bowser
            if emu.r8(S("Bowser_FightOn")):
                started = True
                break
        m = mario()
        st = [o[0x25] for _, o in objs(BOWSER)]
        check(started, f"walking into the arena starts the fight (Mario x {m['x']:#x}, controller states {st})")
        if not started:
            return
        walls = [s for s, b in objs(S("ObjID_WFZBoss")) if b[0x24] == 4]
        check(len(walls) == 2, f"two laser walls ({len(walls)})")
        bp = emu.r16(S("Bowser_Ptr")) | 0xFF0000
        b = emu.read(bp, 0x40)
        check(b[0] == BOWSER, f"Bowser exists at {bp:#x} (ground y {w(b, 0x34):#x})")
        emu.screenshot(os.path.join(OUT, f"fight{'_fb' if fireballs else ''}.png"))
        axe = objs(MISC, 4)
        check(len(axe) == 1, "the axe is there")
        ax, ay = (w(axe[0][1], 8), w(axe[0][1], 0xC)) if axe else (0, 0)
        print(f"  axe at {ax:#x},{ay:#x}")

        if not fireballs:
            xs, ys, flames, hammers, hurt = set(), set(), 0, 0, False
            ground = w(b, 0x34)
            prev = set()
            # the castle theme: Z80 driver RAM (song ID, PSG1 track's data pointer in the bank window)
            Z80 = 0xA00000
            psg1 = S("zSongPSG1")
            lo = 0x8000 + (S("MarioCastle_PSG1") - S("MusicPoint1"))
            hi = 0x8000 + (S("MarioCastle_PSG2") - S("MusicPoint1"))
            song_ids, ptrs = set(), []
            for i in range(900):
                emu.frame(); god()
                song_ids.add(emu.r8(Z80 + S("zCurSong")))
                t = emu.read(Z80 + psg1, 5)
                if t[0] & 0x80:                            # track playing
                    ptrs.append((i, t[3] | t[4] << 8))
                b = emu.read(bp, 0x40)
                xs.add(w(b, 0x30)); ys.add(w(b, 0xC))
                now = {(s, o[0x28]) for s, o in objs(MISC)}
                for s, sub in now - prev:                  # newly appeared this frame
                    flames += sub == 0
                    hammers += sub == 2
                prev = now
                if i == 300:
                    emu.screenshot(os.path.join(OUT, "flames.png"))
            check(len(xs) > 5, f"Bowser paces (x range {min(xs):#x}-{max(xs):#x})")
            check(min(ys) < ground - 16, f"Bowser jumps (highest y {min(ys):#x}, ground {ground:#x})")
            check(flames > 0, f"Bowser breathes flames ({flames})")
            check(hammers > 0, f"Bowser throws hammers ({hammers})")
            check(S("MusID_BowserCastle") in song_ids, f"the castle theme reaches the driver (zCurSong {sorted(map(hex, song_ids))})")
            castle = [(i, p) for i, p in ptrs if lo <= p < hi]
            wraps = [castle[k][0] for k in range(1, len(castle)) if castle[k][1] < castle[k - 1][1]]
            check(len(castle) > 600 and wraps, f"PSG1 plays MarioCastle_PSG1 ({len(castle)} frames) and loops"
                                               f" (jumps back at frames {wraps}; a pass is ~482 frames)")
            # touching Bowser hurts
            emu.write(MC + 0x30, b"\x00\x00")
            emu.w16(S("Ring_count"), 5)
            b = emu.read(bp, 0x40)
            emu.w16(MC + 8, w(b, 8) - 12); emu.w16(MC + 0xC, w(b, 0xC))   # his left side: knocked away from the axe
            for _ in range(10):
                emu.frame()
                if mario()["routine"] == 4:
                    hurt = True
                    break
            check(hurt, "touching Bowser hurts Mario")
            for _ in range(150):
                emu.frame(); god()
        else:
            # five fireball hits (Bowser's hit points set to the last one to save time is not
            # SMB1-faithful: really throw them, standing still facing him)
            hp0 = emu.read(bp, 0x40)[0x3D]
            for k in range(60):
                b = emu.read(bp, 0x40)
                if b[0] != BOWSER or b[0x3F]:
                    break
                bx = w(b, 8)
                emu.w16(MC + 8, bx - 0x40)
                emu.frames(2, "right"); emu.frames(4)
                emu.frames(1, "a"); emu.frames(20)
                god()
            b = emu.read(bp, 0x40)
            check(b[0] == BOWSER and b[0x3F] == 0x20, f"fireballs defeat Bowser (hp {hp0} -> state {b[0x3F]:#x})")
            for _ in range(300):
                emu.frame(); god()
                if not emu.r16(S("Bowser_Ptr")):
                    break
            check(not emu.r16(S("Bowser_Ptr")), "the defeated Bowser falls off the screen and is gone")
            check(emu.r8(S("Bowser_FightOn")) != 0 and emu.r16(S("Camera_Max_Y_pos")) == 0x442,
                  "the fight is not over until the axe")

        # the axe
        check(not emu.r8(S("Bowser_AxeTouched")) and len(objs(MISC, 4)) == 1, "the axe is still there, untouched")
        emu.w16(MC + 8, ax); emu.w16(MC + 0xC, ay)
        emu.frames(3)
        check(emu.r8(S("Bowser_AxeTouched")) != 0 and emu.r8(S("Control_Locked")) != 0,
              "touching the axe: fight won, Mario held")
        states, explosions, end_ok = set(), 0, False
        for i in range(800):
            emu.frame()
            if emu.r16(S("Bowser_Ptr")):
                states.add(emu.read(emu.r16(S("Bowser_Ptr")) | 0xFF0000, 0x40)[0x3F])
            explosions = max(explosions, len(objs(S("ObjID_BossExplosion"))))
            if i in (40, 200):
                emu.screenshot(os.path.join(OUT, f"axe{i}{'_fb' if fireballs else ''}.png"))
            if emu.r16(S("Camera_Max_Y_pos")) == 0x720 and not emu.r8(S("Control_Locked")):
                end_ok = True
                break
        if not fireballs:
            check({0x80, 0x40} <= states, f"Bowser's bridge collapses, then he falls (states {sorted(states)})")
        check(explosions >= 2, f"explosions across the screen (up to {explosions} at once)")
        check(end_ok, "then the post-boss ending: camera floor $720, controls back")
        for k in range(8):
            emu.frames(40)
            print('  walls', [(hex(s), o[0x25], o[0x1C], o[0x1D], o[0x30], hex(emu.r8(w(o, 0x2C) | 0xFF0000)), hex(emu.r8((w(o, 0x2C) | 0xFF0000) + 0x22))) for s, o in objs(S('ObjID_WFZBoss')) if o[0x24] == 4])
        walls = [s for s, b in objs(S("ObjID_WFZBoss")) if b[0x24] == 4]
        check(not walls, f"the laser walls are gone ({len(walls)})")
        emu.screenshot(os.path.join(OUT, f"end{'_fb' if fireballs else ''}.png"))
    finally:
        emu.close()


run(False)
run(True)
print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
