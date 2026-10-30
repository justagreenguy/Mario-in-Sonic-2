#!/usr/bin/env python3
"""
test_postcredits.py - the post-credits scene (mario/mario_postcredits.asm) in BlastEm.

    python -I tools/test_postcredits.py [rom] [mario|luigi]

Title -> level select -> CREDITS (H34) starts the ending; the test sets
Credits_Trigger to skip the cutscene and jumps the credits to their last
slide, then presses a button on the logo. EndgameCredits (H35) must start
EHZ2 on the credits-demo path; the director (ObjPostCredits) then walks
Mario to the capsule, hops him onto its button (Peach comes out: H36), off
again, up to Peach, shows the message and the victory music, fades out and
resets to the SEGA screen. Screenshots: tools/out/postcredits/scene_*.png.
Exit code 1 on any failure.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blastem_gdb import BlastEm, S2, HERE  # noqa: E402

OUT = os.path.join(HERE, "out", "postcredits")
os.makedirs(OUT, exist_ok=True)
rom = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].endswith(".bin") else os.path.join(S2, "s2built.bin")
who = "luigi" if "luigi" in sys.argv[1:] else "mario"
emu = BlastEm(rom)
S = emu.sym
failures = []
M = S("MainCharacter")
PHASES = ["walk", "hop", "wait Peach", "hop off", "stop", "message", "fade"]


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


def find_obj(oid, routine=None):
    for slot in range(0x80):
        a = S("Object_RAM") + slot * 0x40
        if emu.r8(a) == oid and (routine is None or emu.r8(a + 0x24) == routine):
            return a
    return None


try:
    # ---- title -> level select (OPTIONS box 1) -> CREDITS ----
    check(wait(lambda: gm() == 4, 1500), "title screen")
    emu.frames(420)
    emu.tap("down"); emu.tap("down"); emu.tap("start")
    check(wait(lambda: gm() == 0x24, 200), "options menu")
    emu.frames(60)
    emu.tap("down")
    for _ in range(4):
        if emu.r16(S("Player_option")) == (1 if who == "luigi" else 0):
            break
        emu.tap("right")
    emu.tap("start")
    check(wait(lambda: gm() == 0x28, 200), "level select")
    emu.frames(120)
    order = S("LevelSelect_Order")
    ss = next(i for i in range(32) if emu.r16(order + 2 * i) == 0x4000)
    emu.w16(S("Level_select_zone"), ss)
    emu.frames(10)
    emu.tap("start")
    check(wait(lambda: gm() == 0x20, 600), "CREDITS starts the ending")
    emu.frames(60)
    emu.w8(S("Credits_Trigger"), 1)                      # skip the cutscene
    check(wait(lambda: emu.r16(S("CreditsScreenIndex")) == 0 and emu.r8(S("Credits_Trigger")) == 0, 400),
          "credits started")
    emu.frames(30)
    emu.w16(S("CreditsScreenIndex"), 20)                  # the last slide next
    # the logo: a button skips it once the flash is over
    for _ in range(1500):
        emu.frame()
        if emu.r16(S("Current_ZoneAndAct")) == 0x0001 and gm() & 0x7F == 0x0C:
            break
        if emu.r16(S("CreditsScreenIndex")) >= 0x5E:
            emu.tap("c")
    check(gm() & 0x7F == 0x0C and emu.r16(S("Current_ZoneAndAct")) == 0x0001,
          f"EHZ2 loads after the logo (Game_Mode {gm():#x}, zone {emu.r16(S('Current_ZoneAndAct')):#06x})")
    check(emu.r16(S("Demo_mode_flag")) == 0xFFFF, "credits-demo path (Demo_mode_flag -1)")

    # ---- the scene ----
    check(wait(lambda: find_obj(S("ObjID_PostCredits"), 2) is not None, 200), "the director runs")
    d = find_obj(S("ObjID_PostCredits"), 2)
    check(emu.r8(M) == 0xD0, "ObjMario")
    check(emu.r8(S("PlayerSize")) == 0 and emu.r8(S("PlayerStatus")) == 1, "Super Mario")
    check(emu.r8(S("Mario_IsLuigi")) == (0xFF if who == "luigi" else 0), f"playing {who}")
    emu.frames(30)
    emu.screenshot(os.path.join(OUT, f"scene_{who}_0start.png"))
    check(emu.r8(S("Level_started_flag")) == 0, "no HUD")
    seen, shots, song_ids, lines, fm1 = [], set(), set(), [], []
    fm_lo = 0x8000 + (S("MarioVictory_FM1") - S("MusicPoint1"))
    fm_hi = 0x8000 + (S("MarioVictory_PSG1") - S("MusicPoint1"))
    landed_on_button = mario_end_x = peach_x = None
    victory_phase = 0
    for f in range(3000):
        emu.frame()
        if gm() != 0x0C:
            break
        ph = emu.r8(d + 0x25) // 2
        if not seen or seen[-1] != ph:
            seen.append(ph)
            print(f"  frame {f}: phase {PHASES[ph] if ph < len(PHASES) else ph}, Mario x {emu.r16(M + 8):04X} "
                  f"y {emu.r16(M + 0xC):04X}, cam {emu.r16(S('Camera_X_pos')):04X},{emu.r16(S('Camera_Y_pos')):04X}")
            if ph == 2:
                btn = emu.r16(d + 0x32) | 0xFFFF0000
                landed_on_button = (emu.r8(M + 0x22) & 0x08) != 0
            if ph == 5:
                mario_end_x = emu.r16(M + 8)
                p = emu.r16(S("PostCredits_Peach"))
                peach_x = emu.r16(0xFFFF0000 | (p + 8)) if p else None
                facing_right = emu.r8(M + 0x22) & 1 == 0
        song = emu.r8(0xA00000 + S("zCurSong"))
        if song == S("MusID_MarioVictory") and song not in song_ids:
            victory_phase = ph
        song_ids.add(song)
        if ph == 5:
            lines.append(emu.r8(d + 0x36))
            t = emu.read(0xA00000 + S("zSongFM1"), 5)          # the triangle's FM track
            if t[0] & 0x80:
                fm1.append(t[3] | t[4] << 8)
        for name, cond in (("1hop", ph == 1 and emu.r16(M + 0x12) & 0x8000 == 0),
                           ("2peach", ph == 2 and emu.r16(S("PostCredits_Peach")) != 0),
                           ("3hopoff", ph == 3 and emu.r8(M + 0x22) & 2),
                           ("4thanks", ph == 5 and emu.r8(d + 0x36) == 1),
                           ("5message", ph == 5 and emu.r8(d + 0x36) == 7),
                           ("6fade", ph == 6)):
            if cond and name not in shots:
                shots.add(name)
                emu.screenshot(os.path.join(OUT, f"scene_{who}_{name}.png"))
    check(seen[:7] == list(range(7)), f"phases in order ({seen})")
    check(landed_on_button, "Mario landed on the capsule's button (on_object)")
    check(peach_x is not None and mario_end_x is not None and 0x10 <= peach_x - mario_end_x <= 0x30,
          f"Mario stops just left of Peach (Mario {mario_end_x}, Peach {peach_x})")
    check(facing_right, "Mario faces Peach")
    check(lines and max(lines) == 7 and lines == sorted(lines), "message lines appear one by one, up to 7")
    check(S("MusID_MarioVictory") in song_ids, f"the victory music reaches the driver ({sorted(map(hex, song_ids))})")
    check(victory_phase == 3, f"the victory music starts as he jumps off the capsule (phase {PHASES[victory_phase]})")
    tri = [p for p in fm1 if fm_lo <= p < fm_hi]
    wraps = sum(1 for k in range(1, len(tri)) if tri[k] < tri[k - 1])
    check(len(tri) > 600 and wraps >= 1, f"FM1 plays the triangle (MarioVictory_FM1: {len(tri)} frames) and loops ({wraps})")
    check(find_obj(S("ObjID_Animal")) is None, "no animals")
    check(gm() == 0, f"resets to the SEGA screen (Game_Mode {gm():#x})")
    check(emu.r16(S("Demo_mode_flag")) == 0, "Demo_mode_flag cleared")
finally:
    emu.close()

print(f"\n{len(failures)} failure(s)")
sys.exit(1 if failures else 0)
