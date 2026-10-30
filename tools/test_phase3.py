#!/usr/bin/env python3
"""
test_phase3.py - frame-by-frame comparison of the 68k SMB1 physics against the
6502 reference model (tools/smb1_ref.py), on flat ground in Emerald Hill 1.

    python -I tools/test_phase3.py [rom]

Every frame both get the same buttons; S2 supplies ground contact (as SMB1's
PlayerBGCollision would). Frames where the floor isn't flat (angle != 0) are
not compared and the model is re-seeded from the ROM afterwards, since S2's
slopes legitimately change the speed. Exit code 1 on any mismatch.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blastem_gdb import BlastEm, S2, HERE, BUTTONS, buttons, boot_to_level  # noqa: E402
from smb1_ref import SMB1Player, s8  # noqa: E402

OUT = os.path.join(HERE, "out", "phase3")
os.makedirs(OUT, exist_ok=True)
rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
emu = BlastEm(rom)
S = emu.sym
MC = S("MainCharacter")

BYTE_VARS = ["Player_X_MoveForce", "Player_XSpeedAbsolute", "MaximumLeftSpeed", "MaximumRightSpeed",
             "FrictionAdderLow", "FrictionAdderHigh", "RunningTimer", "JumpSwimTimer", "RunningSpeed",
             "Player_State", "VerticalForce", "VerticalForceDown", "Player_MovingDir", "PlayerFacingDir",
             "PlayerAnimTimerSet", "CrouchingFlag", "PlayerSize", "DiffToHaltJump",
             "A_B_Buttons", "PreviousA_B_Buttons", "Left_Right_Buttons", "Up_Down_Buttons", "SavedJoypadBits"]
ram = {n: S(n) for n in BYTE_VARS + ["Player_X_Speed", "JumpOrigin_Y", "Mario_LastXHand"]}


def smb_joypad(gen):
    """Genesis held bits -> SMB1 SavedJoypadBits (same mapping as Mario_ReadJoypad)."""
    v = 0
    if gen & (1 << BUTTONS["right"]): v |= 0x01
    if gen & (1 << BUTTONS["left"]): v |= 0x02
    if gen & (1 << BUTTONS["down"]): v |= 0x04
    if gen & (1 << BUTTONS["up"]): v |= 0x08
    if gen & (1 << BUTTONS["start"]): v |= 0x10
    if gen & (1 << BUTTONS["a"]): v |= 0x40
    if gen & (1 << BUTTONS["b"]): v |= 0x80
    return v


XSCALE = S("Mario_XSpeedToS2")      # S2 units per SMB1 X_Speed unit
YSCALE = S("Mario_YScale")          # 8.8 vertical multiplier
RAM_BASE = S("Mario_RAM")
RAM_LEN = S("Mario_RAM_End") - RAM_BASE


def rom_state():
    sst = emu.read(MC, 0x40)
    blk = emu.read(RAM_BASE, RAM_LEN)
    off = lambda n: (ram[n] - RAM_BASE) & 0xFFFFFF
    st = {n: blk[off(n)] for n in BYTE_VARS}
    st["Player_X_Speed"] = int.from_bytes(blk[off("Player_X_Speed"):off("Player_X_Speed") + 2], "big", signed=True)
    st["JumpOrigin_Y"] = int.from_bytes(blk[off("JumpOrigin_Y"):off("JumpOrigin_Y") + 2], "big")
    st["LastXHand"] = int.from_bytes(blk[off("Mario_LastXHand"):off("Mario_LastXHand") + 2], "big", signed=True)
    st["x_vel"] = int.from_bytes(sst[0x10:0x12], "big", signed=True)
    st["y_vel"] = int.from_bytes(sst[0x12:0x14], "big", signed=True)
    st["inertia"] = int.from_bytes(sst[0x14:0x16], "big", signed=True)
    st["y_pos"] = int.from_bytes(sst[0x0C:0x0E], "big")
    st["x_pos"] = int.from_bytes(sst[0x08:0x0A], "big")
    st["status"] = sst[0x22]
    st["angle"] = sst[0x26]
    st["routine"] = sst[0x24]
    return st


def seed(model, st):
    for n in BYTE_VARS:
        if hasattr(model, n):
            setattr(model, n, st[n])
    # apply any S2 change the ROM will fold in next frame (Mario_SyncXSpeed)
    speed_s2 = st["x_vel"] if st["status"] & 2 else st["inertia"]
    L = st["Player_X_Speed"] * 256 + st["Player_X_MoveForce"]
    L += ((speed_s2 - st["LastXHand"]) * S("Mario_S2ToXSpeed")) >> 5
    model.Player_X_Speed = (L >> 8) & 0xFF
    model.Player_X_MoveForce = L & 0xFF
    xs = abs(L >> 8)
    model.Player_XSpeedAbsolute = min(xs, 0xFF) if speed_s2 != st["LastXHand"] else st["Player_XSpeedAbsolute"]
    yv = int((st["y_vel"] * 256) / YSCALE) & 0xFFFF   # back to SMB1 units
    model.Player_Y_Speed, model.Player_Y_MoveForce = yv >> 8, yv & 0xFF


def compare(model, st):
    diffs = []
    for n in BYTE_VARS:
        if hasattr(model, n) and getattr(model, n) != st[n]:
            diffs.append(f"{n} rom={st[n]:#04x} ref={getattr(model, n):#04x}")
    if s8(model.Player_X_Speed) != st["Player_X_Speed"]:
        diffs.append(f"Player_X_Speed rom={st['Player_X_Speed']} ref={s8(model.Player_X_Speed)}")
    speed_s2 = st["x_vel"] if st["status"] & 2 else st["inertia"]
    # S2 must hold exactly the last speed Mario exchanged with it; when Mario wrote
    # it this frame (ground, or air with left/right held) that is Player_X_Speed * scale
    if speed_s2 != st["LastXHand"]:
        diffs.append(f"S2 speed {speed_s2:#x} != last exchanged {st['LastXHand']:#x}")
    wrote = not (st["status"] & 2) or st["Left_Right_Buttons"]
    if wrote and speed_s2 != st["Player_X_Speed"] * XSCALE:
        diffs.append(f"S2 speed {speed_s2:#x} != Player_X_Speed*{XSCALE}")
    if st["status"] & 2:  # airborne: y_vel is SMB1's Y_Speed:Y_MoveForce
        ref_yv = ((s8(model.Player_Y_Speed) * 256 + model.Player_Y_MoveForce) * YSCALE) >> 8
        if ref_yv != st["y_vel"]:
            diffs.append(f"y_vel rom={st['y_vel']:#06x} ref={ref_yv & 0xFFFF:#06x}")
    return diffs


compared = skipped = mismatched_frames = 0
log = []


def run(label, frames, spec=None):
    """Play `frames` frames with `spec` held, comparing ROM and model every frame."""
    global compared, skipped, mismatched_frames
    for i in range(frames):
        before = rom_state()
        on_ground = not (before["status"] & 2)
        rise = (before["JumpOrigin_Y"] - before["y_pos"]) & 0xFFFF
        # emu.frame() first finishes the frame already set up with the buttons
        # written by the previous call, then writes `spec` for the next frame.
        used = emu.held
        emu.frame(spec)
        model.frame(smb_joypad(used), on_ground, rise)
        after = emu_after_frame()
        flat = before["angle"] == 0 and after["angle"] == 0
        walls = (before["status"] | after["status"]) & 0x20 or after["inertia"] == 0 and before["inertia"] != 0 and not (after["status"] & 2) and model.Player_X_Speed != 0
        if not flat or walls or after["routine"] != 2:
            skipped += 1
            seed(model, after)
            continue
        compared += 1
        d = compare(model, after)
        if d:
            mismatched_frames += 1
            if len(log) < 40:
                log.append(f"[{label} f{i}] " + "; ".join(d))
            seed(model, after)  # keep going from the ROM's state


def emu_after_frame():
    # The breakpoint stops at the start of the next frame's joypad read, i.e.
    # after this frame's game logic ran - exactly the state we want.
    return rom_state()


try:
    boot_to_level(emu)
    emu.frames(60)  # stand still
    model = SMB1Player()
    seed(model, rom_state())
    model.Player_State = 0

    print("start x =", hex(rom_state()["x_pos"]), "angle", rom_state()["angle"])
    run("walk right", 50, "right")
    run("let go", 30)
    run("turn left (skid)", 25, "left")
    run("stop", 40)
    run("run right (A=run)", 45, "right|a")
    run("skid while running", 20, "left|a")
    run("stop", 40)
    run("standing jump, held", 50, "b")
    run("land", 20)
    run("short hop", 3, "b")
    run("short hop fall", 40)
    run("walk-jump", 20, "left")
    run("walk-jump", 45, "left|b")
    run("land", 25)
    run("run-jump", 40, "right|a")
    run("run-jump", 50, "right|a|b")
    run("land", 30, "right|a")
    run("crouch (small: no crouch)", 10, "down")
    run("down+right nullifies", 10, "down|right")
    run("stop", 30)
    emu.screenshot(os.path.join(OUT, "end.png"))
finally:
    emu.close()

for line in log:
    print(line)
print(f"\ncompared {compared} frames, skipped {skipped} (slopes/other), mismatched {mismatched_frames}")
sys.exit(1 if mismatched_frames else 0)
