#!/usr/bin/env python3
"""
test_phase6.py - Mario's fireballs (Phase 6) in BlastEm, EHZ1.

    python -I tools/test_phase6.py [rom]

Fire Mario (30 rings): throwing (Genesis A), the throw pose, at most two
fireballs, no throw when crouching / not fiery, the SMB1 bounce, the wall
explosion, killing a badnik (Mario's speed untouched), a boss hit, exploding
on a harmful object, deletion off screen. Screenshots: tools/out/phase6/.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from blastem_gdb import BlastEm, S2, boot_to_level  # noqa: E402

OUT = os.path.join(HERE, "out", "phase6")
os.makedirs(OUT, exist_ok=True)
rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
emu = BlastEm(rom)
S = emu.sym
MC = S("MainCharacter")
DYN, DYN_END = S("Dynamic_Object_RAM"), S("Dynamic_Object_RAM_End")
FB_ID = S("ObjID_MarioFireball")
GFXBASE = S("MarioFrame_GfxBase")
THROW_FRAMES = {GFXBASE + 11} | {S(f"MarioFrame_Throw_{n}") for n in
                                 ["Walk1", "Walk2", "Walk3", "Skid", "Jump", "Swim1", "Swim2", "Swim3", "Stand"]}
XSPEED = 0x40 * S("Mario_XSpeedToS2")
BOUNCE = (-0x300 * S("Mario_YScale")) >> 8
failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def s16(v):
    return v - 0x10000 if v & 0x8000 else v


def mario():
    b = emu.read(MC, 0x40)
    return dict(x=int.from_bytes(b[8:10], "big"), y=int.from_bytes(b[0xC:0xE], "big"), frame=b[0x1A],
                status=b[0x22], routine=b[0x24], x_vel=s16(int.from_bytes(b[0x10:0x12], "big")),
                y_vel=s16(int.from_bytes(b[0x12:0x14], "big")))


def fireballs():
    out = []
    for s in range(DYN, DYN_END, 0x40):
        b = emu.read(s, 0x40)
        if b[0] == FB_ID:
            out.append(dict(slot=s, x=int.from_bytes(b[8:10], "big"), y=int.from_bytes(b[0xC:0xE], "big"),
                            x_vel=s16(int.from_bytes(b[0x10:0x12], "big")),
                            y_vel=s16(int.from_bytes(b[0x12:0x14], "big")), frame=b[0x1A], state=b[0x32]))
    return out


def spawn(objid, x, y):
    s = next(s for s in range(DYN, DYN_END, 0x40) if emu.r8(s) == 0)
    emu.write(s, bytes(0x40))
    emu.w16(s + 8, x); emu.w16(s + 0xC, y); emu.w8(s, objid)
    emu.frames(2)
    return s


def settle(n=150):
    for _ in range(n):
        emu.frame()
        m = mario()
        if m["routine"] == 2 and not (m["status"] & 2) and not emu.r8(S("Mario_PowerTask")):
            return m
    return mario()


def clear_fireballs(n=200):
    for _ in range(n):
        if not fireballs():
            return
        emu.frame()


def place(x, y):
    emu.w16(MC + 8, x); emu.w16(MC + 0xC, y)
    emu.w16(MC + 0x10, 0); emu.w16(MC + 0x12, 0); emu.w16(MC + 0x14, 0)
    emu.w8(MC + 0x22, (emu.r8(MC + 0x22) & 1) | 2)
    emu.w16(S("Mario_LastYVel"), 0); emu.w16(S("Mario_LastXHand"), 0); emu.w16(S("Player_X_Speed"), 0)


try:
    boot_to_level(emu)
    emu.frames(20)
    emu.write(MC + 0x30, b"\x7f\xff")

    # not fiery: no fireball
    emu.frames(2, "a"); emu.frames(10)
    check(not fireballs(), "small Mario can't throw")
    emu.w16(S("Ring_count"), 30)
    for _ in range(200):
        emu.frame()
        if emu.r8(S("PlayerStatus")) == 2 and not emu.r8(S("Mario_PowerTask")):
            break
    check(emu.r8(S("PlayerStatus")) == 2, "fiery at 30 rings")
    settle()
    emu.frames(10, "right"); emu.frames(20)               # face right

    # one throw
    emu.frames(1, "a")
    poses, fb0, vels = set(), None, []
    for i in range(40):
        emu.frame()
        poses.add(mario()["frame"])
        f = fireballs()
        if f:
            vels.append(f[0]["y_vel"])
            if fb0 is None:
                fb0 = f[0]
        if i == 3:
            emu.screenshot(os.path.join(OUT, "throw.png"))
    check(fb0 is not None and fb0["x_vel"] == XSPEED, f"a throw makes a fireball moving right at ${XSPEED:X} ({fb0 and fb0['x_vel']})")
    check(bool(poses & THROW_FRAMES), f"throw pose shown (frames {sorted(map(hex, poses))})")
    check(BOUNCE in vels, f"fireball bounces with SMB1's $FD speed (scaled {BOUNCE})")
    # ImposeGravity only caps once the fraction reaches $80: 4.00 -> 4.50 -> capped 3.00
    check(max(vels) <= ((0x480 * S("Mario_YScale")) >> 8) and vels.count(max(vels)) == 1,
          f"fall speed within SMB1's cap (max {max(vels)}, once)")
    clear_fireballs()
    check(not fireballs() and emu.read(S("Fireball_State"), 2) == b"\x00\x00",
          "fireballs leaving the screen are deleted and free their slots")

    # at most two at once
    most = 0
    for i in range(40):
        emu.frame("a" if i % 2 == 0 else None)
        most = max(most, len(fireballs()))
    check(most == 2, f"never more than 2 fireballs (max {most})")
    clear_fireballs()

    # crouching: no throw
    emu.frames(5, "down")
    emu.frames(1, "down|a")
    emu.frames(10, "down")
    check(not fireballs(), "no throw while crouching")
    emu.frames(10)

    # kill a badnik ahead (Mario's speed untouched)
    m = settle()
    bz = spawn(0x4B, m["x"] + 0x50, m["y"])
    emu.w8(bz + 0x20, 0x0A)
    emu.frames(1, "a")
    killed, m_vel = False, set()
    for i in range(40):
        emu.frame()
        m_vel.add((mario()["x_vel"], mario()["y_vel"]))
        if emu.r8(bz) != 0x4B:
            killed = True
            break
    check(killed, "fireball kills a badnik")
    check(m_vel == {(0, 0)}, f"Mario's speed untouched by the kill ({m_vel})")
    emu.screenshot(os.path.join(OUT, "kill.png"))
    clear_fireballs()

    # boss: one hit, fireball explodes
    m = settle()
    bz = spawn(0x4B, m["x"] + 0x50, m["y"])
    emu.w8(bz + 0x21, 2)
    emu.w8(bz + 0x20, 0x0A)
    emu.frames(1, "a")
    hit, exploded = False, False
    for i in range(40):
        emu.frame()
        if emu.r8(bz + 0x21) == 1:
            hit = True
        if any(f["state"] & 0x80 for f in fireballs()):
            exploded = True
    check(hit and exploded, f"fireball takes one hit off a boss and explodes (hit {hit}, exploded {exploded})")
    emu.write(bz, bytes(0x40))
    clear_fireballs()

    # harmful object: explodes, object survives
    m = settle()
    bz = spawn(0x4B, m["x"] + 0x50, m["y"])
    exploded, survived = False, True
    emu.frames(1, "a")
    for i in range(40):
        emu.w8(bz + 0x20, 0x8A)
        emu.frame()
        if any(f["state"] & 0x80 for f in fireballs()):
            exploded = True
        if emu.r8(bz) != 0x4B:
            survived = False
    check(exploded and survived, "fireball explodes on a harmful object, which survives")
    emu.write(bz, bytes(0x40))
    clear_fireballs()

    # wall: the solid pillar left of EHZ1's underground passage at x ~ $77C-$78B
    place(0x7C0, 0x200)
    settle(200)
    emu.frames(120)                                       # camera catches up
    emu.frames(2, "left"); emu.frames(10)
    m = mario()
    emu.frames(1, "a")
    frames_seen, end_x = set(), 0xFFFF
    for i in range(40):
        emu.frame()
        for f in fireballs():
            frames_seen.add(f["frame"])
            end_x = min(end_x, f["x"])
        if i == 4:
            emu.screenshot(os.path.join(OUT, "wall.png"))
    expl = {S("MarioFireballFrame_Explosion") + k for k in range(3)}
    print(f"  wall test: Mario at {m['x']:#x},{m['y']:#x}")
    check(frames_seen & expl and end_x > 0x770, f"fireball explodes at the wall (frames {sorted(frames_seen)}, min x {end_x:#x})")
    check(not fireballs(), "explosion finishes and is removed")
finally:
    emu.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
