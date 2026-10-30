#!/usr/bin/env python3
"""
test_breakables.py - Mario and S2's breakable blocks (EHZ1, objects spawned).

    python -I tools/test_breakables.py [rom]

Obj32 (CPZ tube caps / HTZ rocks), Obj3D (OOZ striped blocks) and Obj2F (HTZ
smashable ground) break when the player lands on them with the "Roll" anim ID.
Mario's stomp ID (Mario_StompAnimID) reads Roll while he is falling, so:
  - landing on one while falling breaks it;
  - jumping into it from below doesn't.
The objects use their zone's art, so they look wrong in EHZ; only the logic is
tested. Exit code 1 on any failure.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blastem_gdb import BlastEm, S2, boot_to_level  # noqa: E402

rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
emu = BlastEm(rom)
S = emu.sym
MC = S("MainCharacter")
DYN, DYN_END = S("Dynamic_Object_RAM"), S("Dynamic_Object_RAM_End")
failures = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def mario():
    b = emu.read(MC, 0x40)
    return dict(x=int.from_bytes(b[8:10], "big"), y=int.from_bytes(b[0xC:0xE], "big"),
                status=b[0x22], routine=b[0x24], anim=b[0x1C])


def spawn(objid, x, y, subtype=0):
    s = next(s for s in range(DYN, DYN_END, 0x40) if emu.r8(s) == 0)
    emu.write(s, bytes(0x40))
    emu.w8(s + 0x28, subtype)
    emu.w16(s + 8, x); emu.w16(s + 0xC, y)
    emu.w8(s, objid)
    emu.frames(2)
    return s


def intact(slot, objid):
    return emu.r8(slot) == objid and emu.r8(slot + 0x24) == 2


def place(x, y, yv):
    emu.w16(MC + 8, x); emu.w16(MC + 0xA, 0)
    emu.w16(MC + 0xC, y); emu.w16(MC + 0xE, 0)
    emu.w16(MC + 0x10, 0); emu.w16(MC + 0x12, yv & 0xFFFF); emu.w16(MC + 0x14, 0)
    emu.w8(MC + 0x22, (emu.r8(MC + 0x22) & 1) | 2)
    emu.w16(S("Mario_LastYVel"), yv & 0xFFFF)
    emu.w16(S("Mario_LastXHand"), 0)
    emu.w16(S("Player_X_Speed"), 0)
    emu.w8(S("Player_State"), 2)


def settle(n=150):
    for _ in range(n):
        emu.frame()
        m = mario()
        if m["routine"] == 2 and not (m["status"] & 2):
            return m
    return mario()


try:
    boot_to_level(emu)
    emu.frames(20)
    emu.write(MC + 0x30, b"\x7f\xff")
    home = settle()
    for objid, name, sub in [(0x32, "Obj32 (CPZ cap / HTZ rock)", 0), (0x3D, "Obj3D (OOZ block)", 0),
                             # Obj2F only breaks with a negative subtype or the player on
                             # collision layer $E (even for Sonic); $80 = always breakable
                             (0x2F, "Obj2F (HTZ smashable ground)", 0x80),
                             # subtype 0 (HTZ's loop floors) with Mario on path $C: for
                             # Mario a stomp breaks it on any path (H23)
                             (0x2F, "Obj2F subtype 0 (HTZ loop floor), Mario on path $C", 0)]:
        # from below: a block over Mario's head, Mario jumps into it
        m = settle()
        s = spawn(objid, m["x"], m["y"] - 0x38, sub)
        for i in range(40):
            emu.frame("b" if i < 15 else None)
        check(intact(s, objid), f"{name}: jumping into it from below leaves it intact")
        emu.write(s, bytes(0x40))                          # remove it
        settle()
        # from above: Mario falls onto it
        m = mario()
        s = spawn(objid, m["x"], m["y"] - 0x60, sub)      # right above him: on camera
        place(m["x"], m["y"] - 0x60 - 0x40, 0x200)
        emu.w8(MC + S("top_solid_bit"), 0x0C)             # S2's default path
        broke = False
        for i in range(40):
            emu.frame()
            if os.environ.get("BRKDEBUG"):
                mm, o = emu.read(MC, 0x40), emu.read(s, 0x40)
                print(f"   {i:2d} M y={int.from_bytes(mm[12:14], 'big'):04X} st={mm[0x22]:02X} anim={mm[0x1C]:02X} "
                      f"tsb={mm[0x3E]:02X} O id={o[0]:02X} rt={o[0x24]:02X} y={int.from_bytes(o[12:14], 'big'):04X} "
                      f"st={o[0x22]:02X} o32={o[0x32]:02X} | rt={mm[0x24]} oc={mm[0x2A]:02X} "
                      f"task={emu.r8(S('Mario_PowerTask')):02X} tc={emu.r8(S('TimerControl')):02X} "
                      f"ps={emu.r8(S('Player_State'))} vf={emu.r8(S('VerticalForce')):02X} "
                      f"rings={emu.r16(S('Ring_count'))} pause={emu.r16(S('Game_paused'))}")
            if not intact(s, objid):
                broke = True
                break
        check(broke, f"{name}: landing on it while falling breaks it")
        emu.frames(30)
        # clean up: Obj3D's invisible launcher grabs the player after the block
        # breaks (OOZ behaviour); delete leftovers and release Mario
        for slot in range(DYN, DYN_END, 0x40):
            if emu.r8(slot) == objid:
                emu.write(slot, bytes(0x40))
        emu.w8(MC + 0x2A, 0)
        settle()
finally:
    emu.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
