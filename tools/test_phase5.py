#!/usr/bin/env python3
"""
test_phase5.py - Mario's combat and power-ups (Phase 5) in BlastEm, EHZ1.

    python -I tools/test_phase5.py [rom]

Mario is teleported next to real objects (Buzzers, a monitor; a second
monitor is spawned) and given a velocity, then the outcome is checked:
grow / fire flower sequences, crouch radius, monitors (side, below, stomp),
badnik stomp / side hit, ring loss + shrink, boss rule (a Buzzer given boss
hit points: any airborne touch hits it, a touch from the ground hurts Mario),
star, shield, speed shoes, death at 0
rings. Screenshots go to tools/out/phase5/. Exit code 1 on any failure.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blastem_gdb import BlastEm, S2, HERE, boot_to_level  # noqa: E402

OUT = os.path.join(HERE, "out", "phase5")
os.makedirs(OUT, exist_ok=True)
rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
emu = BlastEm(rom)
S = emu.sym
MC = S("MainCharacter")
DYN, DYN_END = S("Dynamic_Object_RAM"), S("Dynamic_Object_RAM_End")
RINGS = S("Ring_count")
V = {n: S(n) for n in ["PlayerSize", "PlayerStatus", "PlayerChangeSizeFlag", "TimerControl",
                       "Mario_PowerTask", "Mario_ArtBank", "CrouchingFlag", "Player_X_Speed",
                       "Mario_LastYVel", "Mario_LastXHand", "Player_State"]}
YSCALE = S("Mario_YScale")
BIG_R, SMALL_R = S("Mario_BigYRadius"), S("Mario_SmallYRadius")
BOUNCE = (-0x300 * YSCALE) >> 8          # $FD00 scaled
HEADBUMP = (0x100 * YSCALE) >> 8         # $0100 scaled

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
    return dict(x=w(8), y=w(0xC), x_vel=s16(w(0x10)), y_vel=s16(w(0x12)), y_radius=b[0x16],
                frame=b[0x1A], anim=b[0x1C], status=b[0x22], routine=b[0x24], status2=b[0x2B],
                size=emu.r8(V["PlayerSize"]), power=emu.r8(V["PlayerStatus"]),
                flag=emu.r8(V["PlayerChangeSizeFlag"]), timer=emu.r8(V["TimerControl"]),
                task=emu.r8(V["Mario_PowerTask"]), bank=emu.r8(V["Mario_ArtBank"]),
                rings=emu.r16(RINGS), xspeed=emu.r16(V["Player_X_Speed"], signed=True))


def obj(slot):
    b = emu.read(slot, 0x40)
    return dict(id=b[0], x=int.from_bytes(b[8:10], "big"), y=int.from_bytes(b[0xC:0xE], "big"),
                coll=b[0x20], prop=b[0x21], routine=b[0x24])


def find(objid, lo=0, hi=0xFFFF):
    for slot in range(DYN, DYN_END, 0x40):
        o = obj(slot)
        if o["id"] == objid and lo <= o["x"] <= hi and o["coll"]:
            return slot
    return None


def spawn(objid, x, y, subtype=0):
    """Create an object in a free dynamic slot (as the level's object manager would)."""
    free = next(s for s in range(DYN, DYN_END, 0x40) if emu.r8(s) == 0)
    emu.write(free, bytes(0x40))
    emu.w8(free + 0x28, subtype)
    emu.w16(free + 0x08, x)
    emu.w16(free + 0x0C, y)
    emu.w8(free, objid)
    emu.frames(2)
    return free


def buzzer():
    """A Buzzer in open air, well above Mario's head (so it is on camera)."""
    m = mario()
    return spawn(0x4B, m["x"], m["y"] - 0x50)


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


def settle(n=200):
    """Wait until Mario is back in control and on the ground."""
    for _ in range(n):
        emu.frame()
        m = mario()
        if m["routine"] == 2 and not (m["status"] & 2) and not m["task"] and not m["flag"]:
            return m
    return mario()


def set_rings(n):
    emu.w16(RINGS, n)


def grow_to(n_rings, label):
    """Set the ring count and follow the power-up sequence while right is held."""
    set_rings(n_rings)
    emu.frames(2, "right")
    m0 = mario()
    xs, flag_at, banks, feet = set(), None, set(), set()
    for i in range(70):
        emu.frame("right")
        m = mario()
        if m["task"]:
            xs.add(m["x"])
        banks.add(m["bank"])
        feet.add(m["y"] + m["y_radius"])
        if m["flag"] and flag_at is None:
            flag_at = i
    return m0, mario(), xs, flag_at, banks, feet


try:
    boot_to_level(emu)
    emu.frames(20)
    invuln(True)

    # ---- small -> super at 10 rings -------------------------------------------------
    m0, m, xs, flag_at, banks, feet = grow_to(10, "super")
    check(m0["task"] == 9, f"10 rings starts PlayerChangeSize (task {m0['task']:#x})")
    check(len(xs) == 1, f"Mario halted while growing (x values {sorted(map(hex, xs))})")
    check(flag_at is not None and 4 <= flag_at <= 8, f"grow animation starts at TimerControl $F8 (frame {flag_at})")
    check(len(feet) == 1, f"feet stay put while growing (feet y {sorted(map(hex, feet))})")
    check(m["power"] == 1 and m["size"] == 0 and m["y_radius"] == BIG_R and m["task"] == 0,
          f"super Mario: status {m['power']} size {m['size']} radius {m['y_radius']:#x} task {m['task']}")
    emu.frames(10)
    emu.screenshot(os.path.join(OUT, "super.png"))
    x_before = mario()["x"]
    emu.frames(10, "right")
    check(mario()["x"] != x_before, "Mario moves again after growing")
    emu.frames(30, "left")
    settle()

    # ---- super -> fiery at 30 rings -----------------------------------------------
    m0, m, xs, flag_at, banks, feet = grow_to(30, "fiery")
    check(m0["task"] == 0xC, f"30 rings starts PlayerFireFlower (task {m0['task']:#x})")
    check(len(xs) == 1, "Mario halted during the fire flower flicker")
    check(banks == {0, 1}, f"colour banks flicker ({sorted(banks)})")
    check(m["power"] == 2 and m["bank"] == 1 and m["task"] == 0 and m["size"] == 0,
          f"fiery Mario: status {m['power']} bank {m['bank']} task {m['task']}")
    emu.frames(10)
    emu.screenshot(os.path.join(OUT, "fiery.png"))

    # ---- crouch uses the small radius, feet kept ---------------------------------------
    m0 = settle()
    emu.frames(6, "down")
    m = mario()
    check(m["y_radius"] == SMALL_R and m["y"] + m["y_radius"] == m0["y"] + m0["y_radius"],
          f"crouching: radius {m['y_radius']:#x}, feet {m['y'] + m['y_radius']:#x} vs {m0['y'] + m0['y_radius']:#x}")
    emu.frames(6)
    m = mario()
    check(m["y_radius"] == BIG_R, f"standing again: radius {m['y_radius']:#x}")

    # over to the objects: drop in just left of the monitor, let the camera catch up
    place(0x390, 0x220, 0)
    settle(120)
    emu.frames(30)

    # ---- monitor: side, below, stomp -------------------------------------------------
    mon = find(0x26)
    if mon is None:
        print("  Mario at", hex(mario()["x"]), hex(mario()["y"]))
        for s in range(DYN, DYN_END, 0x40):
            o = obj(s)
            if o["id"]:
                print("   ", {k: hex(v) for k, v in o.items()})
    check(mon is not None, "found the EHZ1 monitor")
    o = obj(mon)
    place(o["x"] - 0x30, o["y"] - 0x20)
    settle(60)
    emu.frames(40, "right")
    m, o2 = mario(), obj(mon)
    check(o2["routine"] == 2 and m["x"] < o["x"] - 0x10,
          f"walking into a monitor: solid, not broken (Mario x {m['x']:#x}, monitor {o['x']:#x}, routine {o2['routine']})")
    emu.frames(20, "left")
    settle()
    # lift it so Mario can jump into it from below
    emu.w16(mon + 0xC, o["y"] - 0x48)
    place(o["x"], o["y"] - 0x10 + 2, 0, air=True)
    settle(60)
    hit_vel, item = None, False
    for i in range(40):
        emu.frame("b" if i < 20 else None)
        if obj(mon)["routine"] != 2 and hit_vel is None:
            hit_vel = mario()["y_vel"]
        for s in range(DYN, DYN_END, 0x40):
            if emu.r8(s) == 0x2E and emu.r16(s + 0x3E) == MC & 0xFFFF:   # Obj2E, parent = Mario
                item = True
    check(hit_vel == HEADBUMP, f"monitor broken from below, jump nullified (y_vel {hit_vel}, expected {HEADBUMP})")
    check(item, "monitor contents (Obj2E) given to Mario")
    emu.frames(60)
    emu.screenshot(os.path.join(OUT, "monitor_below.png"))
    settle()
    # spawn a second monitor on the ground and stomp it
    free = next(s for s in range(DYN, DYN_END, 0x40) if emu.r8(s) == 0)
    emu.write(free, bytes(0x40))
    emu.w8(free, 0x26)
    emu.w8(free + 0x28, 6)                                 # subtype: ring monitor
    emu.w16(free + 0x08, o["x"] - 0x40)
    emu.w16(free + 0x0C, o["y"])
    emu.frames(2)
    o = obj(free)
    place(o["x"], o["y"] - 0x40, 0x200)
    hit_vel = None
    for i in range(30):
        emu.frame()
        if obj(free)["routine"] != 2 and hit_vel is None:
            hit_vel = mario()["y_vel"]
    check(hit_vel == BOUNCE, f"monitor stomped, Mario bounces (y_vel {hit_vel}, expected {BOUNCE})")
    settle()

    # ---- badnik stomp ---------------------------------------------------------------
    place(0x2E0, 0x240, 0)
    settle(120)
    bz = buzzer()
    if bz is None:
        print("  Mario at", hex(mario()["x"]), hex(mario()["y"]))
        for s in range(DYN, DYN_END, 0x40):
            o = obj(s)
            if o["id"]:
                print("   ", {k: hex(v) for k, v in o.items()})
    check(bz is not None, "found a Buzzer")
    b = obj(bz)
    place(b["x"], b["y"] - 0x30, 0x200)
    hit_vel, m_routine = None, None
    for i in range(30):
        emu.frame()
        if obj(bz)["id"] != 0x4B and hit_vel is None:
            hit_vel, m_routine = mario()["y_vel"], mario()["routine"]
    check(hit_vel == BOUNCE and m_routine == 2,
          f"Buzzer stomped: Mario bounces (y_vel {hit_vel}, expected {BOUNCE}), not hurt (routine {m_routine})")
    emu.screenshot(os.path.join(OUT, "stomp.png"))
    settle()

    # ---- the other EHZ badniks --------------------------------------------------------
    for objid, name in [(0x9D, "Coconuts"), (0x5C, "Masher")]:
        m = mario()
        s = spawn(objid, m["x"], m["y"] - 0x50)
        o = obj(s)
        place(o["x"], o["y"] - 0x30, 0x200)
        hit_vel, rt = None, None
        for i in range(30):
            emu.frame()
            if obj(s)["id"] != objid and hit_vel is None:
                hit_vel, rt = mario()["y_vel"], mario()["routine"]
        check(hit_vel == BOUNCE and rt == 2, f"{name} stomped (y_vel {hit_vel}, routine {rt})")
        settle()

    # ---- hurt-class objects (spikes, projectiles: collision $80+) always hurt ------------
    set_rings(5)
    s = buzzer()
    emu.w8(s + 0x20, 0x8A)
    o = obj(s)
    invuln(False)
    place(o["x"], o["y"] - 0x30, 0x200)
    hurt = False
    for i in range(30):
        emu.frame()
        emu.w8(s + 0x20, 0x8A)                              # (the Buzzer resets it)
        if mario()["routine"] == 4:
            hurt = True
            break
    check(hurt and obj(s)["id"] == 0x4B, "falling onto a hurt-class object hurts Mario, no stomp")
    settle()
    invuln(True)
    emu.frames(130)                                         # let him pick up / lose the scattered rings
    emu.w16(RINGS, 0)

    # ---- boss rule: a Buzzer with boss hit points ---------------------------------------
    bz = buzzer()
    emu.w8(bz + 0x21, 2)                                    # collision_property = 2 hits
    set_rings(5)
    b = obj(bz)
    invuln(False)
    place(b["x"], b["y"] + 0x20, -0x600)                    # rising into it (airborne)
    hit = None
    for i in range(20):
        emu.frame()
        if obj(bz)["prop"] != 2 and hit is None:
            hit = mario()
    check(hit is not None and hit["routine"] == 2,
          f"rising into a boss hits it (routine {hit and hit['routine']}, boss hits left {obj(bz)['prop']})")
    settle()
    invuln(False)
    emu.write(bz, bytes(0x40))                              # (the hit bounced Mario elsewhere:
    bz = buzzer()                                           #  a fresh boss above his head)
    emu.w8(bz + 0x21, 1)
    b = obj(bz)
    place(b["x"], b["y"] - 0x30, 0x200)                     # falling onto it
    hit = None
    for i in range(30):
        emu.frame()
        if os.environ.get("P5DEBUG"):
            mm, o = mario(), obj(bz)
            print(f"   f{i} M x={mm['x']:#x} y={mm['y']:#x} yv={mm['y_vel']} rt={mm['routine']} st={mm['status']:#x} "
                  f"| B id={o['id']:#x} x={o['x']:#x} y={o['y']:#x} coll={o['coll']:#x} prop={o['prop']}")
        if obj(bz)["prop"] != 1 and hit is None:
            hit = mario()
    check(hit is not None and hit["routine"] == 2 and hit["y_vel"] < 0,
          f"falling onto a boss hits it, Mario bounces up (y_vel {hit and hit['y_vel']}, boss hits left {obj(bz)['prop']})")
    m = settle()
    invuln(False)
    emu.write(bz, bytes(0x40))
    bz = buzzer()
    emu.w8(bz + 0x21, 2)                                    # boss hit points
    emu.w8(bz + 0x20, 0x0A)
    emu.w16(bz + 0x08, m["x"] + 0x10)                       # bring it down beside Mario on the ground
    emu.w16(bz + 0x0C, m["y"])
    hurt = False
    for i in range(10):
        emu.frame()
        if mario()["routine"] == 4:
            hurt = True
            break
    check(hurt and obj(bz)["prop"] == 2, f"touching a boss from the ground hurts Mario (hurt {hurt}, boss hits left {obj(bz)['prop']})")
    settle()

    # ---- side hit while fiery: rings scattered, shrink ----------------------------------
    m0, m, *_ = grow_to(30, "regrow")
    settle()
    while mario()["power"] != 2:
        m0, m, *_ = grow_to(30, "regrow")
        settle()
    check(mario()["power"] == 2, "fiery again for the hit test")
    bz = buzzer()
    b = obj(bz)
    invuln(False)
    place(b["x"] - 0x10, b["y"], 0)
    shrink_at, hit, after_shrink = None, None, None
    for i in range(140):
        emu.frame()
        m = mario()
        if i < 40 and os.environ.get("P5DEBUG"):
            print(f"   f{i} rt={m['routine']} rings={m['rings']} pow={m['power']} size={m['size']} task={m['task']:#x} "
                  f"tc={m['timer']:#x} flag={m['flag']} y={m['y']:#x} yv={m['y_vel']} st={m['status']:#x}")
        if m["routine"] == 4 and hit is None:
            hit = m
        if m["flag"] and shrink_at is None and hit:
            shrink_at = i
            emu.screenshot(os.path.join(OUT, "shrinking.png"))
        if shrink_at is not None and not m["flag"] and after_shrink is None:
            emu.frame()
            after_shrink = mario()
    check(hit is not None and hit["rings"] == 0 and hit["power"] == 0 and hit["bank"] == 0 and hit["task"] == 0xA,
          f"side hit: knockback, rings lost, status small, normal colours, injury task "
          f"({hit and (hit['rings'], hit['power'], hit['bank'], hit['task'])})")
    check(shrink_at is not None and hit is not None and 14 <= shrink_at <= 17,
          f"shrink animation starts at TimerControl $F0 (frame {shrink_at})")
    check(after_shrink is not None and after_shrink["size"] == 1 and after_shrink["y_radius"] == SMALL_R,
          f"after the shrink: size {after_shrink and after_shrink['size']}, radius {after_shrink and hex(after_shrink['y_radius'])}")
    settle()

    # ---- star: touching kills, no bounce, no hurt -----------------------------------------
    invuln(True)
    emu.w8(MC + 0x2B, emu.r8(MC + 0x2B) | 2)
    emu.w16(MC + 0x32, 300)
    bz = buzzer()
    b = obj(bz)
    bid = b["id"]
    invuln(False)
    place(b["x"] - 0x10, b["y"], 0)
    killed = None
    for i in range(20):
        emu.frame()
        if obj(bz)["id"] != bid and killed is None:
            killed = mario()
    check(killed is not None and killed["routine"] == 2 and killed["y_vel"] >= 0,
          f"star Mario kills on touch without a bounce ({killed and (killed['routine'], killed['y_vel'])})")
    emu.w8(MC + 0x2B, emu.r8(MC + 0x2B) & ~2)
    emu.w16(MC + 0x32, 0)
    settle()

    # ---- shield: absorbs the hit, keeps rings and power ----------------------------------
    m0, m, *_ = grow_to(15, "shield super")
    settle()
    set_rings(15)
    power0 = mario()["power"]
    emu.w8(MC + 0x2B, emu.r8(MC + 0x2B) | 1)
    target = buzzer()
    t = obj(target)
    invuln(False)
    place(t["x"] - 0x10, t["y"], 0)
    for i in range(20):
        emu.frame()
        if mario()["routine"] == 4:
            break
    m = mario()
    check(m["routine"] == 4 and not (m["status2"] & 1) and m["rings"] >= 15 and m["power"] == power0 >= 1,
          f"shield absorbs the hit (routine {m['routine']}, shield {m['status2'] & 1}, rings {m['rings']}, "
          f"status {power0} -> {m['power']})")
    m = settle()
    check(m["power"] == power0 and m["size"] == 0, "still powered up after the shield hit")

    # ---- speed shoes: doubled top speed --------------------------------------------------
    invuln(True)
    emu.w8(MC + 0x2B, emu.r8(MC + 0x2B) | 4)
    emu.w16(MC + 0x34, 600)
    place(0x100, mario()["y"] - 0x40, 0)
    settle(60)
    top = 0
    for i in range(80):
        emu.frame("right|a")
        top = max(top, mario()["xspeed"])
    check(top >= 0x50, f"speed shoes: top speed {top:#x} (normal run $28, doubled $50)")
    emu.w8(MC + 0x2B, emu.r8(MC + 0x2B) & ~4)
    emu.w16(MC + 0x34, 0)
    emu.frames(60, "left")
    settle()

    # ---- 0 rings, small: dies ----------------------------------------------------------
    m0 = mario()
    if m0["power"]:
        # get small first: one hit with no rings shrinks a big Mario (SMB1 rule)
        set_rings(0)
        t = obj(buzzer())
        invuln(False)
        place(t["x"] - 0x10, t["y"], 0)
        emu.frames(10)
        m = settle()
        check(m["routine"] == 2 and m["power"] == 0, f"big Mario with 0 rings shrinks instead of dying (routine {m['routine']}, status {m['power']})")
    set_rings(0)
    invuln(False)
    t = obj(buzzer())
    place(t["x"] - 0x10, t["y"], 0)
    dead = False
    for i in range(30):
        emu.frame()
        if mario()["routine"] == 6:
            dead = True
            break
    check(dead, "small Mario with 0 rings dies")
    emu.frames(20)
    emu.screenshot(os.path.join(OUT, "death.png"))
finally:
    emu.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
