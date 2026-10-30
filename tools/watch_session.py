#!/usr/bin/env python3
"""
watch_session.py - boot Mario mode in BlastEm, hand control to the person at
the keyboard, and log Mario's state ~30 times a second until the BlastEm window
is closed (or the time limit runs out).

    python -I tools/watch_session.py [minutes] [player_option]

BlastEm keys: arrows, A/S/D = Genesis A/B/C, Enter = Start.
Mario: S or D = jump (SMB1 A), A = run (SMB1 B).
Log: tools/out/session.csv  (analyse with tools/analyze_session.py)
"""
import csv
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blastem_gdb import BlastEm, S2, HERE, boot_to_level  # noqa: E402

minutes = float(sys.argv[1]) if len(sys.argv) > 1 else 15
option = int(sys.argv[2]) if len(sys.argv) > 2 else 0     # 0 = Mario, 1 = Luigi
OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)
path = os.path.join(OUT, "session.csv")

emu = BlastEm(os.path.join(S2, "s2built.bin"))
S = emu.sym
MC = S("MainCharacter")
RAM = S("Mario_RAM")
RAM_LEN = (S("Mario_RAM_End") - RAM) & 0xFFFFFF
off = lambda n: (S(n) - RAM) & 0xFFFFFF if n in emu.lst.symbols else None
fields = ["Player_State", "Player_XSpeedAbsolute", "VerticalForce", "Mario_LaunchFlag",
          "A_B_Buttons", "Left_Right_Buttons", "PlayerFacingDir", "Player_MovingDir"]
foff = {n: off(n) for n in fields}
xs_off = off("Player_X_Speed")
OBJ, OBJ_END = S("Object_RAM"), S("Dynamic_Object_RAM_End")
hop_off = off("Mario_TornadoHop")


def tornado(objs):
    """The Tornado (ObjB2) driving a cutscene, if any: (routine, routine_secondary, x, y)."""
    for o in range(0, len(objs), 0x40):
        if objs[o] == 0xB2 and objs[o + 0x24] in (4, 6):
            return objs[o + 0x24], objs[o + 0x25], int.from_bytes(objs[o + 8:o + 10], "big"), \
                int.from_bytes(objs[o + 0xC:o + 0xE], "big")
    return "", "", "", ""

boot_to_level(emu, option)
if len(sys.argv) > 3:   # warp: zone/act word in hex, e.g. 0D00 = Chemical Plant 1
    emu.w16(S("Current_ZoneAndAct"), int(sys.argv[3], 16))
    emu.w16(S("Level_Inactive_flag"), 1)     # restart the level -> loads the new zone
    emu.frames(30)
    for _ in range(600):
        if emu.r16(S("Level_Inactive_flag")) == 0 and emu.r8(MC + 0x24) == 2:
            break
        emu.frame()
    emu.frames(120)
GOD = bool(os.environ.get("MARIO_GOD"))      # MARIO_GOD=1: can't be hurt (testing only)
if os.environ.get("MARIO_LIVES"):            # e.g. MARIO_LIVES=99 for long test runs
    emu.w8(S("Life_count"), int(os.environ["MARIO_LIVES"]))
    emu.w8(S("Update_HUD_lives"), 1)
# BlastEm's stub can't be interrupted while running, so sample on a breakpoint
# that is only hit every 8 frames: ChangeRingFrame's ring-animation reset.
sample_bp = emu.lst.addr_of("ChangeRingFrame", r"move\.b\s+#7,\(Rings_anim_counter\)") & 0xFFFFFF
emu.cmd(f"z0,{emu.joy_bp:x},2")      # stop overriding the controller
emu.cmd(f"Z0,{sample_bp:x},2")
print("READY - click the BlastEm window and play. Close it when done.", flush=True)

end = time.time() + minutes * 60
rows = 0
with open(path, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["t", "frame", "zoneact", "x", "y", "x_vel", "y_vel", "inertia", "angle", "status",
                "routine", "anim", "mapping_frame", "y_radius", "move_lock", "obj_control", "ctrl",
                "Player_X_Speed"] + fields +
               ["tornado_routine", "tornado_state", "tornado_x", "tornado_y", "TornadoHop",
                "Control_Locked", "Ctrl_1_Logical"])
    t0 = time.time()
    try:
        while time.time() < end and emu.proc.poll() is None:
            emu.cont()                       # runs until the next sample point (8 frames)
            if GOD:                          # keep the post-hit invulnerability topped up (pits still kill)
                emu.w16(MC + 0x30, 0x40)
            sst = emu.read(MC, 0x40)
            blk = emu.read(RAM, RAM_LEN)
            fc = emu.r16(S("Level_frame_counter"))
            za = emu.r16(S("Current_ZoneAndAct"))
            ctrl = emu.r8(S("Ctrl_1_Held"))
            g = lambda o, s=True: int.from_bytes(sst[o:o + 2], "big", signed=s)
            w.writerow([round(time.time() - t0, 3), fc, f"{za:04X}", g(8, False), g(0xC, False), g(0x10), g(0x12),
                        g(0x14), sst[0x26], sst[0x22], sst[0x24], sst[0x1C], sst[0x1A], sst[0x16], g(0x2E),
                        sst[0x2A], ctrl, int.from_bytes(blk[xs_off:xs_off + 2], "big", signed=True)]
                       + [blk[foff[n]] for n in fields]
                       + list(tornado(emu.read(OBJ, OBJ_END - OBJ)))
                       + [blk[hop_off] if hop_off is not None else "", emu.r8(S("Control_Locked")),
                          emu.r16(S("Ctrl_1_Logical"))])
            rows += 1
            if rows % 20 == 0:
                fh.flush()
    except (ConnectionError, OSError) as e:
        print("stopped:", e)
print(f"logged {rows} samples to {path}")
try:
    emu.close()
except Exception:
    pass
