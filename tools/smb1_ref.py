#!/usr/bin/env python3
"""
smb1_ref.py - reference model of SMB1's player movement, transliterated
line by line from the 6502 (8-bit registers, carry, wraparound) so it can be
compared frame by frame against the 68k port.

Covers: frame timers (nmi.asm), PlayerCtrlRoutine input split, PlayerMovementSubs
(crouch flag), PlayerPhysicsSub/CheckForJumping/ProcJumping/X_Physics,
OnGroundStateSub/GetPlayerAnimSpeed/ImposeFriction, FallingSub/JumpSwimSub/LRAir,
MovePlayerVertically/ImposeGravity (speed only), PlayerCtrlRoutine:ChkMoveDir,
and GameEngine's PreviousA_B_Buttons save. Not covered: climbing, swimming,
whirlpools, jumpsprings, background collision (supplied by the caller).

Positions are not modelled; JumpSwimSub needs (JumpOrigin_Y - Y_Position),
which the caller supplies each frame as `rise` (the low byte is what SMB1 uses).
"""

JumpMForceData = [0x20, 0x20, 0x1E, 0x28, 0x28, 0x0D, 0x04]
FallMForceData = [0x70, 0x70, 0x60, 0x90, 0x90, 0x0A, 0x09]
PlayerYSpdData = [0xFC, 0xFC, 0xFC, 0xFB, 0xFB, 0xFE, 0xFF]
InitMForceData = [0x00, 0x00, 0x00, 0x00, 0x00, 0x80, 0x00]
MaxLeftXSpdData = [0xD8, 0xE8, 0xF0]
MaxRightXSpdData = [0x28, 0x18, 0x10, 0x0C]
FrictionData = [0xE4, 0x98, 0xD0]
PlayerAnimTmrData = [0x02, 0x04, 0x07]

A_Button, B_Button = 0x80, 0x40


def s8(v):
    v &= 0xFF
    return v - 256 if v & 0x80 else v


class SMB1Player:
    def __init__(self):
        self.Player_X_Speed = 0
        self.Player_X_MoveForce = 0
        self.Player_Y_Speed = 0
        self.Player_Y_MoveForce = 0
        self.Player_State = 0
        self.PlayerSize = 1
        self.PlayerFacingDir = 1
        self.Player_MovingDir = 1
        self.Player_XSpeedAbsolute = 0
        self.CrouchingFlag = 0
        self.SwimmingFlag = 0
        self.FrictionAdderHigh = 0
        self.FrictionAdderLow = 0
        self.MaximumLeftSpeed = 0
        self.MaximumRightSpeed = 0
        self.RunningSpeed = 0
        self.VerticalForce = 0x70
        self.VerticalForceDown = 0x70
        self.DiffToHaltJump = 0
        self.PlayerAnimTimer = 0
        self.JumpSwimTimer = 0
        self.RunningTimer = 0
        self.PlayerAnimTimerSet = 0
        self.SavedJoypadBits = 0
        self.A_B_Buttons = 0
        self.PreviousA_B_Buttons = 0
        self.Up_Down_Buttons = 0
        self.Left_Right_Buttons = 0
        self.water = False
        self.jumped = False  # set when ProcJumping ran this frame

    # ---- 6502-ish helpers on unsigned bytes ----
    def frame(self, joypad, on_ground, rise):
        """
        joypad: SMB1 bit layout. on_ground: background collision result from the
        previous frame (S2 supplies it). rise: JumpOrigin_Y - Y_Position (int).
        """
        # nmi.asm: frame timers count down
        for t in ("PlayerAnimTimer", "JumpSwimTimer", "RunningTimer"):
            if getattr(self, t):
                setattr(self, t, getattr(self, t) - 1)
        # PlayerBGCollision results (landing / leaving the ground)
        if on_ground:
            if self.Player_State != 0:
                self.Player_Y_Speed = 0
                self.Player_Y_MoveForce = 0
            self.Player_State = 0
        elif self.Player_State == 0:
            self.Player_State = 2
        self.jumped = False
        self.SavedJoypadBits = joypad & 0xFF
        self.PlayerCtrlRoutine(rise)
        # GameEngine: save A/B for next frame
        self.PreviousA_B_Buttons = self.A_B_Buttons

    def PlayerCtrlRoutine(self, rise):
        a = self.SavedJoypadBits
        self.A_B_Buttons = a & 0xC0
        self.Left_Right_Buttons = a & 0x03
        self.Up_Down_Buttons = a & 0x0C
        if (self.Up_Down_Buttons & 0x04) and self.Player_State == 0 and self.Left_Right_Buttons:
            self.Left_Right_Buttons = 0
            self.Up_Down_Buttons = 0
        self.PlayerMovementSubs(rise)
        # ChkMoveDir
        if self.Player_X_Speed != 0:
            self.Player_MovingDir = 1 if self.Player_X_Speed < 0x80 else 2

    def PlayerMovementSubs(self, rise):
        if self.PlayerSize != 0:
            self.CrouchingFlag = 0
        elif self.Player_State == 0:
            self.CrouchingFlag = self.Up_Down_Buttons & 0x04
        self.PlayerPhysicsSub()
        st = self.Player_State
        if st == 0:
            self.OnGroundStateSub()
        elif st == 1:
            self.JumpSwimSub(rise)
        elif st == 2:
            self.FallingSub()

    def PlayerPhysicsSub(self):
        # CheckForJumping
        if (self.A_B_Buttons & A_Button) and not (self.A_B_Buttons & A_Button & self.PreviousA_B_Buttons):
            if self.ProcJumping():
                return
        self.X_Physics()

    def ProcJumping(self):
        """returns True if it already ran X_Physics (always does in SMB1)."""
        if self.Player_State != 0:
            if not self.SwimmingFlag:
                return False
            if self.JumpSwimTimer == 0 and s8(self.Player_Y_Speed) < 0:
                return False
        # InitJS
        self.JumpSwimTimer = 0x20
        y = 0
        self.Player_Y_MoveForce = 0
        self.Player_State = 1
        self.jumped = True
        a = self.Player_XSpeedAbsolute
        for thr in (0x09, 0x10, 0x19, 0x1C):
            if a < thr:
                break
            y += 1
        self.DiffToHaltJump = 1
        if self.SwimmingFlag:
            y = 5
        self.VerticalForce = JumpMForceData[y]
        self.VerticalForceDown = FallMForceData[y]
        self.Player_Y_MoveForce = InitMForceData[y]
        self.Player_Y_Speed = PlayerYSpdData[y]
        self.X_Physics()
        return True

    def X_Physics(self):
        y = 0
        d00 = 0
        if self.Player_State != 0:
            if self.Player_XSpeedAbsolute >= 0x19:
                return self.GetXPhy(y, d00)
            # ChkRFast
        else:
            y += 1
            if not self.water:
                y -= 1
                if self.Left_Right_Buttons == self.Player_MovingDir:
                    if self.A_B_Buttons & B_Button:
                        self.RunningTimer = 0x0A
                        return self.GetXPhy(y, d00)
                    if self.RunningTimer:
                        return self.GetXPhy(y, d00)
        # ChkRFast
        y += 1
        d00 += 1
        if self.RunningSpeed or self.Player_XSpeedAbsolute >= 0x21:
            d00 += 1
        return self.GetXPhy(y, d00)

    def GetXPhy(self, y, d00):
        self.MaximumLeftSpeed = MaxLeftXSpdData[y]
        self.MaximumRightSpeed = MaxRightXSpdData[y]
        self.FrictionAdderLow = FrictionData[d00]
        self.FrictionAdderHigh = 0
        if self.PlayerFacingDir != self.Player_MovingDir:
            v = self.FrictionAdderLow << 1
            self.FrictionAdderLow = v & 0xFF
            self.FrictionAdderHigh = (self.FrictionAdderHigh << 1 | (v >> 8)) & 0xFF

    def OnGroundStateSub(self):
        self.GetPlayerAnimSpeed()
        if self.Left_Right_Buttons:
            self.PlayerFacingDir = self.Left_Right_Buttons
        self.ImposeFriction(self.Left_Right_Buttons)

    def FallingSub(self):
        self.VerticalForce = self.VerticalForceDown
        self.LRAir()

    def JumpSwimSub(self, rise):
        dump = False
        if s8(self.Player_Y_Speed) >= 0:
            dump = True
        elif self.A_B_Buttons & A_Button & self.PreviousA_B_Buttons:
            dump = False
        elif ((0 if self.jumped else rise) & 0xFF) < self.DiffToHaltJump:
            # (InitJS just stored JumpOrigin_Y = Y_Position this frame, so the rise is 0)
            dump = False
        else:
            dump = True
        if dump:
            self.VerticalForce = self.VerticalForceDown
        self.LRAir()

    def LRAir(self):
        if self.Left_Right_Buttons:
            self.ImposeFriction(self.Left_Right_Buttons)
        self.MovePlayerVertically()

    def GetPlayerAnimSpeed(self):
        y = 0
        a = self.Player_XSpeedAbsolute
        if a >= 0x1C:
            self.RunningSpeed = a
        else:
            y += 1
            if a < 0x0E:
                y += 1
            j = self.SavedJoypadBits & 0x7F
            if j:
                j &= 0x03
                if j == self.Player_MovingDir:
                    self.RunningSpeed = 0
                else:
                    if self.Player_XSpeedAbsolute < 0x0B:
                        self.Player_MovingDir = self.PlayerFacingDir
                        self.Player_X_Speed = 0
                        self.Player_X_MoveForce = 0
        self.PlayerAnimTimerSet = PlayerAnimTmrData[y]

    def ImposeFriction(self, a):
        # and Player_CollisionBits -> all open
        if a == 0:
            if self.Player_X_Speed == 0:
                self.Player_XSpeedAbsolute = 0
                return
            right = self.Player_X_Speed >= 0x80  # bmi LeftFrict when negative
            left_frict = right  # negative speed -> LeftFrict (add)
        else:
            left_frict = bool(a & 1)  # right pressed -> LeftFrict
        if left_frict:
            v = self.Player_X_MoveForce + self.FrictionAdderLow
            self.Player_X_MoveForce = v & 0xFF
            c = v >> 8
            self.Player_X_Speed = (self.Player_X_Speed + self.FrictionAdderHigh + c) & 0xFF
            # cmp MaximumRightSpeed / bmi XSpdSign: bit 7 of the difference
            if ((self.Player_X_Speed - self.MaximumRightSpeed) & 0x80) == 0:
                self.Player_X_Speed = self.MaximumRightSpeed
                self.Player_XSpeedAbsolute = self.MaximumRightSpeed  # jmp SetAbsSpd with A = max
                return
        else:
            v = self.Player_X_MoveForce - self.FrictionAdderLow
            self.Player_X_MoveForce = v & 0xFF
            borrow = 1 if v < 0 else 0
            self.Player_X_Speed = (self.Player_X_Speed - self.FrictionAdderHigh - borrow) & 0xFF
            if ((self.Player_X_Speed - self.MaximumLeftSpeed) & 0x80) != 0:  # bpl not taken
                self.Player_X_Speed = self.MaximumLeftSpeed
        # XSpdSign
        a = self.Player_X_Speed
        if a & 0x80:
            a = (-a) & 0xFF
        self.Player_XSpeedAbsolute = a

    def MovePlayerVertically(self):
        # ImposeGravity (speed part): Y_MoveForce += VerticalForce, carry into Y_Speed
        v = self.Player_Y_MoveForce + self.VerticalForce
        self.Player_Y_MoveForce = v & 0xFF
        self.Player_Y_Speed = (self.Player_Y_Speed + (v >> 8)) & 0xFF
        # cmp $02 (4) / bmi ChkUpM : bit 7 of (Y_Speed - 4)
        if ((self.Player_Y_Speed - 4) & 0x80) == 0 and self.Player_Y_MoveForce >= 0x80:
            self.Player_Y_Speed = 4
            self.Player_Y_MoveForce = 0
