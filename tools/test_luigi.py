#!/usr/bin/env python3
"""
test_luigi.py - Luigi (Player_option 1) and the Mario-only character select.

    python -I tools/test_luigi.py

Boots the real menus twice (MARIO, then LUIGI) into Emerald Hill 1 and checks:
  - the menu choice reaches the game: Player_mode 3, Mario_IsLuigi
  - Luigi's palette: line 0 entry LuigiPalSlot is his green, normal and fade
    target; every other entry is S2's; Mario keeps S2's colour there
  - SMB2J physics: walk/run friction $68/$B4 (Mario $98/$E4), no doubling when
    turning (Mario doubles), jump forces $18/$42 (Mario $20/$70), the starting
    falling force $42; and per-frame speed changes equal the friction adder
  - a held standing jump goes higher for Luigi than for Mario
Screenshots: tools/out/luigi/
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blastem_gdb import BlastEm, S2, HERE, boot_to_level  # noqa: E402

OUT = os.path.join(HERE, "out", "luigi")
os.makedirs(OUT, exist_ok=True)
fails = []


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        fails.append(msg)


pal_file = open(os.path.join(S2, "art", "palettes", "SonicAndTails.bin"), "rb").read()
S2_LINE0 = [(pal_file[i * 2] << 8) | pal_file[i * 2 + 1] for i in range(16)]
GREEN = SLOT = None
for line in open(os.path.join(S2, "mario", "luigi_palette.asm")):
    if line.startswith("LuigiGreen\t"):
        GREEN = int(line.split("$")[1].split()[0], 16)
    if line.startswith("LuigiPalSlot"):
        SLOT = int(line.split("$")[1].split()[0], 16)


def run(option):
    name = ["mario", "luigi"][option]
    emu = BlastEm(os.path.join(S2, "s2built.bin"))
    S = emu.sym
    MC = S("MainCharacter")
    b = lambda n: emu.r8(S(n))
    res = {}
    try:
        boot_to_level(emu, option)
        check(emu.r16(S("Player_option")) == option, f"{name}: Player_option = {option}")
        check(emu.r16(S("Player_mode")) == 3, f"{name}: Player_mode = 3")
        check(emu.r8(MC) == 0xD0, f"{name}: main character is ObjMario")
        check(b("Mario_IsLuigi") == (0xFF if option else 0), f"{name}: Mario_IsLuigi = ${b('Mario_IsLuigi'):02X}")
        emu.screenshot(os.path.join(OUT, f"{name}_start.png"))

        # palette line 0
        for lab in ("Normal_palette", "Target_palette"):
            words = [emu.r16(S(lab) + 2 * i) for i in range(16)]
            want = list(S2_LINE0)
            if option:
                want[SLOT] = GREEN
            check(words == want, f"{name}: {lab} line 0 " + ("has Luigi's green" if option else "is S2's")
                  + ("" if words == want else f" {[hex(w) for w in words]}"))

        check(b("VerticalForce") == (0x42 if option else 0x70), f"{name}: starting fall force ${b('VerticalForce'):02X}")

        # walking right from a standstill: friction adder and the speed steps
        steps, adders = [], set()
        prev = None
        for _ in range(40):
            emu.frame("right")
            sp = (emu.r16(S("Player_X_Speed"), signed=True) << 8) | b("Player_X_MoveForce")
            adders.add((b("FrictionAdderHigh") << 8) | b("FrictionAdderLow"))
            if prev is not None and sp != prev:
                steps.append(sp - prev)
            prev = sp
        walk = 0x68 if option else 0x98
        check(walk in adders, f"{name}: walking friction ${walk:02X} (seen {sorted(hex(a) for a in adders)})")
        check(steps and steps[0] == walk, f"{name}: first speed steps {[hex(s) for s in steps[:4]]}")
        res["walk_frames"] = len([s for s in steps if s > 0])
        # turn around while walking: SMB1 doubles the friction, SMB2J's Luigi doesn't
        adders = set()
        for _ in range(6):
            emu.frame("left")
            adders.add((b("FrictionAdderHigh") << 8) | b("FrictionAdderLow"))
        turn = walk if option else walk * 2
        check(turn in adders, f"{name}: turning friction ${turn:X} (seen {sorted(hex(a) for a in adders)})")
        emu.frames(90)          # stop
        # run (Genesis A held)
        adders = set()
        for _ in range(30):
            emu.frame("right|a")
            adders.add((b("FrictionAdderHigh") << 8) | b("FrictionAdderLow"))
        run_f = 0xB4 if option else 0xE4
        check(run_f in adders, f"{name}: running friction ${run_f:02X} (seen {sorted(hex(a) for a in adders)})")
        emu.frames(120)         # stop again

        # held standing jump: forces and height
        y0 = emu.r16(MC + 0xC)
        emu.frame("b")
        emu.frame("b")
        check((b("VerticalForce"), b("VerticalForceDown")) == ((0x18, 0x42) if option else (0x20, 0x70)),
              f"{name}: jump forces ${b('VerticalForce'):02X}/${b('VerticalForceDown'):02X}")
        top = y0
        for _ in range(90):
            emu.frame("b")
            top = min(top, emu.r16(MC + 0xC))
        res["jump"] = y0 - top
        print(f"  {name}: held standing jump {res['jump']} px")
        emu.frames(60)

        if option:
            # run right up EHZ1's first hill: Mario's acceleration uphill (Luigi_Uphill),
            # SMB2J's on the flat (angle steady for two frames, as X_Physics runs
            # before AnglePos updates it)
            flat, up, prev_a = set(), set(), None
            for _ in range(240):
                emu.frame("right|a")
                a = b("Player_State") == 0 and emu.r8(MC + S("angle"))
                f = (b("FrictionAdderHigh") << 8) | b("FrictionAdderLow")
                if a is not False and a == prev_a:
                    if a == 0:
                        flat.add(f)
                    elif 0x88 <= a <= 0xF8:
                        up.add(f)
                prev_a = a
            check(up == {0xE4}, f"luigi: running uphill uses Mario's $E4 (seen {sorted(hex(x) for x in up)})")
            check(0xB4 in flat and 0xE4 not in flat,
                  f"luigi: running on the flat uses $B4 (seen {sorted(hex(x) for x in flat)})")
            emu.screenshot(os.path.join(OUT, "luigi_uphill.png"))
        emu.screenshot(os.path.join(OUT, f"{name}_after.png"))
    finally:
        emu.close()
    return res


mario = run(0)
luigi = run(1)
check(luigi["jump"] > mario["jump"], f"Luigi jumps higher: {luigi['jump']} px vs Mario's {mario['jump']} px")
print(f"walk-up frames (speed rising): Mario {mario['walk_frames']}, Luigi {luigi['walk_frames']}")
print(f"\n{len(fails)} failure(s)")
sys.exit(1 if fails else 0)
