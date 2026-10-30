#!/usr/bin/env python3
"""
test_phase7.py - Mario's swimming, the hold-C air swim, drowning and the
Phase 7 S2 hooks, in BlastEm.

    python -I tools/test_phase7.py [rom]

EHZ1 (dry):
  - H15: standing, the camera frames Mario's feet as it frames Sonic's.
  - Hold C in the air (user rule): a C jump is a normal jump (same apex as a
    B jump); while C is held SwimmingFlag is set, a B press mid-air is a swim
    stroke; releasing C restores the normal falling force.
ARZ1 (the water level is raised over Mario's start):
  - water entry: SwimmingFlag, swim falling force $0A
  - water walk speed (SMB1's $10, also with run held)
  - a swim stroke from the floor: SMB1's swim speed, the swim/stomp sound
  - strokes reach the surface line and its $18 force is used; a press there
    jumps out of the water (user change 2026-10-10)
  - fireballs work underwater
  - holding C, strokes take Mario out of the water and on up into the air;
    releasing C, he falls back (normal falling force), re-entering water gives
    the swim force again
  - underwater, landing on a badnik hurts (SMB1: no stomping in water)
  - no drowning (disabled 2026-10-10): the air is refilled
EHZ1 again:
  - H11: touching a starpost with 50 rings makes no Special Stage stars
  - H16: the signpost ends on Mario's face (screenshot) and the results say
    "MARIO GOT THROUGH" (mappings pointer + screenshot)
Screenshots: tools/out/phase7/. Exit code 1 on any failure.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from blastem_gdb import BlastEm, S2, boot_to_level  # noqa: E402
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location("nes_sfx2smps", os.path.join(HERE, "nes_sfx2smps.py"))
conv = importlib.util.module_from_spec(spec); spec.loader.exec_module(conv)
NOTE = {conv.note_name(i): i for i in range(len(conv.TABLE))}

OUT = os.path.join(HERE, "out", "phase7")
os.makedirs(OUT, exist_ok=True)
rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
emu = BlastEm(rom)
S = emu.sym
MC = S("MainCharacter")
DYN, DYN_END = S("Dynamic_Object_RAM"), S("Dynamic_Object_RAM_End")
OBJ, OBJ_END = S("Object_RAM"), S("Dynamic_Object_RAM_End")
TR = 0xA00000 + S("zSFX_PSG3")
YS = S("Mario_YScale")
SWIM_VEL = (-0x180 * YS) >> 8                  # PlayerYSpdData/InitMForceData[5] = $FE80, scaled
JUMP_VEL = (-0x400 * YS) >> 8
WL1, WL2, WL3 = S("Water_Level_1"), S("Water_Level_2"), S("Water_Level_3")
SURF = S("Mario_SwimSurface")
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
    return dict(x=w(8), y=w(0xC), x_vel=s16(w(0x10)), y_vel=s16(w(0x12)), r=b[0x16], frame=b[0x1A],
                anim=b[0x1C], status=b[0x22], routine=b[0x24], air=b[0x28], objctl=b[0x2A])


def ram(name):
    return emu.r8(S(name))


def gm():
    return emu.r8(S("Game_Mode"))


def wait_level(timeout=3000):
    """Wait for a (re)started level: Game_Mode $0C, Mario in control."""
    for _ in range(timeout):
        emu.frame()
        if gm() == 0x0C and emu.r8(MC) == S("ObjID_Mario") and emu.r8(MC + 0x24) == 2:
            break
    emu.frames(60)


def warp(zoneact):
    emu.w16(S("Current_ZoneAndAct"), zoneact)
    emu.w16(S("Level_Inactive_flag"), 1)
    emu.frames(5)
    wait_level()


def settle(n=200):
    for _ in range(n):
        emu.frame()
        m = mario()
        if m["routine"] == 2 and not (m["status"] & 2) and not ram("Mario_PowerTask"):
            return m
    return mario()


def invulnerable():
    emu.write(MC + 0x30, b"\x7f\xff")


def psg3():
    t = emu.read(TR, 0x1A)
    if not t[0] & 0x80:
        return "off"
    if t[0] & 2:
        return None
    det = t[0x19] - 0x100 if t[0x19] & 0x80 else t[0x19]
    return (t[0x0E] << 8 | t[0x0D]) + det


def smps_timeline(path):
    """Per-frame PSG divider (None = rest) of the generated PSG3 SFX (volume steps ignored)."""
    lines = [l.split(";")[0].strip() for l in open(path).read().splitlines()]
    start = next(i for i, l in enumerate(lines) if l.endswith("_PSG3:")) + 1
    out, detune = [], 0
    for l in lines[start:]:
        if l.startswith("smpsStop"):
            break
        if l.startswith("smpsDetune"):
            v = int(l.split("$")[1], 16); detune = v - 256 if v & 0x80 else v
        m = re.match(r"dc\.b\s+(\w+),\s*\$([0-9A-Fa-f]+)", l)
        if m:
            n = None if m.group(1) == "nRst" else conv.TABLE[NOTE[m.group(1)]] + detune
            out += [n] * int(m.group(2), 16)
    return out


def runs(v):
    return [x for i, x in enumerate(v) if i == 0 or v[i - 1] != x]


def set_water(level):
    for a in (WL1, WL2, WL3):
        emu.w16(a, level)


def box_top(m):
    return m["y"] + m["r"] + 1 - 32


def spawn(objid, x, y):
    s = next(s for s in range(DYN, DYN_END, 0x40) if emu.r8(s) == 0)
    emu.write(s, bytes(0x40))
    emu.w16(s + 8, x); emu.w16(s + 0xC, y); emu.w8(s, objid)
    return s


def teleport(x, y, timeout=1200):
    """Put Mario (airborne) at x, y and wait until the camera has caught up,
    so the objects there are loaded."""
    emu.w16(MC + 8, x); emu.w16(MC + 0xC, y)
    emu.w8(MC + 0x22, emu.r8(MC + 0x22) | 2)
    last, still = None, 0
    for _ in range(timeout):
        emu.frame()
        cx = emu.r16(S("Camera_X_pos"))
        still = still + 1 if cx == last else 0
        last = cx
        if still > 20:                                     # caught up (or at a camera limit)
            break
    emu.frames(10)


def objects(objid):
    return [s for s in range(OBJ, OBJ_END, 0x40) if emu.r8(s) == objid]


try:
    boot_to_level(emu)
    emu.frames(20)
    invulnerable()

    # ---------------- EHZ1: camera (H15) ----------------
    m = settle()
    emu.frames(90)
    m = mario()
    cam = emu.r16(S("Camera_Y_pos"))
    bias = emu.r16(S("Camera_Y_pos_bias"))
    feet_c = m["y"] + m["r"] - 0x13 - cam
    check(feet_c == bias, f"H15: camera frames Mario's feet like Sonic's (feet-$13-cam = {feet_c:#x}, bias {bias:#x})")

    # ---------------- EHZ1: hold C in the air ----------------
    def jump(spec, frames=70):
        y0, apex, flags, vels = mario()["y"], 0xFFFF, set(), []
        for i in range(frames):
            emu.frame(spec)
            m = mario()
            apex = min(apex, m["y"])
            if m["status"] & 2:
                flags.add(ram("SwimmingFlag"))
                vels.append(m["y_vel"])
        return y0 - apex, flags, vels

    hb, fb, vb = jump("b")
    settle(); emu.frames(10)
    hc, fc, vc = jump("c")
    settle(); emu.frames(10)
    check(hb > 40 and hc == 0 and not vc, f"C doesn't jump, B does (B jump {hb} px, C {hc} px)")
    check(fb == {0}, f"SwimmingFlag stays 0 in a B jump ({fb})")
    # a B jump with C held, B tapped again after the apex: a swim stroke in the air
    vels, flags = [], set()
    for i in range(71):
        emu.frame("c|b" if i < 38 or i == 41 else "c")   # (B held: a full-height jump)
        if mario()["status"] & 2:
            flags.add(ram("SwimmingFlag"))
        vels.append(mario()["y_vel"])
    check(1 in flags, f"holding C in the air sets SwimmingFlag ({flags})")
    check(min(vels[39:]) <= SWIM_VEL + 0x20 and ram("Mario_SwimForces") != 0,
          f"holding C, a B press mid-air is a swim stroke (y_vel {min(vels[39:])}, expected ~{SWIM_VEL})")
    check(ram("VerticalForceDown") == 0x0A, f"swim falling force after the stroke ({ram('VerticalForceDown'):#x})")
    emu.frames(2)                                          # C released, still airborne
    m = mario()                                            # (RAM shows the previous frame's logic)
    check(m["status"] & 2 and ram("SwimmingFlag") == 0 and ram("VerticalForceDown") == 0x70
          and ram("VerticalForce") == 0x70,
          f"releasing C: no longer swimming, normal falling force (flag {ram('SwimmingFlag')}, "
          f"forces {ram('VerticalForce'):#x}/{ram('VerticalForceDown'):#x})")
    settle()

    # ---------------- ARZ1: water ----------------
    warp(0x0F00)
    invulnerable()
    m = settle()
    print(f"  ARZ1 start: Mario at {m['x']:#x},{m['y']:#x}, water {emu.r16(WL1):#x}")
    floor_x, floor_y = m["x"], m["y"]
    wl = floor_y - 0x60
    set_water(wl)
    emu.frames(3)
    check(mario()["status"] & 0x40 and ram("SwimmingFlag") == 1 and ram("VerticalForceDown") == 0x0A,
          f"in water: underwater, SwimmingFlag {ram('SwimmingFlag')}, falling force {ram('VerticalForceDown'):#x}")
    emu.screenshot(os.path.join(OUT, "underwater.png"))

    # water walk: SMB1's water maximum speed, run or not
    sp = []
    for i in range(70):
        emu.frame("right|a")
        sp.append(s16(emu.r16(S("Player_X_Speed"))))
    check(max(sp) == 0x10, f"water walk/run top speed $10 (max {max(sp):#x})")
    emu.frames(40, "left|a"); settle()

    # one stroke from the floor, with the swim/stomp sound
    vels, sound = [], []
    emu.frame("b")
    for i in range(40):
        m = mario()
        vels.append(m["y_vel"]); sound.append(psg3())
        emu.frame("b" if i < 5 else None)
    check(emu.r16(S("Mario_JumpSpeed")) in (0xFE80, 0x0080) and min(vels) <= SWIM_VEL + 0x10,
          f"swim stroke from the floor: SMB1 swim speed (min y_vel {min(vels)}, expected ~{SWIM_VEL})")
    played = [p for p in sound if p != "off"]
    expected = smps_timeline(os.path.join(S2, "sound", "sfx", "A9 - Mario Swim Stomp.asm"))
    check(runs(played)[:len(runs(expected))] == runs(expected),
          f"swim/stomp sound plays (PSG3 {[hex(p) if p else p for p in runs(played)][:8]}...)")

    # B strokes every 16 frames, then mashing: never out of the water
    out_of_water, min_top, forces = False, 0xFFFF, set()
    for i in range(400):
        mash = i >= 200
        emu.frame("b" if (i % 2 == 0 if mash else i % 16 < 2) else None)
        m = mario()
        if not m["status"] & 0x40 or m["y"] <= emu.r16(WL1):
            out_of_water = True
        min_top = min(min_top, box_top(m) - wl)
        forces.add(ram("VerticalForce"))
        if i == 120:
            emu.screenshot(os.path.join(OUT, "surface.png"))
    check(out_of_water, "a press at the surface jumps out of the water (user change 2026-10-10: not SMB1's clamp)")
    check(min_top < SURF and 0x18 in forces,
          f"Mario reaches the surface line (box top {min_top:+d} px from the water level) and its $18 force applies")

    # fireballs underwater
    emu.w16(S("Ring_count"), 30)
    for _ in range(250):
        emu.frame()
        if ram("PlayerStatus") == 2 and not ram("Mario_PowerTask"):
            break
    settle()
    emu.frames(1, "a")
    seen = []
    for i in range(12):
        emu.frame()
        seen += [emu.r16(s + 8) for s in objects(S("ObjID_MarioFireball"))]
    check(len(set(seen)) > 5, f"fireballs fly underwater ({len(set(seen))} positions)")
    emu.frames(60)

    # holding C, B strokes carry Mario out of the water and on into the air
    left, rose, airflag = False, 0, set()
    for i in range(300):
        emu.frame("c|b" if i % 16 < 2 else "c")
        m = mario()
        if not m["status"] & 0x40 and m["status"] & 2:
            left = True
            airflag.add(ram("SwimmingFlag"))
            rose = max(rose, wl - m["y"])
        if rose > 0x40:
            emu.screenshot(os.path.join(OUT, "air_swim.png"))
            break
    check(left and rose > 0x40 and airflag == {1},
          f"holding C, Mario swims out of the water and on up ({rose} px above it, SwimmingFlag {airflag})")
    # releasing C: falls back in; entering the water gives the swim falling force again
    falling = []
    for i in range(200):
        emu.frame()
        m = mario()
        if not m["status"] & 0x40:
            falling.append((ram("SwimmingFlag"), ram("VerticalForceDown")))
        else:
            break
    emu.frames(2)                                          # Mario_SwimCheck sees the entry next frame
    check(falling and all(f == (0, 0x70) for f in falling[1:]),
          f"C released above the water: falls with the normal force ({set(falling)})")
    check(mario()["status"] & 0x40 and ram("VerticalForceDown") == 0x0A,
          f"back in the water: swim falling force ({ram('VerticalForceDown'):#x})")
    settle()

    # underwater, falling onto a badnik hurts (no stomping in water)
    m = settle()
    emu.w16(S("Ring_count"), 5)
    emu.write(MC + 0x30, b"\x00\x00")
    bz = spawn(0x4B, m["x"], m["y"] - 0x30)
    emu.frames(2)
    emu.w8(bz + 0x20, 0x0A)
    emu.w16(MC + 0xC, m["y"] - 0x50)
    emu.w8(MC + 0x22, emu.r8(MC + 0x22) | 2)
    emu.w16(MC + 0x12, 0x200); emu.w16(S("Mario_LastYVel"), 0x200)
    hurt, alive = False, True
    for i in range(30):
        emu.w16(bz + 0x8, mario()["x"])
        emu.frame()
        if mario()["routine"] == 4:
            hurt = True
        if emu.r8(bz) != 0x4B:
            alive = False
        if hurt:
            break
    check(hurt and alive, f"underwater, landing on a badnik hurts Mario (hurt {hurt}, badnik survives {alive})")
    emu.write(bz, bytes(0x40))
    invulnerable()
    settle(300)

    # drowning is disabled (user decision 2026-10-10): Mario_Water refills the air
    emu.w16(MC + 8, floor_x); emu.w16(MC + 0xC, floor_y)
    settle()
    emu.w8(MC + 0x28, 0)                                   # no air left
    drowned = False
    for i in range(400):
        emu.frame()
        m = mario()
        if m["anim"] == S("AniIDSonAni_Drown") or m["routine"] >= 6:
            drowned = True
            break
    check(not drowned and emu.r8(MC + 0x28) == 30,
          f"no drowning: the air is refilled (drowned {drowned}, air {emu.r8(MC + 0x28)})")

    # ---------------- EHZ1: starpost (H11), signpost and results (H16) ----------------
    emu.w16(S("Current_ZoneAndAct"), 0)
    emu.w8(S("Level_Inactive_flag"), 1)                    # restart into EHZ1
    for _ in range(120):
        emu.frame()
        if gm() != 0x0C:
            break
    wait_level()
    invulnerable()
    teleport(0x2240, 0x140)                               # just before EHZ1's third starpost
    print(f"  starpost test: Mario at {mario()['x']:#x},{mario()['y']:#x}, camera "
          f"{emu.r16(S('Camera_X_pos')):#x}, starposts {[hex(emu.r16(s + 8)) for s in objects(0x79)]}")
    emu.w16(S("Ring_count"), 50)
    for _ in range(300):                                   # grow, then fire flower (world paused)
        emu.frame()
        if ram("PlayerStatus") == 2 and not ram("Mario_PowerTask"):
            break
    emu.frames(40, "right")
    emu.frames(20)
    stars = [s for s in objects(0x79) if emu.r8(s + 0x24) == 8]
    check(ram("Last_star_pole_hit") == 3 and not stars,
          f"H11: starpost activated with 50 rings (hit {ram('Last_star_pole_hit')}), no Special Stage stars ({len(stars)})")

    teleport(0x29C0, 0x2A0)
    sign = None
    for i in range(400):
        emu.frame("right" if i < 60 else None)
        o = objects(0x0D)
        if o:
            sign = o[0]
        if sign and emu.r8(sign + 0x1C) == 3 and emu.r8(sign + 0x1A) == 0:
            emu.frames(20)
            break
    check(sign is not None and emu.r8(sign + 0x1C) == 3 and emu.r8(sign + 0x1A) == 0,
          "H16: the signpost ends on frame 0 (Mario's panel)")
    emu.screenshot(os.path.join(OUT, "signpost.png"))
    name_obj = None
    for i in range(600):
        emu.frame()
        for s in objects(S("ObjID_Results")):
            if emu.r8(s + 0x24) in (2, 0xA) and emu.r32(s + 4) == S("MapUnc_MarioEOLName"):
                name_obj = s
        if name_obj and emu.r8(name_obj + 0x24) == 0xA:
            break
    check(name_obj is not None, "H16: results name object uses MapUnc_MarioEOLName (\"MARIO GOT\")")
    emu.frames(30)
    emu.screenshot(os.path.join(OUT, "results.png"))
finally:
    emu.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
