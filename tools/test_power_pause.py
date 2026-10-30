#!/usr/bin/env python3
"""
test_power_pause.py - Mario's power-up/down sounds and the world pause (H17).

    python -I tools/test_power_pause.py [rom]

1. Grow (10 rings): the power-up sound plays on PSG3, and while Mario's power
   task runs a Buzzer, the oscillators and the level clock stand still; they
   move again afterwards.
2. Big Mario hit (15 rings, so S2's hurt and ring-spill sounds are queued in
   the same frame): the power-down sound plays, frame by frame as the
   generated SMPS file says (interpreted here); the world is paused during the
   injury task, Mario holds still during it, and the knockback moves him after.
Exit code 1 on any failure.
"""
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from blastem_gdb import BlastEm, S2, boot_to_level  # noqa: E402

spec = importlib.util.spec_from_file_location("nes_sfx2smps", os.path.join(HERE, "nes_sfx2smps.py"))
conv = importlib.util.module_from_spec(spec); spec.loader.exec_module(conv)
NOTE = {conv.note_name(i): i for i in range(len(conv.TABLE))}


def smps_timeline(path):
    """Per-frame PSG divider (None = rest) of a tempo-1 PSG SFX built from the
    subset of SMPS that nes_sfx2smps.py emits."""
    lines = [l.split(";")[0].strip() for l in open(path).read().splitlines()]
    labels = {l[:-1]: i for i, l in enumerate(lines) if l.endswith(":")}
    start = next(i for i, l in enumerate(lines) if l.endswith("_PSG3:")) + 1
    out, detune, pc, stack = [], 0, start, []
    while True:
        l = lines[pc]; pc += 1
        if l.startswith("smpsStop"):
            return out
        if l.startswith("smpsReturn"):
            pc = stack.pop(); continue
        if l.startswith("smpsCall"):
            stack.append(pc); pc = labels[l.split()[1]] + 1; continue
        if l.startswith("smpsDetune"):
            v = int(l.split("$")[1], 16); detune = v - 256 if v & 0x80 else v; continue
        m = re.match(r"dc\.b\s+(\w+),\s*\$([0-9A-Fa-f]+)", l)
        if m:
            n = None if m.group(1) == "nRst" else conv.TABLE[NOTE[m.group(1)]] + detune
            out += [n] * int(m.group(2), 16)


def runs(v):
    return [x for i, x in enumerate(v) if i == 0 or v[i - 1] != x]


rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
emu = BlastEm(rom)
S = emu.sym
MC = S("MainCharacter")
DYN, DYN_END = S("Dynamic_Object_RAM"), S("Dynamic_Object_RAM_End")
TR = 0xA00000 + S("zSFX_PSG3")
TASK, TIMER, OSC = S("Mario_PowerTask"), S("Timer"), S("Oscillating_Data")
failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def psg3():
    t = emu.read(TR, 0x1A)
    if not t[0] & 0x80:
        return "off"
    if t[0] & 2:
        return None
    det = t[0x19] - 0x100 if t[0x19] & 0x80 else t[0x19]
    return (t[0x0E] << 8 | t[0x0D]) + det


def spawn_buzzer(dx, dy):
    m = emu.read(MC, 0x10)
    x, y = int.from_bytes(m[8:10], "big"), int.from_bytes(m[12:14], "big")
    s = next(s for s in range(DYN, DYN_END, 0x40) if emu.r8(s) == 0)
    emu.write(s, bytes(0x40))
    emu.w16(s + 8, x + dx); emu.w16(s + 0xC, y + dy); emu.w8(s, 0x4B)
    return s


def watch(frames, buzzer):
    """Per frame: (task, buzzer x, oscillator bytes, clock, mario x, mario y, psg3)."""
    rows = []
    for _ in range(frames):
        emu.frame()
        rows.append(dict(task=emu.r8(TASK), bx=emu.r16(buzzer + 8), osc=emu.read(OSC, 8),
                         clock=emu.read(TIMER, 4), mx=emu.r16(MC + 8), my=emu.r16(MC + 0xC), psg=psg3()))
    return rows


def paused_checks(rows, label, mario_moves):
    during = [r for r in rows[1:] if r["task"]]
    after = [r for r in rows if not r["task"]][-30:]
    check(len(during) > 40, f"{label}: power task ran {len(during)} frames")
    check(len({r["bx"] for r in during}) == 1, f"{label}: Buzzer stands still while paused")
    check(len({r["osc"] for r in during}) == 1, f"{label}: oscillators stand still while paused")
    check(len({r["clock"] for r in during}) == 1, f"{label}: level clock stops while paused")
    check(len({r["bx"] for r in after}) > 1 and len({r["clock"] for r in after}) > 1,
          f"{label}: Buzzer and clock run again afterwards")
    if mario_moves:
        # SMB1 halts Mario for the injury task too; the knockback comes after it
        # (moving during the pause dropped him through paused solid objects)
        resume = [r for r in rows[rows.index(during[-1]) + 1:]][:20]
        # (y may change by the radius difference when he shrinks: feet kept in place)
        held = sorted({(r["mx"], r["my"]) for r in during[1:]})
        shrink = S("Mario_BigYRadius") - S("Mario_SmallYRadius")
        check(len({x for x, _ in held}) == 1 and max(y for _, y in held) - min(y for _, y in held) <= shrink,
              f"{label}: Mario holds still while paused ({[(hex(x), hex(y)) for x, y in held]})")
        check(len({(r["mx"], r["my"]) for r in resume}) > 5, f"{label}: the knockback moves him afterwards")


try:
    boot_to_level(emu)
    emu.frames(20)
    emu.write(MC + 0x30, b"\x7f\xff")                      # no hurt from the Buzzer during the grow
    bz = spawn_buzzer(0x60, -0x50)
    emu.w16(S("Ring_count"), 10)
    rows = watch(110, bz)
    paused_checks(rows, "grow", mario_moves=False)
    up = [r["psg"] for r in rows if r["psg"] not in ("off",)]
    up_expected = smps_timeline(os.path.join(S2, "sound", "sfx", "D2 - Mario Power Up.asm"))
    check(runs(up)[:len(runs(up_expected))] == runs(up_expected), "power-up sound plays (PSG3 pitches)")

    emu.frames(60)
    emu.w16(S("Ring_count"), 15)
    emu.write(MC + 0x30, b"\x00\x00")
    bz2 = spawn_buzzer(0x10, 0)                            # touching Mario: a side hit
    rows = watch(110, bz)
    paused_checks(rows, "injury", mario_moves=True)
    start = next((i for i, r in enumerate(rows) if r["psg"] != "off" and r["psg"] not in up_expected), None)
    down = [r["psg"] for r in rows[start:] if r["psg"] != "off"] if start is not None else []
    down_expected = smps_timeline(os.path.join(S2, "sound", "sfx", "D1 - Mario Power Down.asm"))
    print("  expected:", runs(down_expected))
    print("  played:  ", runs(down)[:len(runs(down_expected)) + 2])
    check(runs(down)[:len(runs(down_expected))] == runs(down_expected),
          f"power-down sound plays as written ({len(down)} frames on PSG3, file: {len(down_expected)})")
finally:
    emu.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
