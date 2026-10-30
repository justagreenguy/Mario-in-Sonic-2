#!/usr/bin/env python3
"""
test_phase9.py - hard mode (MARIO MODE, Difficulty_option 1) in BlastEm, EHZ1.

    python -I tools/test_phase9.py [rom]

Boots through the options menu's DIFFICULTY box, then checks each hard-mode
rule with Buzzers spawned next to Mario (as test_phase5.py does):
  7  a speed shoes monitor shows and gives 10 rings
  2  a hit while big: rings simply lost (no LostRings object), shrink
  3  no knockback: Mario stays in Control, halted until the shrink is over,
     the world paused until TimerControl $C8
  4  SMB1 invincibility: 168 frames, halted with the timers, blinking
  1  small Mario dies with 25 rings (and with 5); a shield still absorbs the hit
  5  a touch 12 px above a badnik (not falling) hurts instead of stomping
  8  rising into a boss hurts; falling onto it hits it
  6  SMB1 death: frozen 15 frames, Y speed $FC, SMB1 gravity, no x speed
A shield is used as a cheap "was Mario hurt?" detector (it absorbs the hit and
is gone). Screenshots go to tools/out/phase9/. Exit code 1 on any failure.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blastem_gdb import BlastEm, S2, HERE, boot_to_level  # noqa: E402

OUT = os.path.join(HERE, "out", "phase9")
os.makedirs(OUT, exist_ok=True)
rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
emu = BlastEm(rom)
S = emu.sym
MC = S("MainCharacter")
DYN, DYN_END = S("Dynamic_Object_RAM"), S("Dynamic_Object_RAM_End")
RINGS = S("Ring_count")
V = {n: S(n) for n in ["PlayerSize", "PlayerStatus", "PlayerChangeSizeFlag", "TimerControl",
                       "Mario_PowerTask", "Mario_HardMode", "Player_X_Speed", "Mario_LastYVel",
                       "Mario_LastXHand", "Player_State", "Difficulty_option", "Life_count"]}
YSCALE = S("Mario_YScale")
INJURY = S("Mario_InjuryFrames")
TOUCH_SIZES = S("Touch_Sizes")

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
    return dict(id=b[0], x=w(8), y=w(0xC), x_vel=s16(w(0x10)), y_vel=s16(w(0x12)), y_radius=b[0x16],
                status=b[0x22], routine=b[0x24], status2=b[0x2B], invuln=w(0x30),
                size=emu.r8(V["PlayerSize"]), power=emu.r8(V["PlayerStatus"]),
                flag=emu.r8(V["PlayerChangeSizeFlag"]), timer=emu.r8(V["TimerControl"]),
                task=emu.r8(V["Mario_PowerTask"]), rings=emu.r16(RINGS))


def obj(slot):
    b = emu.read(slot, 0x40)
    return dict(id=b[0], x=int.from_bytes(b[8:10], "big"), y=int.from_bytes(b[0xC:0xE], "big"),
                coll=b[0x20], prop=b[0x21], anim=b[0x1C], routine=b[0x24])


def spawn(objid, x, y, subtype=0):
    free = next(s for s in range(DYN, DYN_END, 0x40) if emu.r8(s) == 0)
    emu.write(free, bytes(0x40))
    emu.w8(free + 0x28, subtype)
    emu.w16(free + 0x08, x)
    emu.w16(free + 0x0C, y)
    emu.w8(free, objid)
    emu.frames(2)
    return free


def buzzer():
    m = mario()
    return spawn(0x4B, m["x"], m["y"] - 0x50)


def count(objid):
    return sum(1 for s in range(DYN, DYN_END, 0x40) if emu.r8(s) == objid)


def place(x, y, yv=0, air=True):
    emu.w16(MC + 0x08, x); emu.w16(MC + 0x0A, 0)
    emu.w16(MC + 0x0C, y); emu.w16(MC + 0x0E, 0)
    emu.w16(MC + 0x10, 0); emu.w16(MC + 0x12, yv & 0xFFFF); emu.w16(MC + 0x14, 0)
    emu.w8(MC + 0x26, 0)
    emu.w8(MC + 0x22, (emu.r8(MC + 0x22) & 1) | (2 if air else 0))
    emu.w16(V["Mario_LastYVel"], yv & 0xFFFF)
    emu.w16(V["Mario_LastXHand"], 0)
    emu.w16(V["Player_X_Speed"], 0)
    emu.w8(V["Player_State"], 2 if air else 0)


def invuln(on):
    emu.w16(MC + 0x30, 0x7FFF if on else 0)


def shield(on):
    emu.w8(MC + 0x2B, (emu.r8(MC + 0x2B) & ~1) | (1 if on else 0))


def settle(n=300):
    for _ in range(n):
        emu.frame()
        m = mario()
        if m["routine"] == 2 and not (m["status"] & 2) and not m["task"] and not m["flag"]:
            return m
    return mario()


def wait_level_restart():
    for _ in range(900):
        emu.frame()
        m = mario()
        if m["id"] == 0xD0 and m["routine"] == 2 and emu.r8(S("Game_Mode")) == 0x0C:
            break
    emu.frames(200)                                       # title card


def drawn():
    """1 if any hardware sprite this frame uses Mario's tiles ($780-$79A)."""
    tbl = emu.read(S("Sprite_Table"), 80 * 8)
    for k in range(min(80, emu.r8(S("Sprite_count")))):
        tile = int.from_bytes(tbl[k * 8 + 4:k * 8 + 6], "big") & 0x7FF
        if 0x780 <= tile < 0x79B:
            return 1
    return 0


def touch_size(slot):
    i = obj(slot)["coll"] & 0x3F
    return emu.r8(TOUCH_SIZES + 2 * i), emu.r8(TOUCH_SIZES + 2 * i + 1)


try:
    boot_to_level(emu, difficulty=1)
    emu.frames(20)
    emu.w8(V["Life_count"], 9)
    check(emu.r16(V["Difficulty_option"]) == 1, "Difficulty_option = 1 (MARIO MODE)")
    check(emu.r8(V["Mario_HardMode"]) == 0xFF, f"Mario_HardMode set ({emu.r8(V['Mario_HardMode']):#x})")
    invuln(True)

    # ---- rule 7: speed shoes monitor -> 10 rings ---------------------------------------
    m = settle()
    mon = spawn(0x26, m["x"] + 0x40, m["y"] + m["y_radius"] - 0x0F, subtype=5)
    emu.frames(2)
    check(obj(mon)["anim"] == 4, f"speed shoes monitor shows the ring icon (anim {obj(mon)['anim']})")
    o = obj(mon)
    place(o["x"], o["y"] - 0x40, 0x200)
    rings0 = mario()["rings"]
    for _ in range(80):
        emu.frame()
    m = mario()
    check(m["rings"] == rings0 + 10 and not (m["status2"] & 4),
          f"it gives 10 rings, no shoes (rings {rings0} -> {m['rings']}, status2 {m['status2']:#x})")
    m = settle()
    check(m["power"] == 1, f"10 rings -> super Mario (status {m['power']})")

    # ---- rules 2, 3, 4: hit while big -------------------------------------------------------
    emu.w16(RINGS, 15)
    bz = buzzer()
    b = obj(bz)
    invuln(False)
    lost0 = count(0x37)
    place(b["x"] - 0x10, b["y"], 0)
    hit, xs, frozen_until, lost, routines, inv_at_end, end_frame = None, set(), None, 0, set(), None, None
    for i in range(140):
        emu.frame("right")
        m = mario()
        routines.add(m["routine"])
        lost = max(lost, count(0x37) - lost0)
        if hit is None and m["task"] == 0xA:
            hit, hit_frame = m, i
        if hit and m["task"] == 0xA and (m["timer"] >= 0xF0 or m["flag"]):
            xs.add((m["x"], m["y"]))
        if hit and frozen_until is None and m["timer"] < 0xF0 and not m["flag"] and m["task"] == 0xA:
            frozen_until = m
        if hit and m["task"] == 0 and end_frame is None:
            end_frame, inv_at_end = i, m["invuln"]
        if hit and i == hit_frame + 20:
            emu.screenshot(os.path.join(OUT, "hit_shrinking.png"))
    check(hit is not None and hit["rings"] == 0 and hit["power"] == 0,
          f"hit while big: rings lost, status small ({hit and (hit['rings'], hit['power'])})")
    check(lost == 0, f"no ring scatter (LostRings objects: {lost})")
    check(routines == {2}, f"no knockback: routine stays Control ({sorted(routines)})")
    check(len(xs) == 1, f"halted (right held) until the shrink is over ({len(xs)} positions)")
    check(frozen_until is not None and frozen_until["size"] == 1,
          f"control returns after the shrink, small (size {frozen_until and frozen_until['size']})")
    check(inv_at_end is not None and abs(inv_at_end - INJURY) <= 1,
          f"invincibility halted during the task ({inv_at_end} of {INJURY} left at its end)")
    # blink: the sprite is in the sprite table on alternate frames only
    seen = []
    for i in range(6):
        emu.frame()
        m = mario()
        seen.append(m["invuln"])
    check(seen[0] - seen[-1] == 5, f"invincibility counts down once per frame afterwards ({seen})")
    # blink: Mario_Display skips DisplaySprite on odd frames; look for his tiles
    # ($780-$79A, his DPLC slot) in the hardware sprite table BuildSprites made
    vis = []
    for i in range(8):
        emu.frame()
        vis.append(drawn())
    check(0 in vis and 1 in vis and all(vis[k] != vis[k + 1] for k in range(7)),
          f"blinks every other frame while invincible ({vis})")
    n = 0
    while mario()["invuln"] and n < 400:
        emu.frame(); n += 1
    vis = []
    for i in range(4):
        emu.frame()
        vis.append(drawn())
    check(vis == [1, 1, 1, 1], f"drawn every frame once the invincibility is over ({vis})")
    settle()

    # ---- rule 1 (shield first): small with 5 rings and a shield survives ---------------------
    m = mario()
    check(m["power"] == 0, "small again")
    emu.w16(RINGS, 5)
    shield(True)
    bz = buzzer()
    b = obj(bz)
    invuln(False)
    place(b["x"] - 0x10, b["y"], 0)
    for _ in range(10):
        emu.frame()
    m = mario()
    check(m["routine"] == 2 and not (m["status2"] & 1) and m["power"] == 0 and m["rings"] >= 5
          and m["invuln"] > INJURY - 15,
          f"shield absorbs the hit: alive, small, rings kept, invincible "
          f"(routine {m['routine']}, shield {m['status2'] & 1}, rings {m['rings']}, invuln {m['invuln']})")
    emu.write(bz, bytes(0x40))
    settle()

    # ---- rule 5: 12 px above a badnik but not falling: hurt -----------------------------------
    shield(True)
    bz = buzzer()
    b = obj(bz)
    w, h = touch_size(bz)
    m = mario()
    my = b["y"] - h - 2                                   # top + 12 just above the enemy's top
    invuln(False)
    place(b["x"], my, 0)
    first = None
    for _ in range(4):
        emu.frame()
        m = mario()
        if first is None and (not (m["status2"] & 1) or obj(bz)["id"] != 0x4B):
            first = (m["status2"] & 1, obj(bz)["id"])
    check(first == (0, 0x4B),
          f"touch 12 px above, not falling: hurt, no stomp (first touch: shield, enemy = {first})")
    emu.write(bz, bytes(0x40))
    settle()
    # ...and falling onto it is still a stomp
    bz = buzzer()
    b = obj(bz)
    invuln(False)
    shield(True)
    place(b["x"], b["y"] - 0x30, 0x200)
    for _ in range(20):
        emu.frame()
    m = mario()
    check(obj(bz)["id"] != 0x4B and m["status2"] & 1, "falling onto a badnik stomps it")
    settle()

    # ---- rule 8: bosses only while falling -----------------------------------------------------
    bz = buzzer()
    emu.w8(bz + 0x21, 2)
    b = obj(bz)
    invuln(False)
    shield(True)
    place(b["x"], b["y"] + 0x20, -0x600)                    # rising into it
    first = None
    for _ in range(12):
        emu.frame()
        m = mario()
        if first is None and (not (m["status2"] & 1) or obj(bz)["prop"] != 2):
            first = (m["status2"] & 1, obj(bz)["prop"])
    check(first == (0, 2), f"rising into a boss hurts Mario, no hit (first touch: shield, boss hits = {first})")
    emu.write(bz, bytes(0x40))
    settle()
    bz = buzzer()
    emu.w8(bz + 0x21, 2)
    b = obj(bz)
    invuln(False)
    shield(True)
    place(b["x"], b["y"] - 0x30, 0x200)                     # falling onto it
    hit = None
    for _ in range(30):
        emu.frame()
        if obj(bz)["prop"] != 2 and hit is None:
            hit = mario()
    check(hit is not None and hit["status2"] & 1,
          f"falling onto a boss hits it (boss hits left {obj(bz)['prop']}, shield kept {bool(hit and hit['status2'] & 1)})")
    emu.write(bz, bytes(0x40))
    settle()
    shield(False)

    # ---- rule 1: small Mario with 25 rings dies; rule 6: SMB1 death ------------------------
    # Small with 10+ rings: the window after an injury (the task runs, the world is
    # paused, Mario has control, no power-up until it ends).
    bz = buzzer()                                         # (spawned first: the task pauses the world)
    b = obj(bz)
    emu.w8(V["Mario_PowerTask"], 0xA)
    emu.w8(V["TimerControl"], 0xD8)
    emu.w16(RINGS, 25)
    invuln(False)
    place(b["x"] - 0x10, b["y"], 0)
    ys, yvs, xvs, dead_at = [], [], [], None
    for i in range(80):
        emu.frame()
        m = mario()
        if m["routine"] == 6 and dead_at is None:
            dead_at = i
        if dead_at is not None:
            ys.append(m["y"]); yvs.append(m["y_vel"]); xvs.append(m["x_vel"])
        if dead_at is not None and i == dead_at + 30:
            emu.screenshot(os.path.join(OUT, "death_hop.png"))
    check(dead_at is not None, "small Mario with 25 rings dies in one hit")
    if dead_at is not None:
        still = 0
        while still + 1 < len(ys) and ys[still + 1] == ys[0]:
            still += 1
        hop = (-0x400 * YSCALE) >> 8
        g = (0x70 * YSCALE) >> 8
        moving = [ys[k + 1] - ys[k] for k in range(still, min(still + 6, len(ys) - 1))]
        dv = [yvs[k + 1] - yvs[k] for k in range(still + 1, still + 6)]
        print(f"  death: frozen {still} frames, y steps {moving}, y_vel {yvs[still:still + 6]}")
        check(14 <= still <= 16, f"death: frozen about 15 frames ({still})")
        check(yvs[0] == hop and moving and moving[0] == hop >> 8,
              f"death hop: Y speed $FC scaled ({yvs[0]:#x} vs {hop & 0xFFFF:#x}), first step {moving[:1]}")
        check(all(d == g for d in dv), f"SMB1 gravity while dying ({dv}, expected {g})")
        check(all(v == 0 for v in xvs), "no horizontal speed while dying")
    wait_level_restart()
    check(emu.r8(V["Mario_HardMode"]) == 0xFF, "hard mode still set after the restart")

    # ---- rule 1: small with 5 rings dies -------------------------------------------------
    emu.frames(30)
    emu.w16(RINGS, 5)
    bz = buzzer()
    b = obj(bz)
    invuln(False)
    place(b["x"] - 0x10, b["y"], 0)
    dead = False
    for _ in range(15):
        emu.frame()
        m = mario()
        if os.environ.get("P9DEBUG"):
            o = obj(bz)
            print(f"   M x={m['x']:#x} y={m['y']:#x} rt={m['routine']} inv={m['invuln']} st={m['status']:#x} "
                  f"| B id={o['id']:#x} x={o['x']:#x} y={o['y']:#x} coll={o['coll']:#x}")
        if m["routine"] == 6:
            dead = True
            break
    check(dead, "small Mario with 5 rings dies in one hit")
finally:
    emu.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
