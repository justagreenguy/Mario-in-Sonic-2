; ===========================================================================
; Mario physics - 68k translations of SMB1's player movement code
; ---------------------------------------------------------------------------
; Sources (smb1-disasm-master):
;   engine/game-mode/routine/player-control.asm  PlayerCtrlRoutine (input split)
;   engine/game-mode/player-movement.asm         PlayerMovementSubs, FallingSub,
;       JumpSwimSub, PlayerPhysicsSub, CheckForJumping, ProcJumping, X_Physics,
;       GetPlayerAnimSpeed, ImposeFriction, and the tables at 156-182
;   main.asm                                     MovePlayerVertically (4580),
;                                                ImposeGravity (4704)
;   system/nmi.asm                               frame timer countdown
;
; Units:
;   Player_X_Speed is SMB1's signed 4.4 speed (widened to a word);
;   S2 inertia/x_vel = Player_X_Speed << 4. Player_X_MoveForce is the extra
;   fraction ImposeFriction keeps below that.
;   SMB1's Y_Speed:Y_MoveForce is 8.8, i.e. exactly S2's y_vel.
;
; Not ported: ClimbingSub/Climb_* (S2 has no vines), Whirlpool_Flag,
; JumpspringAnimCtrl (S2 springs are objects), pipe-intro max speed.
; Swimming: SwimmingFlag comes from S2's water (Mario_SwimCheck).
; ===========================================================================

; ---------------------------------------------------------------------------
; Physics data - copied verbatim from player-movement.asm:156-182, 350
; Index 0-4: jump/run speed classes; 5: swimming; 6: whirlpool (unused here).
; ---------------------------------------------------------------------------
JumpMForceData:		dc.b $20, $20, $1E, $28, $28, $0D, $04
FallMForceData:		dc.b $70, $70, $60, $90, $90, $0A, $09
PlayerYSpdData:		dc.b $FC, $FC, $FC, $FB, $FB, $FE, $FF
InitMForceData:		dc.b $00, $00, $00, $00, $00, $80, $00
MaxLeftXSpdData:	dc.b $D8, $E8, $F0
MaxRightXSpdData:	dc.b $28, $18, $10
			dc.b $0C	; used for pipe intros (not used in S2)
FrictionData:		dc.b $E4, $98, $D0
PlayerAnimTmrData:	dc.b $02, $04, $07

; Luigi: SMB2J (threecreepio/smb2j-disassembly sm2main.asm, JumpFrictionData:
; "note luigi's higher jump, but with lesser friction"). SMB2J's LoadPhysicsData
; copies these over the three tables above and turns X_Physics' friction
; doubling (PhyOpcode) into an RTS; here the tables are picked by Mario_IsLuigi.
; Lower jump/fall forces = less gravity, so a higher jump with the same Y speed;
; lower friction = slower acceleration and deceleration (skidding further).
LuigiJumpMForceData:	dc.b $18, $18, $18, $22, $22, $0D, $04
LuigiFallMForceData:	dc.b $42, $42, $3E, $5D, $5D, $0A, $09
LuigiFrictionData:	dc.b $B4, $68, $A0
	even
	if (FallMForceData-JumpMForceData<>7)||(LuigiFallMForceData-LuigiJumpMForceData<>7)
		fatal "GetYPhy expects each FallMForceData 7 bytes after its JumpMForceData."
	endif

; port: the falling force a jump-less fall starts with (Mario_Init; also when
; swimming stops): FallMForceData[0] of the character being played.
Mario_InitFallForce:
	move.b	FallMForceData(pc),d0
	tst.b	(Mario_IsLuigi).w
	beq.s	+
	move.b	LuigiFallMForceData(pc),d0
+	move.b	d0,(VerticalForceDown).w
	move.b	d0,(VerticalForce).w
	rts

; ---------------------------------------------------------------------------
; SMB1 frame timers (nmi.asm: the NMI decrements $0780-$0794 every frame
; before the game logic runs). Only Mario's own timers are needed here.
; ---------------------------------------------------------------------------
Mario_FrameTimers:
	lea	(PlayerAnimTimer).w,a1	; PlayerAnimTimer, JumpSwimTimer, RunningTimer
	moveq	#3-1,d1
-	tst.b	(a1)
	beq.s	+
	subq.b	#1,(a1)
+	addq.w	#1,a1
	dbf	d1,-
	rts

; ---------------------------------------------------------------------------
; PlayerCtrlRoutine (player-control.asm:6-39)
; Builds SMB1's SavedJoypadBits from the Genesis pad, then splits it.
; Mapping: Genesis B = SMB1 A (jump), Genesis A = SMB1 B (run/fire).
; Genesis C doesn't jump (user, 2026-10-12): it is only the air-swim hold
; (Mario_SwimCheck), so holding it and pressing B is a clean stroke.
; ---------------------------------------------------------------------------
Mario_ReadJoypad:
	move.b	(Ctrl_1_Held_Logical).w,d0
	moveq	#0,d1
	btst	#button_right,d0
	beq.s	+
	ori.b	#Right_Dir,d1
+	btst	#button_left,d0
	beq.s	+
	ori.b	#Left_Dir,d1
+	btst	#button_down,d0
	beq.s	+
	ori.b	#Down_Dir,d1
+	btst	#button_up,d0
	beq.s	+
	ori.b	#Up_Dir,d1
+	btst	#button_start,d0
	beq.s	+
	ori.b	#%00010000,d1
+	btst	#button_A,d0
	beq.s	+
	ori.b	#B_Button,d1
+	btst	#button_B,d0
	beq.s	+
	ori.b	#A_Button,d1
+	tst.w	move_lock(a0)		; port: S2 locks the D-pad on the ground while sliding back
	beq.s	+			; down steep slopes (Sonic_Move); air control ignores it
	btst	#status.player.in_air,status(a0)
	bne.s	+
	andi.b	#~(Left_Dir|Right_Dir)&$FF,d1
+	move.b	d1,(SavedJoypadBits).w
; SaveJoyp:
	move.b	d1,d0
	andi.b	#%11000000,d0		; store A and B buttons
	move.b	d0,(A_B_Buttons).w
	move.b	d1,d0
	andi.b	#%00000011,d0		; store left and right buttons
	move.b	d0,(Left_Right_Buttons).w
	andi.b	#%00001100,d1		; store up and down buttons
	move.b	d1,(Up_Down_Buttons).w
	move.b	(Up_Down_Buttons).w,d1
	andi.b	#%00000100,d1		; check for pressing down
	beq.s	.done
	tst.b	(Player_State).w	; on the ground?
	bne.s	.done
	tst.b	(Left_Right_Buttons).w	; left or right also pressed?
	beq.s	.done
	clr.b	(Left_Right_Buttons).w	; if pressing down while on the ground,
	clr.b	(Up_Down_Buttons).w	; nullify directional bits
.done:
	rts

; ---------------------------------------------------------------------------
; PlayerMovementSubs, first part (player-movement.asm:2-11): crouch flag.
; Only big Mario crouches, and only while on the ground; in the air the flag
; is left as it was (SMB1's crouch-jump).
; ---------------------------------------------------------------------------
Mario_CrouchCheck:
	moveq	#0,d0			; init crouch flag by default
	tst.b	(PlayerSize).w		; is player small?
	bne.s	.set			; if so, branch
	tst.b	(Player_State).w	; if not on the ground, branch
	bne.s	.keep
	move.b	(Up_Down_Buttons).w,d0
	andi.b	#%00000100,d0		; single out bit for down button
.set:
	move.b	d0,(CrouchingFlag).w
.keep:
	rts

; ---------------------------------------------------------------------------
; port: SwimmingFlag. SMB1 sets it for a whole water-type area; here it is set
; while Mario is under S2's water (the underwater status bit), and also - user
; rule, so Mario can never be stranded - while he is airborne and C is held:
; then B presses are swim strokes in the air, and the surface line no longer
; holds him under the water (Mario_NearSurface).
; Forces: entering water gives the swim falling force, as if his last stroke
; had been in water (SMB1's falls in water areas use it); when swimming stops
; (out of the water, or C released in the air) swim forces go back to the
; falling force Mario starts with, so he doesn't drift down like a swimmer.
; ---------------------------------------------------------------------------
Mario_SwimCheck:
	moveq	#0,d2
	btst	#status.player.underwater,status(a0)
	beq.s	+
	moveq	#1,d2
	tst.b	(Mario_InWater).w	; just entered the water?
	bne.s	+
	move.b	FallMForceData+5(pc),(VerticalForceDown).w	; swim falling force
	st.b	(Mario_SwimForces).w
+	move.b	d2,(Mario_InWater).w
	moveq	#1,d1
	tst.b	d2			; in water: swimming
	bne.s	.set
	btst	#status.player.in_air,status(a0)
	beq.s	.dry
	btst	#button_C,(Ctrl_1_Held_Logical).w	; in the air with C held: swimming
	bne.s	.set
.dry:
	moveq	#0,d1
	tst.b	(Mario_SwimForces).w	; swim forces still in use?
	beq.s	.set
	clr.b	(Mario_SwimForces).w
	bsr.w	Mario_InitFallForce	; Mario_Init's falling force (keeps d1)
.set:
	move.b	d1,(SwimmingFlag).w
	rts

; ---------------------------------------------------------------------------
; port: SMB1's "Player_Y_Position < $14" test for a swimmer near the surface.
; Player_Y_Position is the top of Mario's 32 px box; the line is S2's water
; level + Mario_SwimSurface. Above it, JumpSwimSub's $18 force holds a
; swimmer at the surface, and a press is a normal jump out (ChkWtr). Only in
; real water, and not while C is held (the user's air-swimming rule: then
; Mario swims on out of the water).
; Returns Z clear (bne) if Mario is above the line. Uses d0-d1.
; ---------------------------------------------------------------------------
Mario_NearSurface:
	btst	#status.player.underwater,status(a0)
	beq.s	.no
	btst	#button_C,(Ctrl_1_Held_Logical).w
	bne.s	.no
	moveq	#0,d0
	move.b	y_radius(a0),d0
	add.w	y_pos(a0),d0
	subi.w	#32-1,d0		; top of the 32 px box: feet (y + radius + 1) - 32
	move.w	(Water_Level_1).w,d1
	addq.w	#Mario_SwimSurface,d1
	cmp.w	d1,d0
	blt.s	.yes
.no:
	moveq	#0,d0
	rts
.yes:
	moveq	#1,d0
	rts

; ---------------------------------------------------------------------------
; PlayerPhysicsSub / CheckForJumping / ProcJumping (player-movement.asm:184-288)
; (the climbing branch is not ported)
; ---------------------------------------------------------------------------
PlayerPhysicsSub:
CheckForJumping:
	move.b	(A_B_Buttons).w,d0	; check for A button press
	andi.b	#A_Button,d0
	beq.s	NoJump
	and.b	(PreviousA_B_Buttons).w,d0	; if button not pressed in previous frame, branch
	beq.s	ProcJumping
NoJump:
	bra.w	X_Physics		; otherwise, jump to something else

ProcJumping:
	tst.b	(Player_State).w	; if on the ground, branch
	beq.s	InitJS
	tst.b	(SwimmingFlag).w	; if swimming flag not set, prevent midair jumping
	beq.s	NoJump
	tst.b	(JumpSwimTimer).w	; if jump/swim timer nonzero, branch
	bne.s	InitJS_Swim
	tst.w	y_vel(a0)		; check player's vertical speed
	bpl.s	InitJS_Swim		; if motionless or moving down, branch
	bra.w	X_Physics		; if timer at zero and player still rising, do not swim
InitJS:
	; port: S2 needs headroom to leave the ground (same check as Sonic_Jump)
	moveq	#0,d0
	move.b	angle(a0),d0
	addi.b	#$80,d0
	jsr	(CalcRoomOverHead).l
	cmpi.w	#6,d1
	blt.s	NoJump
InitJS_Swim:
	move.b	#$20,(JumpSwimTimer).w	; set jump/swim timer
	move.w	y_pos(a0),(JumpOrigin_Y).w	; store vertical position of jump origin
	move.b	#1,(Player_State).w	; set player state to jumping/swimming
	st.b	(Mario_JumpStart).w	; port: tell the mode routine a jump started
	moveq	#0,d1			; Y
	move.b	(Player_XSpeedAbsolute).w,d0	; check value related to walking/running speed
	cmpi.b	#$09,d0
	blo.s	ChkWtr			; branch if below certain values, increment Y
	addq.w	#1,d1			; for each amount equal or exceeded
	cmpi.b	#$10,d0
	blo.s	ChkWtr
	addq.w	#1,d1
	cmpi.b	#$19,d0
	blo.s	ChkWtr
	addq.w	#1,d1
	cmpi.b	#$1C,d0
	blo.s	ChkWtr			; note that for jumping, range is 0-4 for Y
	addq.w	#1,d1
ChkWtr:
	move.b	#1,(DiffToHaltJump).w	; set value here (apparently always set to 1)
	clr.b	(Mario_SwimForces).w	; port: swim forces in use from now on? (not yet)
	tst.b	(SwimmingFlag).w	; if swimming flag disabled, branch
	beq.s	GetYPhy
	; port (user rule): SMB1 keeps a swimmer under the surface (Y speed zeroed
	; at "Player_Y_Position < $14"); S2's levels need Mario to get out, so at
	; the surface line he makes a normal jump out of the water instead.
	move.w	d1,-(sp)
	bsr.w	Mario_NearSurface
	movem.w	(sp)+,d1		; (movem: keeps the flags)
	bne.s	GetYPhy			; at the surface: jump data
	st.b	(Mario_SwimForces).w
	moveq	#5,d1			; otherwise set Y to 5 (no whirlpools in S2)
GetYPhy:
	lea	JumpMForceData(pc),a1	; store appropriate jump/swim data
	tst.b	(Mario_IsLuigi).w	; (SMB2J: Luigi's data, see LuigiJumpMForceData)
	beq.s	+
	lea	LuigiJumpMForceData(pc),a1
+	move.b	(a1,d1.w),(VerticalForce).w
	move.b	FallMForceData-JumpMForceData(a1,d1.w),(VerticalForceDown).w
	lea	PlayerYSpdData(pc),a1
	move.b	(a1,d1.w),d0		; Player_Y_Speed
	lsl.w	#8,d0
	lea	InitMForceData(pc),a1
	move.b	(a1,d1.w),d0		; Player_Y_MoveForce
	move.w	d0,(Mario_JumpSpeed).w	; port: applied to y_vel by the mode routine
	tst.b	(Mario_SwimForces).w	; if swimming flag disabled (port: or jumping out), branch
	beq.s	PJumpSnd
	move.b	#SndID_MarioSwimStomp,(Sound_Queue.SFX2).w	; load swim/goomba stomp sound (3rd queue slot)
	; (SMB1's surface clamp is replaced by the jump out, above)
	bra.s	X_Physics
PJumpSnd:
	move.b	#SndID_MarioBigJump,d0	; load big mario's jump sound by default
	tst.b	(PlayerSize).w		; is mario big?
	beq.s	SJumpSnd
	move.b	#SndID_MarioSmallJump,d0	; if not, load small mario's jump sound
SJumpSnd:
	move.b	d0,(Sound_Queue.SFX2).w	; store appropriate jump sound (3rd queue slot, as Mario's other sounds)

; ---------------------------------------------------------------------------
; X_Physics (player-movement.asm:289-346): choose maximum speeds and friction.
; AreaType = water is taken to mean "underwater" in S2.
; ---------------------------------------------------------------------------
X_Physics:
	moveq	#0,d1			; Y
	moveq	#0,d2			; $00
	tst.b	(Player_State).w	; if mario is on the ground, branch
	beq.s	ProcPRun
	cmpi.b	#$19,(Player_XSpeedAbsolute).w	; check mario's speed
	bhs.s	GetXPhy			; if =>$19 branch here
	bra.s	ChkRFast		; if not branch elsewhere
ProcPRun:
	addq.w	#1,d1			; if mario on the ground, increment Y
	btst	#status.player.underwater,status(a0)	; water type area?
	bne.s	ChkRFast		; if so, branch
	subq.w	#1,d1			; decrement Y by default for non-water type area
	move.b	(Left_Right_Buttons).w,d0	; get left/right controller bits
	cmp.b	(Player_MovingDir).w,d0	; check against moving direction
	bne.s	ChkRFast		; if controller bits <> moving direction, skip this part
	move.b	(A_B_Buttons).w,d0
	andi.b	#B_Button,d0		; check for b button pressed
	bne.s	SetRTmr			; if pressed, skip ahead to set timer
	tst.b	(RunningTimer).w	; check for running timer set
	bne.s	GetXPhy			; if set, branch
ChkRFast:
	addq.w	#1,d1			; if running timer not set or level type is water,
	addq.w	#1,d2			; increment Y again and temp variable in memory
	tst.b	(RunningSpeed).w
	bne.s	FastXSp			; if running speed set here, branch
	cmpi.b	#$21,(Player_XSpeedAbsolute).w	; otherwise check player's walking/running speed
	blo.s	GetXPhy			; if less than a certain amount, branch ahead
FastXSp:
	addq.w	#1,d2			; if running speed set or speed => $21 increment $00
	bra.s	GetXPhy
SetRTmr:
	move.b	#$0A,(RunningTimer).w	; if b button pressed, set running timer
GetXPhy:
	lea	MaxLeftXSpdData(pc),a1	; get maximum speed to the left
	move.b	(a1,d1.w),(MaximumLeftSpeed).w
	lea	MaxRightXSpdData(pc),a1	; get maximum speed to the right
	move.b	(a1,d1.w),(MaximumRightSpeed).w
	lea	FrictionData(pc),a1	; get friction using $00 as offset
	tst.b	(Mario_IsLuigi).w	; (SMB2J: Luigi's data)
	beq.s	+
	bsr.w	Luigi_Uphill		; port: uphill he uses Mario's
	bne.s	+
	lea	LuigiFrictionData(pc),a1
+	move.b	(a1,d2.w),(FrictionAdderLow).w
	clr.b	(FrictionAdderHigh).w
	tst.b	(Mario_IsLuigi).w	; SMB2J: PhyOpcode is an RTS for Luigi, so his
	beq.s	+			; friction is never doubled when turning
	bsr.w	Luigi_Uphill		; (port: except uphill, where he is Mario)
	beq.s	ExitPhy
+	move.b	(PlayerFacingDir).w,d0
	cmp.b	(Player_MovingDir).w,d0	; check facing direction against moving direction
	beq.s	ExitPhy			; if the same, branch to leave
	moveq	#0,d0			; otherwise double the friction adder:
	move.b	(FrictionAdderLow).w,d0	; asl FrictionAdderLow / rol FrictionAdderHigh
	add.w	d0,d0
	move.b	d0,(FrictionAdderLow).w
	lsr.w	#8,d0
	move.b	d0,(FrictionAdderHigh).w
ExitPhy:
	; port: S2 speed shoes double the maximum speeds and the friction adder
	btst	#status_secondary.speed_shoes,status_secondary(a0)
	beq.s	+
	move.b	(MaximumLeftSpeed).w,d0
	add.b	d0,d0
	move.b	d0,(MaximumLeftSpeed).w
	move.b	(MaximumRightSpeed).w,d0
	add.b	d0,d0
	move.b	d0,(MaximumRightSpeed).w
	move.b	(FrictionAdderHigh).w,d0
	lsl.w	#8,d0
	move.b	(FrictionAdderLow).w,d0
	add.w	d0,d0
	move.b	d0,(FrictionAdderLow).w
	lsr.w	#8,d0
	move.b	d0,(FrictionAdderHigh).w
+	rts

; ---------------------------------------------------------------------------
; port (user tuning, 2026-10-10): SMB2J's Luigi accelerates more slowly than
; Mario ($B4/$68 vs $E4/$98), so S2's slope resistance ($20 at most,
; Sonic_SlopeResist) stopped him on slopes Mario can climb (running: ~32
; degrees vs ~42). While he is on the ground pushing up a slope steeper than
; Luigi_UphillAngle, he uses Mario's friction data and doubling instead;
; flat ground and downhill keep SMB2J's.
; S2 angles: $01-$7F rise to the left, $81-$FF rise to the right.
; Returns Z clear if uphill. Uses d0.
; ---------------------------------------------------------------------------
Luigi_UphillAngle = $08			; about 11 degrees

Luigi_Uphill:
	tst.b	(Player_State).w	; on the ground?
	bne.s	.no
	move.b	(Left_Right_Buttons).w,d0
	beq.s	.no			; not pushing
	move.b	angle(a0),d0
	btst	#0,(Left_Right_Buttons).w	; pushing right?
	beq.s	+
	neg.b	d0			; right: uphill when the angle is -$08..-$78
+	subq.b	#Luigi_UphillAngle,d0
	cmpi.b	#$80-2*Luigi_UphillAngle,d0
	bhs.s	.no
	moveq	#1,d0			; Z clear: uphill
	rts
.no:
	moveq	#0,d0			; Z set
	rts

; port: the soft-cap speed (Mario_MaxSMBSpeed, doubled with speed shoes) in d3.w
Mario_SoftCap:
	moveq	#Mario_MaxSMBSpeed,d3
	btst	#status_secondary.speed_shoes,status_secondary(a0)
	beq.s	+
	add.w	d3,d3
+	rts

; ---------------------------------------------------------------------------
; OnGroundStateSub (player-movement.asm:35-44)
; MovePlayerHorizontally is S2's job (Obj01_Traction + ObjectMove).
; ---------------------------------------------------------------------------
OnGroundStateSub:
	bsr.w	GetPlayerAnimSpeed	; set animation frame timing
	move.b	(Left_Right_Buttons).w,d0
	beq.s	GndMove			; if left/right controller bits not set, skip
	move.b	d0,(PlayerFacingDir).w	; otherwise set new facing direction
GndMove:
	; port: while S2 has Mario sliding (e.g. OOZ oil), the ground speed is S2's
	btst	#status_secondary.sliding,status_secondary(a0)
	bne.s	+
	move.b	(Left_Right_Buttons).w,d0
	bsr.w	ImposeFriction		; impose friction on player's walk/run
+	rts

; ---------------------------------------------------------------------------
; FallingSub / JumpSwimSub (player-movement.asm:48-96)
; The actual movement (MovePlayerHorizontally/Vertically) is done afterwards
; by Mario_AirMove, so these end where SMB1 would start moving.
; ---------------------------------------------------------------------------
FallingSub:
	move.b	(VerticalForceDown).w,(VerticalForce).w	; dump falling force into main one
	bra.s	LRAir

JumpSwimSub:
	tst.w	y_vel(a0)		; if player's vertical speed zero
	bpl.s	DumpFall		; or moving downwards, branch to falling
	move.b	(A_B_Buttons).w,d0
	andi.b	#A_Button,d0		; check to see if A button is being pressed
	and.b	(PreviousA_B_Buttons).w,d0	; and was pressed in previous frame
	bne.s	ProcSwim		; if so, branch elsewhere
	move.w	(JumpOrigin_Y).w,d0	; get vertical position player jumped from
	sub.w	y_pos(a0),d0		; subtract current from original vertical coordinate
	cmp.b	(DiffToHaltJump).w,d0	; compare to value set here to see if player is in mid-jump
	blo.s	ProcSwim		; or just starting to jump, if just starting, skip ahead
DumpFall:
	move.b	(VerticalForceDown).w,(VerticalForce).w	; otherwise dump falling into main fractional
ProcSwim:
	tst.b	(Mario_SwimForces).w	; if swimming flag not set (port: not swimming yet, see Mario_SwimForces),
	beq.s	LRAir			; branch ahead to last part
	bsr.w	GetPlayerAnimSpeed	; get animation frame timing
	bsr.w	Mario_NearSurface	; check vertical position against preset value
	beq.s	LRWater			; if not yet reached a certain position, branch ahead
	move.b	#$18,(VerticalForce).w	; otherwise set fractional
LRWater:
	move.b	(Left_Right_Buttons).w,d0	; check left/right controller bits (check for swimming)
	beq.s	LRAir			; if not pressing any, skip
	move.b	d0,(PlayerFacingDir).w	; otherwise set facing direction accordingly
LRAir:
	move.b	(Left_Right_Buttons).w,d0	; check left/right controller bits (check for jumping/falling)
	beq.s	JSMove			; if not pressing any, skip
	bsr.w	ImposeFriction		; otherwise process horizontal movement
	bsr.w	Mario_XSpeedForS2	; port: hand the new speed to S2
	move.w	d0,x_vel(a0)
JSMove:
	rts

; ---------------------------------------------------------------------------
; GetPlayerAnimSpeed (player-movement.asm:350-385)
; ---------------------------------------------------------------------------
GetPlayerAnimSpeed:
	moveq	#0,d1			; initialize offset in Y
	move.b	(Player_XSpeedAbsolute).w,d0	; check player's walking/running speed
	cmpi.b	#$1C,d0			; against preset amount
	bhs.s	SetRunSpd		; if greater than a certain amount, branch ahead
	addq.w	#1,d1			; otherwise increment Y
	cmpi.b	#$0E,d0			; compare against lower amount
	bhs.s	ChkSkid			; if greater than this but not greater than first, skip increment
	addq.w	#1,d1			; otherwise increment Y again
ChkSkid:
	move.b	(SavedJoypadBits).w,d0	; get controller bits
	andi.b	#%01111111,d0		; mask out A button
	beq.s	SetAnimSpd		; if no other buttons pressed, branch ahead of all this
	andi.b	#$03,d0			; mask out all others except left and right
	cmp.b	(Player_MovingDir).w,d0	; check against moving direction
	bne.s	ProcSkid		; if left/right controller bits <> moving direction, branch
	moveq	#0,d0			; otherwise set zero value here
SetRunSpd:
	move.b	d0,(RunningSpeed).w	; store zero or running speed here
	bra.s	SetAnimSpd
ProcSkid:
	cmpi.b	#$0B,(Player_XSpeedAbsolute).w	; check player's walking/running speed
	bhs.s	SetAnimSpd		; if greater than this amount, branch
	move.b	(PlayerFacingDir).w,(Player_MovingDir).w	; use facing direction to set moving direction
	clr.w	(Player_X_Speed).w	; nullify player's horizontal speed
	clr.b	(Player_X_MoveForce).w	; and dummy variable for player
SetAnimSpd:
	lea	PlayerAnimTmrData(pc),a1	; get animation timer setting using Y as offset
	move.b	(a1,d1.w),(PlayerAnimTimerSet).w
	rts

; ---------------------------------------------------------------------------
; ImposeFriction (player-movement.asm:389-433)
; Input: d0.b = left/right controller bits.
; The 6502 adds/subtracts FrictionAdderHigh:Low to Player_X_Speed:
; Player_X_MoveForce as one 16-bit number; here that is a 32-bit value
; (Player_X_Speed is a word) so S2-sized speeds don't wrap.
; ---------------------------------------------------------------------------
ImposeFriction:
	; (and Player_CollisionBits: S2 does its own wall collision, so all directions are open)
	tst.b	d0
	bne.s	JoypFrict		; if any bits set, branch to next part
	move.w	(Player_X_Speed).w,d1
	beq.w	SetAbsSpd		; if player has no horizontal speed, branch ahead to last part
	bpl.s	RghtFrict		; if player moving to the right, branch to slow
	bra.s	LeftFrict		; otherwise logic dictates player moving left, branch to slow
JoypFrict:
	lsr.b	#1,d0			; put right controller bit into carry
	bcc.s	RghtFrict		; if left button pressed, carry = 0, thus branch
LeftFrict:
	; port (hybrid soft cap): already moving right faster than SMB1 ever does
	; (S2 slope/spring)? Then neither accelerate nor clamp - keep the speed.
	bsr.w	Mario_SoftCap
	move.w	(Player_X_Speed).w,d1
	cmp.w	d3,d1
	bgt.s	XSpdSign
	bsr.s	Mario_LoadXSpeed32
	add.l	d2,d1			; add FrictionAdder to Player_X_Speed:Player_X_MoveForce
	bsr.s	Mario_StoreXSpeed32
	move.b	(MaximumRightSpeed).w,d2
	ext.w	d2
	cmp.w	d2,d1			; compare against maximum value for right movement
	blt.s	XSpdSign		; if less, keep it
	move.w	d2,(Player_X_Speed).w	; otherwise set preset value as horizontal speed
	move.w	d2,d1
	bra.s	SetAbsSpd		; skip to the end
RghtFrict:
	bsr.w	Mario_SoftCap		; port (hybrid soft cap), mirrored
	neg.w	d3
	move.w	(Player_X_Speed).w,d1
	cmp.w	d3,d1
	blt.s	XSpdSign
	bsr.s	Mario_LoadXSpeed32
	sub.l	d2,d1			; subtract FrictionAdder from Player_X_Speed:Player_X_MoveForce
	bsr.s	Mario_StoreXSpeed32
	move.b	(MaximumLeftSpeed).w,d2
	ext.w	d2
	cmp.w	d2,d1			; compare against maximum value for left movement
	bge.s	XSpdSign		; if greater positively, keep it
	move.w	d2,(Player_X_Speed).w	; otherwise set preset value as horizontal speed
	move.w	d2,d1
XSpdSign:
SetAbsSpd:
	; store absolute walking/running speed (capped to a byte: SMB1 thresholds are all < $FF)
	tst.w	d1
	bpl.s	+
	neg.w	d1
+	cmpi.w	#$FF,d1
	bls.s	+
	move.w	#$FF,d1
+	move.b	d1,(Player_XSpeedAbsolute).w
	rts

; d1.l = Player_X_Speed:Player_X_MoveForce (signed, 24 bits used);
; d2.l = FrictionAdderHigh:FrictionAdderLow
Mario_LoadXSpeed32:
	move.w	(Player_X_Speed).w,d1
	ext.l	d1
	asl.l	#8,d1
	move.b	(Player_X_MoveForce).w,d1
	moveq	#0,d2
	move.b	(FrictionAdderHigh).w,d2
	lsl.w	#8,d2
	move.b	(FrictionAdderLow).w,d2
	rts

; Store d1.l back into Player_X_Speed:Player_X_MoveForce; returns d1.w = Player_X_Speed
Mario_StoreXSpeed32:
	move.b	d1,(Player_X_MoveForce).w
	asr.l	#8,d1
	move.w	d1,(Player_X_Speed).w
	rts

; ---------------------------------------------------------------------------
; port: SMB1 -> S2 speed conversions (see Mario_XSpeedToS2 / Mario_YScale).
; ---------------------------------------------------------------------------
; d0.w = Player_X_Speed in S2 units (inertia/x_vel); the caller writes it to S2,
; and it is remembered as the last value exchanged (Mario_LastXHand)
Mario_XSpeedForS2:
	move.w	(Player_X_Speed).w,d0
	muls.w	#Mario_XSpeedToS2,d0
	move.w	d0,(Mario_LastXHand).w
	rts

; d0.w = d0.w (an SMB1 8.8 vertical value) scaled by Mario_YScale
Mario_YForS2:
	muls.w	#Mario_YScale,d0
	asr.l	#8,d0
	rts

; ---------------------------------------------------------------------------
; port: fold S2's changes to Mario's speed back into the SMB1 variables.
; Input: d0.w = S2's current speed (inertia on the ground, x_vel in the air).
; The difference from the last value exchanged (Mario_LastXHand) was made by
; S2 (slopes, springs, walls, landing, ground->air projection); it is converted
; back and added to Player_X_Speed:Player_X_MoveForce exactly once.
; ---------------------------------------------------------------------------
Mario_SyncXSpeed:
	move.w	d0,d2
	sub.w	(Mario_LastXHand).w,d2	; S2's change since the last exchange
	beq.s	.done
	move.w	d0,(Mario_LastXHand).w	; accounted for
	move.w	(Player_X_Speed).w,d1
	ext.l	d1
	asl.l	#8,d1
	move.b	(Player_X_MoveForce).w,d1
	muls.w	#Mario_S2ToXSpeed,d2	; S2 units -> Xs:MF units (x32)
	asr.l	#5,d2
	add.l	d2,d1
	bsr.s	Mario_StoreXSpeed32
	bra.w	SetAbsSpd		; keep Player_XSpeedAbsolute current
.done:
	rts

; ---------------------------------------------------------------------------
; MovePlayerVertically / ImposeGravity (main.asm:4580, 4704), after S2's
; ObjectMove has moved Mario by his current speed (SMB1 also moves first,
; then adds the force). Maximum vertical speed 4.
; port: while Mario_LaunchFlag is set (airborne from an S2 spring/launcher,
; not his own jump) S2's gravity is used until the apex, so S2's gimmicks
; reach the heights their levels were designed for.
; ---------------------------------------------------------------------------
MovePlayerVertically:
	tst.b	(Mario_LaunchFlag).w
	beq.s	.smb
	tst.w	y_vel(a0)
	bpl.s	.apex
	addi.w	#$38,y_vel(a0)		; S2 gravity (ObjectMoveAndFall)
	btst	#status.player.underwater,status(a0)
	beq.s	+
	subi.w	#$28,y_vel(a0)		; S2 underwater gravity ($38-$28=$10)
+	rts
.apex:
	clr.b	(Mario_LaunchFlag).w
.smb:
	moveq	#0,d0
	move.b	(VerticalForce).w,d0
	bsr.w	Mario_YForS2		; port: scaled by Mario_YScale
	add.w	d0,y_vel(a0)		; add downward force to Y_Speed:Y_MoveForce
	; maximum speed check, done in SMB1 units (y_vel / Mario_YScale)
	move.w	y_vel(a0),d0
	ext.l	d0
	asl.l	#8,d0
	divs.w	#Mario_YScale,d0
	bvs.s	.cap			; (only for absurd S2 speeds: treat as over the cap)
	cmpi.w	#$0400,d0		; Y_Speed compared to maximum speed (4)
	blt.s	.done			; if less than preset value, skip this part
	cmpi.b	#$80,d0			; Y_MoveForce: if less than $80, skip this part
	blo.s	.done
.cap:
	tst.w	y_vel(a0)		; (the overflow case can also be a huge upward speed)
	bmi.s	.done
	move.w	#$0400,d0		; keep vertical speed within maximum value, clear fractional
	bsr.w	Mario_YForS2
	move.w	d0,y_vel(a0)
.done:
	rts
