#!/usr/bin/env python3
"""
test_phase2.py - automated Phase 2 checks for Mario mode (build with marioMode = 1).

    python -I tools/test_phase2.py [rom]

Drives the real menus through BlastEm's GDB stub (tools/blastem_gdb.py):
title -> OPTIONS -> PLAYER SELECT "MARIO" -> Emerald Hill 1, then
walks, jumps, enters/exits debug mode and dies (time over), checking RAM
at each step. Screenshots go to tools/out/phase2/. Exit code 1 on failure.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blastem_gdb import BlastEm, S2, HERE  # noqa: E402

OUT = os.path.join(HERE, "out", "phase2")
os.makedirs(OUT, exist_ok=True)
rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
emu = BlastEm(rom)
S = emu.sym
MC = S("MainCharacter")
failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def shot(name):
    emu.screenshot(os.path.join(OUT, name + ".png"))


def wait_until(pred, limit, spec=None):
    for _ in range(limit):
        if pred():
            return True
        emu.frame(spec)
    return pred()


def obj(off, size=1, signed=False):
    if size == 1:
        v = emu.r8(MC + off)
        return v - 256 if signed and v >= 128 else v
    return emu.r16(MC + off, signed)


game_mode = lambda: emu.r8(S("Game_Mode"))

try:
    # --- title screen -> options -> MARIO ---
    check(wait_until(lambda: game_mode() == 4, 1200), "reached title screen")
    emu.frames(420)          # let the title intro finish so the menu accepts input
    shot("01_title")
    emu.tap("down"); emu.tap("down"); emu.tap("start")
    check(wait_until(lambda: game_mode() == 0x24, 120), "entered options menu")
    emu.frames(60)           # let the options screen finish fading in
    # Box 0 is DIFFICULTY: HYBRID MODE (0) and MARIO MODE (1); Right wraps between them
    seen = []
    for _ in range(4):
        emu.tap("right")
        seen.append(emu.r16(S("Difficulty_option")))
        if len(seen) == 1:
            emu.frames(10)
            shot("02_options_mario_mode")
    print("  Difficulty_option after each Right:", seen)
    check(seen == [1, 0, 1, 0], f"difficulty box has 2 choices, Hybrid and Mario: {seen}")
    emu.frames(10)
    shot("02_options_hybrid")
    check(emu.r16(S("Difficulty_option")) == 0, "Difficulty_option = 0 (HYBRID MODE)")
    check(emu.r16(S("Player_option")) == 0, "Player_option = 0 (MARIO)")

    # --- start the game: Emerald Hill 1 ---
    emu.tap("start")
    check(wait_until(lambda: game_mode() == 0x0C, 300), "level game mode")
    emu.frames(200)          # title card
    check(obj(0) == S("ObjID_Mario") if "ObjID_Mario" in emu.lst.symbols else obj(0) == 0xD0,
          f"main character is ObjMario (id ${obj(0):02X})")
    check(obj(0x24) == 2, f"routine = Control ({obj(0x24)})")
    check(emu.r32(MC + 4) == S("MapUnc_Mario"), "mappings = MapUnc_Mario")
    check(obj(0x16) == 0x0E, f"y_radius = small $0E (${obj(0x16):02X})")
    shot("03_level_start")

    # --- walk ---
    x0 = obj(8, 2)
    emu.frames(90, "right")
    x1 = obj(8, 2)
    check(x1 > x0 + 40, f"walked right: x {x0:#x} -> {x1:#x}")
    check(1 <= obj(0x1A) < S("MarioFrame_Count") if "MarioFrame_Count" in emu.lst.symbols else True,
          f"mapping_frame in range ({obj(0x1A)})")
    shot("04_walking")

    # --- jump ---
    y_ground = obj(0x0C, 2)
    emu.frames(12, "right|b")
    in_air = obj(0x22) & 2
    y_air = obj(0x0C, 2)
    check(in_air and y_air < y_ground - 20, f"jumped: y {y_ground:#x} -> {y_air:#x}")
    check(obj(0x16) == 0x0E, f"radius kept in the air (${obj(0x16):02X})")
    shot("05_jump")
    check(wait_until(lambda: not (obj(0x22) & 2), 120, "right"), "landed")
    emu.frames(2)
    check(obj(0x16) == 0x0E and not (obj(0x22) & 4), "after landing: small radius, not rolling")
    shot("06_landed")

    # --- debug mode in and out ---
    emu.w16(S("Debug_mode_flag"), 1)
    emu.tap("b")
    check(emu.r8(S("Debug_placement_mode")) != 0, "entered debug placement mode")
    emu.frames(20)
    shot("07_debug")
    emu.tap("b")
    emu.frames(4)
    check(emu.r8(S("Debug_placement_mode")) == 0, "left debug mode")
    check(emu.r32(MC + 4) == S("MapUnc_Mario"), "mappings restored to MapUnc_Mario")
    check(obj(0x16) == 0x0E, f"radius restored after debug (${obj(0x16):02X})")
    emu.frames(30, "right")
    shot("08_after_debug")
    emu.w16(S("Debug_mode_flag"), 0)

    # --- death (time over) -> level restart ---
    lives = emu.r8(S("Life_count"))
    emu.write(S("Timer_minute"), bytes([9, 59, 58]))
    check(wait_until(lambda: obj(0x24) == 6, 180), "time over killed Mario (routine Dead)")
    emu.frames(20)
    shot("09_dying")
    check(wait_until(lambda: obj(0x24) == 8, 400), "Mario reached Gone")
    check(emu.r8(S("Life_count")) == lives - 1, "lost a life")
    check(wait_until(lambda: game_mode() == 0x0C and obj(0x24) == 2, 900), "level restarted, Mario back in control")
    emu.frames(60)
    check(obj(0) == 0xD0, "Mario respawned")
    shot("10_respawned")
finally:
    emu.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
