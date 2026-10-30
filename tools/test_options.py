#!/usr/bin/env python3
"""
test_options.py - the Mario build's options menu (H31, H33) in BlastEm.

    python -I tools/test_options.py [rom]

Title -> OPTIONS. Box 1 (LEVEL SELECT) picks MARIO GAME/LUIGI GAME
(Player_option); START on it opens the level select; START there starts
Emerald Hill 1 as the chosen character. Then back to the level select:
CREDITS (the old SPECIAL STAGE entry, H34) loads DEZ and starts the ending.
Screenshots go to tools/out/options/ (credits_NNNN.png: check the fall
scene shows DEZ's starfield and clouds, not garbage).
Exit code 1 on any failure.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blastem_gdb import BlastEm, S2, HERE  # noqa: E402

OUT = os.path.join(HERE, "out", "options")
os.makedirs(OUT, exist_ok=True)
rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
emu = BlastEm(rom)
S = emu.sym
failures = []
CREDIT_SHOTS = (60, 1500, 2250, 3000)   # frames into the ending (tools/out/options/credits_NNNN.png):
                                        # a photo, the Tornado, the fall over DEZ's background, the sky


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


gm = lambda: emu.r8(S("Game_Mode"))


def wait(pred, n):
    for _ in range(n):
        if pred():
            return True
        emu.frame()
    return pred()


try:
    check(wait(lambda: gm() == 4, 1500), "title screen")
    emu.frames(420)
    emu.tap("down"); emu.tap("down"); emu.tap("start")
    check(wait(lambda: gm() == 0x24, 200), "options menu")
    emu.frames(60)
    emu.tap("down")
    check(emu.r8(S("Options_menu_box")) == 1, "box 1 selected")
    seen = []
    for _ in range(3):
        emu.tap("right")
        seen.append(emu.r16(S("Player_option")))
    check(seen == [1, 0, 1], f"box 1 toggles MARIO/LUIGI ({seen})")
    check(emu.r16(S("Two_player_items")) == 0, "Two_player_items untouched")
    emu.frames(10)
    emu.screenshot(os.path.join(OUT, "options_luigi.png"))
    emu.tap("start")
    check(wait(lambda: gm() == 0x28, 200), f"START on box 1 opens the level select (Game_Mode {gm():#x})")
    check(emu.r16(S("Two_player_mode")) == 0, "one player")
    emu.frames(60)
    emu.screenshot(os.path.join(OUT, "level_select.png"))
    emu.tap("start")                                      # first entry: Emerald Hill 1
    check(wait(lambda: gm() == 0x0C, 400), f"level select starts a level (Game_Mode {gm():#x})")
    emu.frames(200)
    check(emu.r8(S("MainCharacter")) == 0xD0, "main character is ObjMario")
    check(emu.r8(S("Mario_IsLuigi")) == 0xFF, "playing Luigi, as chosen in box 1")
    check(emu.r16(S("Current_ZoneAndAct")) == 0, f"Emerald Hill 1 ({emu.r16(S('Current_ZoneAndAct')):#06x})")
    emu.screenshot(os.path.join(OUT, "level_luigi.png"))

    # ---- CREDITS (H34): the old SPECIAL STAGE entry loads DEZ, then the ending ----
    emu.w8(S("Level_Inactive_flag"), 0)
    emu.w8(S("Game_Mode"), 0x28)                          # back to the level select
    check(wait(lambda: gm() == 0x28, 600), "level select again")
    emu.frames(120)
    order = S("LevelSelect_Order")
    ss = next(i for i in range(32) if emu.r16(order + 2 * i) == 0x4000)
    emu.w16(S("Level_select_zone"), ss)
    emu.frames(10)
    emu.screenshot(os.path.join(OUT, "level_select_credits.png"))
    emu.tap("start")
    check(wait(lambda: gm() == 0x20, 600), f"START on CREDITS starts the ending (Game_Mode {gm():#x})")
    check(emu.r16(S("Current_ZoneAndAct")) == 0x0E00, f"ending in DEZ ({emu.r16(S('Current_ZoneAndAct')):#06x})")
    prev = 0
    for f in CREDIT_SHOTS:
        emu.frames(f - prev)
        prev = f
        emu.screenshot(os.path.join(OUT, f"credits_{f:04d}.png"))
finally:
    emu.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
