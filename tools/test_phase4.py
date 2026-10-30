#!/usr/bin/env python3
"""
test_phase4.py - Mario's animation (Phase 4) in BlastEm.

    python -I tools/test_phase4.py [rom]

1. Every frame in which Mario's own code drives the animation, the ROM's
   mapping_frame, render flips, PlayerAnimCtrl and PlayerAnimTimer are checked
   against an independent Python model of SMB1's ProcessPlayerAction /
   AnimationControl (main.asm:11955) plus the port's floor-angle rotation.
2. Scenarios: walk cadence vs speed, skid frame + S2 skid dust, crouch only
   when big, a run through Emerald Hill 1 (loops: all four orientations),
   forced-roll tumbling, hang / bubble scripts.
Screenshots go to tools/out/phase4/. Exit code 1 on any failure.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blastem_gdb import BlastEm, S2, HERE, boot_to_level  # noqa: E402

OUT = os.path.join(HERE, "out", "phase4")
os.makedirs(OUT, exist_ok=True)
rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
emu = BlastEm(rom)
S = emu.sym
MC = S("MainCharacter")
R = {n: S(n) for n in ["Player_State", "CrouchingFlag", "SwimmingFlag", "Player_X_Speed",
                       "Left_Right_Buttons", "Player_XSpeedAbsolute", "Player_MovingDir",
                       "PlayerFacingDir", "PlayerSize", "PlayerStatus", "PlayerAnimTimerSet",
                       "PlayerAnimCtrl", "PlayerAnimTimer", "PlayerChangeSizeFlag", "JumpSwimTimer",
                       "TimerControl"]}
GFXBASE = S("MarioFrame_GfxBase")
OFFS = [0x20, 0x28, 0xC8, 0x18, 0x00, 0x40, 0x50, 0x58, 0x80, 0x88, 0xB8, 0x78, 0x60, 0xA0, 0xB0, 0xB8]
ROT = {}
for row, name in [(0, "Big_Walk1"), (1, "Big_Walk2"), (2, "Big_Walk3"), (3, "Big_Skid"), (4, "Big_Jump"),
                  (10, "Big_Crouch"), (12, "Small_Walk1"), (13, "Small_Walk2"), (14, "Small_Walk3"),
                  (15, "Small_Skid"), (16, "Small_Jump"), (23, "Small_Stand"), (25, "Big_Stand")]:
    ROT[GFXBASE + row] = S(f"MarioFrame_{name}_Rot90")
FLIPS = [[0, 0, 3, 3], [1, 2, 2, 1]]           # [facing left][quarter]
SMB_ANIMS = {0, 1, 2, 3, 4, 5, 8, 0xD}          # MarioAniData entries that run MAnim_SMB

failures = []


def fail(msg):
    if len(failures) < 60:
        print("FAIL:", msg)
    failures.append(msg)


def state():
    sst = emu.read(MC, 0x40)
    st = {n: emu.r8(a) for n, a in R.items() if n != "Player_X_Speed"}
    st["Player_X_Speed"] = emu.r16(R["Player_X_Speed"], signed=True)
    st.update(frame=sst[0x1A], rflags=sst[1] & 3, anim=sst[0x1C], status=sst[0x22], angle=sst[0x26],
              routine=sst[0x24], inertia=int.from_bytes(sst[0x14:0x16], "big", signed=True),
              x=int.from_bytes(sst[8:10], "big"), y=int.from_bytes(sst[0xC:0xE], "big"),
              obj_control=sst[0x2A], anim_frame=sst[0x1B])
    return st


def quarter(angle):
    a = angle
    if 0 < a < 0x80:
        a -= 1
    return ((((-a) & 0xFF) + 0x1F) & 0xFF) >> 6


def model(before, after):
    """ProcessPlayerAction + AnimationControl + orientation. Returns
    (mapping_frame, flips, ctrl, timer) expected after this frame."""
    ctrl, timer = before["PlayerAnimCtrl"], before["PlayerAnimTimer"]
    if before["TimerControl"] <= 1:          # (Phase 5) TimerControl halts the frame timers
        timer = max(0, timer - 1)
    s = after
    adder = (lambda y: y + 8) if s["PlayerSize"] else (lambda y: y)

    def nonanim(y):
        return OFFS[adder(y)], 0, timer

    def animate(y):
        nonlocal ctrl, timer
        off = ctrl * 8 + OFFS[adder(y)]
        if timer == 0:
            timer = s["PlayerAnimTimerSet"]
            ctrl = ctrl + 1 if ctrl + 1 < 3 else 0
        return off, ctrl, timer

    ps = s["Player_State"]
    if ps == 2:
        off = ctrl * 8 + OFFS[adder(4)]
        res = (off, ctrl, timer)
    elif ps == 1:
        res = nonanim(6 if s["CrouchingFlag"] else 0)
    else:
        if s["CrouchingFlag"]:
            res = nonanim(6)
        elif s["Player_X_Speed"] == 0 and s["Left_Right_Buttons"] == 0:
            res = nonanim(2)
        elif s["Player_XSpeedAbsolute"] >= 9 and not (s["Player_MovingDir"] & s["PlayerFacingDir"]):
            res = nonanim(3)
        else:
            res = animate(4)
    off, ctrl, timer = res
    frame = GFXBASE + off // 8
    q = quarter(s["angle"])
    if q & 1:
        if frame in ROT:
            frame = ROT[frame]
        else:
            q &= 2
    return frame, FLIPS[s["status"] & 1][q], ctrl, timer


stats = dict(compared=0, quarters=set(), frames_seen=set())


def step(spec=None, n=1, check=True):
    """Run n frames, comparing with the model whenever Mario's own action drives the frame."""
    global prev
    for _ in range(n):
        emu.frame(spec)
        cur = state()
        if check and cur["routine"] == 2 and prev["routine"] == 2 and cur["anim"] in SMB_ANIMS \
                and not (cur["status"] & 4) and not cur["PlayerChangeSizeFlag"] and not cur["SwimmingFlag"] \
                and not prev["PlayerChangeSizeFlag"]:
            exp = model(prev, cur)
            got = (cur["frame"], cur["rflags"], cur["PlayerAnimCtrl"], cur["PlayerAnimTimer"])
            stats["compared"] += 1
            stats["quarters"].add(quarter(cur["angle"]))
            stats["frames_seen"].add(cur["frame"])
            if exp != got:
                fail(f"f{emu.frame_count} x={cur['x']:#x} angle={cur['angle']:#x} state={cur['Player_State']} "
                     f"anim={cur['anim']:#x}: got frame/flip/ctrl/timer {got}, expected {exp}")
        prev = cur
    return prev


def count_skid_dust():
    n = 0
    for slot in range(0xFFFFB000, 0xFFFFD000, 0x40):
        b = emu.read(slot, 0x20)
        if b[0] == 0x08 and b[0x1C] == 3:
            n += 1
    return n


def change_intervals(spec, n):
    """Average frames between walk-frame changes while holding spec."""
    changes, last = [], None
    for i in range(n):
        s = step(spec)
        if last is not None and s["frame"] != last:
            changes.append(i)
        last = s["frame"]
    d = [b - a for a, b in zip(changes, changes[1:])]
    return sum(d[2:]) / max(1, len(d[2:])) if len(d) > 2 else 999


def set_big():
    emu.w8(R["PlayerSize"], 0)
    emu.w8(R["PlayerStatus"], 1)
    emu.w8(MC + 0x16, S("Mario_BigYRadius"))
    emu.w16(MC + 0xC, emu.r16(MC + 0xC) - (S("Mario_BigYRadius") - S("Mario_SmallYRadius")))


try:
    boot_to_level(emu)
    prev = state()
    step(n=30)
    emu.write(MC + 0x30, b"\x7f\xff")       # invulnerable_time: badniks can't kill 0-ring Mario

    # --- walk cadence: slower legs when walking than when running ----------------
    walk = change_intervals("right", 90)
    step(n=60, spec="left")                   # come back
    step(n=40)
    run = change_intervals("right|a", 90)
    print(f"walk cadence {walk:.2f} frames/step, run cadence {run:.2f}")
    if not run < walk:
        fail(f"run cadence {run} not faster than walk {walk}")

    # --- skid: frame + dust ----------------------------------------------------------
    dust, skid_frames = 0, 0
    for i in range(20):
        s = step("left|a")
        if s["anim"] == 0xD:
            skid_frames += 1
            dust = max(dust, count_skid_dust())
        if i == 4:
            emu.screenshot(os.path.join(OUT, "skid.png"))
    print(f"skid frames {skid_frames}, skid dust objects {dust}")
    if skid_frames == 0:
        fail("no skid when reversing at run speed")
    if dust == 0:
        fail("no S2 skid dust (Obj08 anim 3) while skidding")
    step(n=60)

    # --- crouch: not small, yes big ---------------------------------------------------
    s = step("down", 10)
    if s["CrouchingFlag"] or s["frame"] == GFXBASE + 10:
        fail("small Mario crouched")
    step(n=10)
    set_big()
    step(n=5)
    s = step("down", 10)
    emu.screenshot(os.path.join(OUT, "crouch_big.png"))
    if not s["CrouchingFlag"] or s["frame"] != GFXBASE + 0x50 // 8:
        fail(f"big Mario not crouching (flag {s['CrouchingFlag']}, frame {s['frame']:#x})")
    s = step(n=5)
    if s["frame"] != GFXBASE + 0xC8 // 8:
        fail(f"big Mario standing frame wrong: {s['frame']:#x}")
    emu.screenshot(os.path.join(OUT, "stand_big.png"))
    # big jump frame
    for i in range(12):
        s = step("b")
    if s["frame"] != GFXBASE + 4:
        fail(f"big jump frame wrong: {s['frame']:#x}")
    step(n=60)

    # --- forced roll tumble (status.rolling set by "S2") -------------------------------
    step("b", 2)
    emu.w8(MC + 0x22, emu.r8(MC + 0x22) | 4)
    seen = set()
    for i in range(30):
        s = step("b")
        if s["status"] & 4:
            seen.add((s["frame"], s["rflags"]))
    print("forced roll orientations:", sorted(seen))
    if len(seen) < 4:
        fail(f"forced roll shows {len(seen)} orientations, expected 4")
    if any(f not in (GFXBASE + 4, ROT[GFXBASE + 4]) for f, _ in seen):
        fail("forced roll used a non-jump frame")
    step(n=60)

    # --- scripts set by S2 objects: hang, bubble --------------------------------------
    emu.w8(MC + 0x2A, 1)                      # obj_control: an object holds Mario
    emu.w8(MC + 0x1C, 0x11)                   # Hang
    s = step(n=3, check=False)
    if s["frame"] != GFXBASE + 8:
        fail(f"Hang shows frame {s['frame']:#x}, expected big climb 1 {GFXBASE + 8:#x}")
    emu.screenshot(os.path.join(OUT, "hang_big.png"))
    emu.w8(MC + 0x1C, 0x14)                   # Hang2
    fr = set()
    for _ in range(40):
        fr.add(step(check=False)["frame"])
    if fr != {GFXBASE + 8, GFXBASE + 9}:
        fail(f"Hang2 frames {fr}")
    emu.w8(MC + 0x2A, 0)
    emu.w8(MC + 0x1C, 0x15)                   # Bubble, as Obj24 sets it (s2.asm ~45483)
    emu.w16(MC + 0x2E, 0x23)                  # move_lock
    s = step(n=3, check=False)
    if s["frame"] != GFXBASE + 5:
        fail(f"Bubble shows frame {s['frame']:#x}")
    s = step(n=40)
    if s["anim"] != 0:
        fail(f"Bubble did not return to Walk (anim {s['anim']:#x})")

    # back to small for the level run
    emu.w8(R["PlayerSize"], 1)
    emu.w8(R["PlayerStatus"], 0)
    emu.w8(MC + 0x16, S("Mario_SmallYRadius"))
    step(n=10)

    # --- run through EHZ1: loops, slopes, walls ----------------------------------------
    # At the current 1.5x tuning a standing run ($3C0) can't make the loop at
    # x~$1780 (a physics matter, not animation), so give one slope-sized push
    # there: inertia $C00 (Mario_SyncXSpeed folds it in like any S2 change).
    shots = set()
    stuck = 0
    boosted = False
    for i in range(2400):
        spec = "right|a"
        if stuck > 20:
            spec = "right|a|b"
        s = step(spec)
        emu.write(MC + 0x30, b"\x7f\xff")
        if not boosted and s["x"] > 0x1680 and not (s["status"] & 2):
            boosted = True
            emu.w16(MC + 0x14, 0xC00)
            print(f"  boost at x={s['x']:#x}")
        stuck = stuck + 1 if (s["inertia"] < 0x100 and not (s["status"] & 2)) else 0
        q = quarter(s["angle"])
        if not (s["status"] & 2) and q not in shots and s["anim"] in SMB_ANIMS:
            shots.add(q)
            emu.screenshot(os.path.join(OUT, f"loop_q{q}.png"))
            print(f"quarter {q}: x={s['x']:#x} y={s['y']:#x} angle={s['angle']:#x} frame={s['frame']:#x} flips={s['rflags']}")
        if i % 150 == 0:
            print(f"  run f{i}: x={s['x']:#x} y={s['y']:#x} inertia={s['inertia']} angle={s['angle']:#x} "
                  f"status={s['status']:#x} routine={s['routine']}")
        if s["routine"] != 2 and i > 10:
            print(f"  run ended: routine {s['routine']} at x={s['x']:#x}")
            break
    print("quarters seen on the ground:", sorted(shots), "end x", hex(s["x"]))
    if not {1, 2, 3} <= shots:
        fail(f"loop run didn't show every orientation on the ground: {sorted(shots)}")
finally:
    emu.close()

print(f"\ncompared {stats['compared']} frames against the model; quarters {sorted(stats['quarters'])}; "
      f"{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
