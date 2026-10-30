; ===========================================================================
; Mario glue - adapters between the SMB1 routines and the S2 engine
; ---------------------------------------------------------------------------
; The mode routines below run SMB1's PlayerMovementSubs logic, then S2's
; terrain collision (AnglePos / Sonic_DoLevelCollision) in place of SMB1's
; PlayerBGCollision. Speeds are exchanged with S2 through Mario_SyncXSpeed
; (S2 -> SMB1) and "inertia/x_vel = Player_X_Speed << 4" (SMB1 -> S2).
; ===========================================================================

; ---------------------------------------------------------------------------
; Bring SMB1's Player_State in line with S2's status at the start of a frame.
; S2 decides when Mario lands or leaves the ground (PlayerBGCollision's job
; in SMB1). In the air, a y_vel that differs from what Mario's own code left
; last frame means S2 moved him (spring, tube exit, bumper, launcher) -
; even mid-jump - so he becomes "falling" (state 2), and if that sends him
; upward it's a launch: S2 gravity until the apex (MovePlayerVertically).
; Leaving the ground without jumping is also falling.
; ---------------------------------------------------------------------------
Mario_SyncState:
	; facing: Mario_SetDirections wrote x_flip from PlayerFacingDir last frame,
	; so a different x_flip now means S2 turned him (springs, etc.): adopt it
	moveq	#1,d0
	btst	#status.player.x_flip,status(a0)
	beq.s	+
	moveq	#2,d0
+	move.b	d0,(PlayerFacingDir).w
	btst	#status.player.in_air,status(a0)
	bne.s	.air
	clr.b	(Player_State).w	; on the ground
	clr.b	(Mario_LaunchFlag).w
	rts
.air:
	move.w	y_vel(a0),d0
	cmp.w	(Mario_LastYVel).w,d0	; did S2 change Mario's vertical speed?
	bne.s	.external
	tst.b	(Player_State).w	; left the ground without jumping?
	bne.s	.done
.external:
	move.b	#2,(Player_State).w	; falling (SMB1 FallingSub)
	tst.w	d0
	bpl.s	.done
	st.b	(Mario_LaunchFlag).w	; launched upward by S2: S2 gravity until the apex
.done:
	rts

; ---------------------------------------------------------------------------
; PlayerCtrlRoutine:ChkMoveDir (player-control.asm:51-57) plus facing -> S2.
; ---------------------------------------------------------------------------
Mario_SetDirections:
	move.w	(Player_X_Speed).w,d0	; check player's horizontal speed
	beq.s	.facing			; if not moving at all horizontally, skip this part
	moveq	#1,d1			; set moving direction to right by default
	tst.w	d0
	bpl.s	+			; if moving to the right, use default moving direction
	moveq	#2,d1			; otherwise change to move to the left
+	move.b	d1,(Player_MovingDir).w
.facing:
	bclr	#status.player.x_flip,status(a0)
	cmpi.b	#2,(PlayerFacingDir).w
	bne.s	+
	bset	#status.player.x_flip,status(a0)
+	rts

; ---------------------------------------------------------------------------
; Mario's on-ground mode (replaces Obj01_MdNormal).
; SMB1 order: crouch flag, PlayerPhysicsSub (jump + X_Physics), then
; OnGroundStateSub. A jump switches to the air routine within the same
; frame, as SMB1's MoveSubs does after ProcJumping sets Player_State to 1.
; ---------------------------------------------------------------------------
Mario_MdNormal:
	move.w	inertia(a0),d0
	bsr.w	Mario_SyncXSpeed
	bsr.w	Mario_CrouchCheck
	clr.b	(Mario_JumpStart).w
	bsr.w	PlayerPhysicsSub
	tst.b	(Mario_JumpStart).w
	bne.s	Mario_JumpFromGround
	jsr	(Sonic_SlopeResist).l	; S2: slopes push on the ground speed
	move.w	inertia(a0),d0
	bsr.w	Mario_SyncXSpeed
	bsr.w	OnGroundStateSub
	bsr.w	Mario_XSpeedForS2	; hand the ground speed to S2
	move.w	d0,inertia(a0)
	jsr	(Obj01_Traction).l	; split inertia into x_vel/y_vel along the floor; stop at walls
	bsr.w	Mario_GroundAnim
	jsr	(Sonic_LevelBound).l
	jsr	(ObjectMove).l
	jsr	(AnglePos).l		; follow the floor (slopes, loops)
	jsr	(Sonic_SlopeRepel).l	; fall off walls/ceilings when too slow
	rts

; ---------------------------------------------------------------------------
; Take-off: S2 side of ProcJumping. Like Sonic_Jump, the jump speed is applied
; perpendicular to the floor, so jumping off slopes and walls works. On flat
; ground this sets y_vel to exactly SMB1's Y_Speed:Y_MoveForce.
; ---------------------------------------------------------------------------
Mario_JumpFromGround:
	moveq	#0,d0
	move.b	angle(a0),d0
	subi.b	#$40,d0
	jsr	(CalcSine).l
	movem.w	d0-d1,-(sp)
	move.w	(Mario_JumpSpeed).w,d0
	bsr.w	Mario_YForS2		; scaled by Mario_YScale
	move.w	d0,d2
	movem.w	(sp)+,d0-d1
	neg.w	d2			; jump strength (positive)
	muls.w	d2,d1
	asr.l	#8,d1
	add.w	d1,x_vel(a0)
	muls.w	d2,d0
	asr.l	#8,d0
	add.w	d0,y_vel(a0)
	bset	#status.player.in_air,status(a0)
	bclr	#status.player.pushing,status(a0)
	move.b	#1,jumping(a0)
	clr.b	stick_to_convex(a0)
	move.w	x_vel(a0),d0		; airborne now: x_vel is the horizontal speed
	bsr.w	Mario_SyncXSpeed
	bra.s	Mario_MdAir_Move	; continue as JumpSwimSub this frame

; ---------------------------------------------------------------------------
; Mario's airborne mode (replaces Obj01_MdAir and Obj01_MdJump).
; ---------------------------------------------------------------------------
Mario_MdAir:
	move.w	x_vel(a0),d0
	bsr.w	Mario_SyncXSpeed
	bsr.w	Mario_CrouchCheck
	clr.b	(Mario_JumpStart).w
	bsr.w	PlayerPhysicsSub	; X_Physics, and swim strokes
	tst.b	(Mario_JumpStart).w	; swim stroke started?
	beq.s	Mario_MdAir_Move
	move.w	(Mario_JumpSpeed).w,d0	; SMB1 sets Player_Y_Speed directly
	bsr.w	Mario_YForS2
	move.w	d0,y_vel(a0)
	clr.b	(Mario_LaunchFlag).w	; Mario's own stroke now: SMB1 forces, not S2 gravity
Mario_MdAir_Move:
	cmpi.b	#1,(Player_State).w	; MoveSubs: jumping/swimming or falling?
	bne.s	.falling
	bsr.w	JumpSwimSub
	; Mario's own action (ProcessPlayerAction draws the jump). Not Sonic's
	; Roll ID: Mario's attacks are SMB1 stomps (Mario_TouchEnemy).
	move.b	#AniIDSonAni_Walk,anim(a0)
	bra.s	.move
.falling:
	bsr.w	FallingSub
.move:
	jsr	(Sonic_LevelBound).l
	jsr	(ObjectMove).l		; MovePlayerHorizontally + ImposeGravity's position update
	bsr.w	MovePlayerVertically	; then the downward force
	jsr	(Sonic_JumpAngle).l
	jsr	(Sonic_DoLevelCollision).l	; landing, walls, ceilings
	move.w	y_vel(a0),(Mario_LastYVel).w	; for Mario_SyncState's launch detection
	; fall through

; ---------------------------------------------------------------------------
; Stomp ID: while Mario's own anim is showing and he is airborne and falling,
; his anim ID reads AniIDSonAni_Roll - S2's "attacking" ID - so landing on
; S2's breakables (Obj32 CPZ caps/HTZ rocks, Obj2F HTZ smashable ground, Obj3D
; OOZ blocks: they break if the player's anim was Roll when he landed)
; counts as a stomp, like on monitors and badniks. Rising, it reads Walk.
; Mario_Animate draws both through SMB1's ProcessPlayerAction, so the frames
; don't change. Anims set by S2 objects (spring, hurt...) and forced rolls
; are left alone.
; ---------------------------------------------------------------------------
Mario_StompAnimID:
	btst	#status.player.rolling,status(a0)
	bne.s	.done
	btst	#status.player.in_air,status(a0)
	beq.s	.done			; landed this frame: the ground code sets the anim
	moveq	#0,d0
	move.b	anim(a0),d0
	add.w	d0,d0
	lea	(MarioAniData).l,a1
	adda.w	(a1,d0.w),a1
	cmpi.b	#$FF,(a1)		; one of Mario's own actions (walk, crouch, skid, jump...)?
	bne.s	.done			; no: an S2 object chose it
	moveq	#AniIDSonAni_Walk,d0
	tst.w	y_vel(a0)
	ble.s	+
	moveq	#AniIDSonAni_Roll,d0	; falling: stomping
+	move.b	d0,anim(a0)
.done:
	rts

; ---------------------------------------------------------------------------
; Forced rolls only (CPZ tubes, CNZ pinball): Mario never starts a roll,
; but objects can put him in one. S2's roll physics, Mario's jump.
; ---------------------------------------------------------------------------
Mario_MdRoll:
	tst.b	pinball_mode(a0)
	bne.s	+
	clr.b	(Mario_JumpStart).w
	bsr.w	PlayerPhysicsSub
	tst.b	(Mario_JumpStart).w
	bne.w	Mario_JumpFromGround	; stays "rolling" until landing, like a roll-jump
+
	jsr	(Sonic_RollRepel).l
	jsr	(Sonic_RollSpeed).l
	jsr	(Sonic_LevelBound).l
	jsr	(ObjectMove).l
	jsr	(AnglePos).l
	jsr	(Sonic_SlopeRepel).l
	rts

; ---------------------------------------------------------------------------
; Ground anim ID for S2's benefit. The frame itself is chosen by SMB1's
; ProcessPlayerAction (Mario_Animate); the ID tells S2 objects what Mario is
; doing: Stop keeps Obj08 throwing skid dust. Skid condition from ProcOnGroundActs.
; While move_lock is set, an anim an S2 object chose (e.g. Bubble) is kept,
; as Sonic_Move does.
; ---------------------------------------------------------------------------
Mario_GroundAnim:
	tst.w	move_lock(a0)
	beq.s	.choose
	moveq	#0,d0
	move.b	anim(a0),d0
	add.w	d0,d0
	lea	(MarioAniData).l,a1
	adda.w	(a1,d0.w),a1
	cmpi.b	#$FF,(a1)		; Mario's own action?
	bne.s	.keep			; no: leave the object's animation alone
.choose:
	move.b	#AniIDSonAni_Duck,d0
	tst.b	(CrouchingFlag).w
	bne.s	.set
	move.b	#AniIDSonAni_Walk,d0
	cmpi.b	#$09,(Player_XSpeedAbsolute).w	; too slow to skid?
	blo.s	.set
	move.b	(Player_MovingDir).w,d1
	and.b	(PlayerFacingDir).w,d1	; moving and facing the same way?
	bne.s	.set
	moveq	#AniIDSonAni_Stop,d0	; skidding
	cmp.b	anim(a0),d0		; just started?
	beq.s	.set
	move.b	d0,anim(a0)
	; S2's skid dust (SMB1 has none). No skid sound: SMB1 has none either, and
	; S2's skid sound slot now holds SMB1's small jump.
	cmpi.b	#12,air_left(a0)	; drowning?
	blo.s	.keep			; if yes, no dust
	move.b	#6,(Sonic_Dust+routine).w	; Obj08: skidding (as Sonic_Move does)
	move.b	#$15,(Sonic_Dust+mapping_frame).w
	rts
.set:
	move.b	d0,anim(a0)
.keep:
	rts

; ---------------------------------------------------------------------------
; S2 code all over the place resets "the player" to Sonic's standing radius
; ($13/9) - e.g. Sonic_RollSpeed when a forced roll ends. Sonic's feet are at
; y_pos+$13; put Mario's feet in the same place with his own radius.
; ---------------------------------------------------------------------------
Mario_FixSonicRadius:
	cmpi.b	#$13,y_radius(a0)
	bne.s	.done
	moveq	#$13,d0
	bsr.s	Mario_SetRadius
	sub.b	y_radius(a0),d0
	ext.w	d0
	add.w	d0,y_pos(a0)
.done:
	rts

; ---------------------------------------------------------------------------
; Set Mario's collision radii from PlayerSize (SMB1: 0 = big, 1 = small).
; While growing/shrinking the big radius is kept (the "tall" frames are drawn);
; crouching uses the small radius (SMB1's crouching bounding box is the small
; one), which also shrinks his S2 touch box - no duck hook needed (H5/H6).
; ---------------------------------------------------------------------------
Mario_SetRadius:
	tst.b	(PlayerChangeSizeFlag).w
	bne.s	.big
	tst.b	(PlayerSize).w
	bne.s	.small
	tst.b	(CrouchingFlag).w
	bne.s	.small
.big:
	move.b	#Mario_BigYRadius,y_radius(a0)
	move.b	#Mario_BigXRadius,x_radius(a0)
	rts
.small:
	move.b	#Mario_SmallYRadius,y_radius(a0)
	move.b	#Mario_SmallXRadius,x_radius(a0)
	rts

; ---------------------------------------------------------------------------
; Bring the radius in line with size/crouch, keeping the feet where they are
; (towards the floor, wall or ceiling Mario stands on). Forced rolls keep the
; radius S2 gave them.
; ---------------------------------------------------------------------------
Mario_ApplyRadius:
	btst	#status.player.rolling,status(a0)
	bne.s	.done
	moveq	#0,d2
	move.b	y_radius(a0),d2
	bsr.s	Mario_SetRadius
	sub.b	y_radius(a0),d2		; old - new
	beq.s	.done
	ext.w	d2
	bsr.w	MAnim_AngleQuadrant	; d1 = 0 floor, 1 right wall, 2 ceiling, 3 left wall
	btst	#1,d1
	beq.s	+
	neg.w	d2			; ceiling / left wall: feet on the negative side
+	btst	#0,d1
	bne.s	.wall
	add.w	d2,y_pos(a0)
	rts
.wall:
	add.w	d2,x_pos(a0)
.done:
	rts

; ---------------------------------------------------------------------------
; Landing (hook H4): Sonic_ResetOnFloor_Part2 branches here for ObjMario.
; This covers normal landings, SolidObject landings, HurtCharacter and
; KillCharacter. If Mario was rolling (forced roll), restore his radius and
; correct y_pos by the radius change so his feet stay where they landed.
; ---------------------------------------------------------------------------
Mario_ResetOnFloor_Part2:
	btst	#status.player.rolling,status(a0)
	beq.s	.part3
	bclr	#status.player.rolling,status(a0)
	moveq	#0,d0
	move.b	y_radius(a0),d0		; radius used while rolling
	bsr.w	Mario_SetRadius
	sub.b	y_radius(a0),d0		; old - new
	ext.w	d0
	add.w	d0,y_pos(a0)		; keep the feet on the floor
	move.b	#AniIDSonAni_Walk,anim(a0)
.part3:
	jmp	(Sonic_ResetOnFloor_Part3).l

; ---------------------------------------------------------------------------
; Debug mode exit (hook H12). Debug_ExitDebugMode has just restored Sonic's
; mappings, art and radii into the main character; put Mario's back.
; Input: a1 = MainCharacter.
; ---------------------------------------------------------------------------
Mario_DebugExit:
	move.l	#MapUnc_Mario,mappings(a1)
	move.w	#make_art_tile(ArtTile_ArtUnc_Sonic,0,0),art_tile(a1)
	st.b	(Mario_LastLoadedDPLC).w	; VRAM slot was overwritten: force a reload
	exg	a0,a1
	bsr.w	Mario_SetRadius
	exg	a0,a1
	move.l	a1,-(sp)
	bsr.w	Mario_LoadFireballArt	; (in case debug placement art used Tails' slot)
	movea.l	(sp)+,a1
	rts

; ===========================================================================
; Power state (Phase 5)
; ---------------------------------------------------------------------------
; SMB1 halts the whole game while Mario grows, gets fire or is injured:
; GameEngineSubroutine switches to PlayerChangeSize ($09), PlayerFireFlower
; ($0C) or PlayerInjuryBlink ($0A), and TimerControl counts $FF down, with
; things happening at fixed counts. Here only Mario is affected (S2 keeps
; running), and S2's knockback replaces SMB1's injury freeze.
; Power-ups come from rings instead of mushrooms/flowers (user decision):
; >= Mario_RingsForSuper rings -> super, >= Mario_RingsForFiery -> fiery.
; They only ever upgrade; only a hit takes them away.
; ===========================================================================

; ---------------------------------------------------------------------------
; nmi.asm: while TimerControl is set it counts down and the frame timers stop.
; ---------------------------------------------------------------------------
Mario_TimerTick:
	tst.b	(TimerControl).w
	beq.w	Mario_FrameTimers
	subq.b	#1,(TimerControl).w
	beq.w	Mario_FrameTimers	; reached zero: timers run again this frame
	rts

; ---------------------------------------------------------------------------
; Run Mario's GameEngineSubroutine. Returns Z clear (bne) if Mario is halted.
; ---------------------------------------------------------------------------
Mario_RunPowerTask:
	move.b	(Mario_PowerTask).w,d0
	cmpi.b	#MarioTask_ChangeSize,d0
	beq.s	PlayerChangeSize
	cmpi.b	#MarioTask_FireFlower,d0
	beq.s	PlayerFireFlower
	cmpi.b	#MarioTask_InjuryBlink,d0
	beq.s	PlayerInjuryBlink
	moveq	#0,d0			; player control
	rts

; player-change-size.asm
PlayerChangeSize:
	move.b	(TimerControl).w,d0	; check master timer control
	cmpi.b	#$F8,d0			; for specific moment in time
	bne.s	EndChgSize		; branch if before or after that point
	bsr.s	InitChangeSize		; otherwise run code to get growing/shrinking going
	bra.s	MarioHalted
EndChgSize:
	cmpi.b	#$C4,d0			; check again for another specific moment
	bne.s	MarioHalted		; and branch to leave if before or after that point
	bsr.s	DonePlayerTask		; otherwise do sub to init timer control and set routine
MarioHalted:
	moveq	#1,d0
	rts

; player-fire-flower.asm. SMB1 cycles the four sprite palettes every 4 frames;
; Mario has two colour banks (normal, fiery), so they alternate instead.
PlayerFireFlower:
	cmpi.b	#$C0,(TimerControl).w	; check master timer control for specific moment in time
	beq.s	ResetPalFireFlower	; branch if at moment, not before or after
	move.b	(Level_frame_counter+1).w,d0	; get frame counter
	lsr.b	#2,d0			; divide by four to change every four frames
	andi.b	#1,d0
	move.b	d0,(Mario_ArtBank).w
	bra.s	MarioHalted
ResetPalFireFlower:
	bsr.s	DonePlayerTask		; do sub to init timer control and run player control routine
	bsr.s	GetPlayerColors
	bra.s	MarioHalted

; player-injury-blink.asm. SMB1 halts Mario until $F0 and shrinks him then.
; Normal mode: the halt itself is in ObjMario_Hurt (he is in S2's hurt
; routine), which holds him still until the task ends; then S2's knockback
; runs, and the value returned here isn't used.
; Hard mode (rule 3): no knockback, Mario stays in ObjMario_Control. He is
; halted until $F0 and while the shrink plays (SMB1's PlayerMovementSubs
; skips movement while PlayerChangeSizeFlag is set), then he has control
; while the world stays paused until $C8.
PlayerInjuryBlink:
	move.b	(TimerControl).w,d0	; check master timer control
	cmpi.b	#$F0,d0			; for specific moment in time
	bhi.s	MarioHalted		; branch if before that point
	bne.s	+
	bsr.s	InitChangeSize		; shrink
	bra.s	MarioHalted
+	cmpi.b	#$C8,d0			; check again for another specific point
	bne.s	+
	bsr.s	DonePlayerTask		; branch if at that point, and not before or after
+	moveq	#0,d0
	tst.b	(PlayerChangeSizeFlag).w	; port: still shrinking? then halted
	beq.s	+
	moveq	#1,d0
+	rts

InitChangeSize:
	tst.b	(PlayerChangeSizeFlag).w	; if growing/shrinking flag already set
	bne.s	ExitBoth		; then branch to leave
	clr.b	(PlayerAnimCtrl).w	; otherwise initialize player's animation frame control
	addq.b	#1,(PlayerChangeSizeFlag).w	; set growing/shrinking flag
	eori.b	#1,(PlayerSize).w	; invert player's size
ExitBoth:
	rts

; player-death.asm
DonePlayerTask:
	clr.b	(TimerControl).w	; initialize master timer control to continue timers
	clr.b	(Mario_PowerTask).w	; set player control routine to run next frame
	rts

; colors.asm GetPlayerColors: fiery Mario uses the fire colour bank.
GetPlayerColors:
	moveq	#0,d0
	cmpi.b	#MarioStatus_Fiery,(PlayerStatus).w
	bne.s	+
	moveq	#1,d0
+	move.b	d0,(Mario_ArtBank).w
	rts

; ---------------------------------------------------------------------------
; Rings -> power-up (in place of HandlePowerUpCollision's Shroom_Flower_PUp,
; main.asm:8468). Only while Mario has control and nothing is in progress.
; Small -> super, then (on a later frame) super -> fiery.
; ---------------------------------------------------------------------------
Mario_UpdatePower:
	tst.b	(Mario_PowerTask).w
	bne.s	NoPUp
	tst.b	(PlayerChangeSizeFlag).w
	bne.s	NoPUp
	move.w	(Ring_count).w,d0
	move.b	(PlayerStatus).w,d1	; if player status = small, branch
	beq.s	.small
	cmpi.b	#MarioStatus_Super,d1	; if player status not super, leave
	bne.s	NoPUp
	cmpi.w	#Mario_RingsForFiery,d0
	blo.s	NoPUp
	move.b	#MarioStatus_Fiery,(PlayerStatus).w	; set player status to fiery
	moveq	#MarioTask_FireFlower,d0	; set value to be used by subroutine tree (fiery)
	bra.s	UpToFiery
.small:
	cmpi.w	#Mario_RingsForSuper,d0
	blo.s	NoPUp
; UpToSuper:
	move.b	#MarioStatus_Super,(PlayerStatus).w	; set player status to super
	moveq	#MarioTask_ChangeSize,d0	; set value to be used by subroutine tree (super)
UpToFiery:
	bsr.s	SetPRout		; set values to stop certain things in motion
	; Sfx_PowerUpGrab, converted (tools/nes_sfx2smps.py). Mario's own sounds use
	; the third SFX queue slot, which S2 never writes: in the same frame, S2's
	; PlaySound/PlaySound2 (hurt, ring spill...) would overwrite slots 1 and 2.
	move.b	#SndID_MarioPowerUp,(Sound_Queue.SFX2).w
	rts
NoPUp:
	rts

; main.asm:8639 SetPRout (Player_State is S2's business here)
SetPRout:
	move.b	d0,(Mario_PowerTask).w	; load new value to run subroutine on next frame
	st.b	(TimerControl).w	; set master timer control flag to halt timers
	rts

; ---------------------------------------------------------------------------
; main.asm:8627 ForceInjury: called by Mario_HurtCharacter when a super or
; fiery Mario is hit. If a grow was still in progress he is treated as big.
; ---------------------------------------------------------------------------
ForceInjury:
	clr.b	(PlayerStatus).w	; set player's status to small
	clr.b	(PlayerChangeSizeFlag).w	; port: cancel any grow in progress...
	clr.b	(PlayerSize).w		; ...so the shrink starts from big
	bsr.s	GetPlayerColors		; change player's palette if necessary
	move.b	#SndID_MarioPowerDown,(Sound_Queue.SFX2).w	; play pipedown/injury sound (3rd queue slot: see UpToFiery)
	moveq	#MarioTask_InjuryBlink,d0	; set subroutine to run on next frame
	bra.s	SetPRout

; ---------------------------------------------------------------------------
; World pause (H17, user request): while TimerControl runs a power task
; (grow, fire flower, injury), SMB1 halts everything but Mario. Here the
; objects outside the reserved slots (the same split S2 uses while the player
; is dead), the oscillators (platform positions), the ring/lost-ring timers and
; the level clock stop. Mario (and his shield, dust...) keep running.
; The S2 hooks replace existing calls of the same size: inserting bytes into
; S2's main code makes AS fail on some sizes (see CLAUDE.md, "Hooking S2").
; ---------------------------------------------------------------------------
; Z clear (bne) if the world is paused. Mario's RAM is only meaningful when
; Mario is the main character (in other modes the block is never initialised).
Mario_WorldPaused:
	cmpi.b	#ObjID_Mario,(MainCharacter+id).w
	bne.s	.no
	tst.b	(Mario_PowerTask).w
	rts
.no:
	move	#4,ccr			; Z set
	rts

; Level_MainLoop's "jsr (RunObjects).l"
Mario_RunObjects:
	bsr.s	Mario_WorldPaused
	bne.s	.paused
	jmp	(RunObjects).l
.paused:
	tst.b	(Teleport_flag).w	; (as RunObjects)
	bne.s	.done
	lea	(Object_RAM).w,a0
	moveq	#0,d0
	jmp	(RunObjectsWhenPlayerIsDead).l	; reserved slots run, the rest only display
.done:
	rts

; Level_MainLoop's "bsr.w OscillateNumDo / bsr.w ChangeRingFrame"
Mario_OscillateAndRings:
	bsr.s	Mario_WorldPaused
	bne.s	.done
	jsr	(OscillateNumDo).l
	jmp	(ChangeRingFrame).l
.done:
	rts

; Hud_ChkTime's "tst.w (Game_paused).w / bne.s Hud_ChkLives"
Mario_HudTimePaused:
	tst.w	(Game_paused).w		; is the game paused?
	bne.s	.skip
	bsr.s	Mario_WorldPaused	; or the world, for Mario?
	bne.s	.skip
	rts				; no: count the time
.skip:
	addq.l	#4,sp			; yes: skip it, as the original branch did
	jmp	(Hud_ChkLives).l

; ---------------------------------------------------------------------------
; Water entry/exit: S2's Sonic_Water, except that leaving the water during
; Mario's own jump out (a normal jump from the surface, see ChkWtr) keeps the
; jump's speed. S2 doubles y_vel on the way out because Sonic's underwater
; jump is weaker; Mario's jump out already has its full land speed. Swim
; strokes out of the water (holding C) still get S2's boost.
; ---------------------------------------------------------------------------
Mario_Water:
	move.w	y_vel(a0),-(sp)
	jsr	(Sonic_Water).l
	move.w	(sp)+,d0
	btst	#status.player.underwater,status(a0)
	bne.s	.done			; still (or now) under water
	tst.b	(Mario_InWater).w	; was under water this frame (Mario_SwimCheck)?
	beq.s	.done
	tst.b	(Mario_SwimForces).w	; swimming out: S2's boost stays
	bne.s	.done
	cmpi.b	#1,(Player_State).w	; Mario's own jump?
	bne.s	.done
	move.w	d0,y_vel(a0)		; undo the doubling
.done:
	; user decision: no drowning for Mario. Air stays full, so S2's Obj0A
	; never reaches its warnings, countdown or drowning (it only ticks once a second).
	move.b	#30,air_left(a0)
	rts

; ---------------------------------------------------------------------------
; Sonic_Display for Mario. Hard mode (rule 4): SMB1's injured invincibility
; blink (main.asm:11797 PlayerGfxHandler: while InjuryTimer is set, the player
; isn't drawn on odd frames), and the timer (S2's invulnerable_time) is halted
; while TimerControl is, as SMB1's interval timers are. Then S2's star and
; speed shoes timers, as Sonic_Display.
; ---------------------------------------------------------------------------
Mario_Display:
	tst.b	(Mario_HardMode).w
	beq.s	.normal
	tst.w	invulnerable_time(a0)	; if player's injured invincibility timer
	beq.s	.draw			; not set, skip checkpoint and continue code
	tst.b	(TimerControl).w	; port: timers halted?
	bne.s	+
	subq.w	#1,invulnerable_time(a0)
+	btst	#0,(Level_frame_counter+1).w	; otherwise check frame counter and branch
	beq.s	.draw			; to leave on every other frame (when d0 is set)
	jmp	(Obj01_ChkInvin).l	; (not drawn)
.draw:
	jmp	(Obj01_Display).l
.normal:
	jmp	(Sonic_Display).l

; ---------------------------------------------------------------------------
; KillCharacter's "jsr (PlaySound).l" (size-neutral hook; every death goes
; through it: enemies, spikes, pits, time over). For Mario it is SMB1's
; KillPlayer: no death sound, the death music, and LoadEventMusic stops the
; sound effects first. One music request is taken per frame (Music0, then
; Music1), so the effects stop this frame and the music starts the next.
; Others: d0 = the hurt sound, as before.
; ---------------------------------------------------------------------------
Mario_DeathSound:
	cmpi.b	#ObjID_Mario,id(a0)
	beq.s	+
	jmp	(PlaySound).l
+	move.b	#MusID_StopSFX,(Sound_Queue.Music0).w
	move.b	#MusID_MarioDeath,(Sound_Queue.Music1).w
	tst.b	(Mario_HardMode).w
	beq.s	+
; Hard mode (rule 6), main.asm:8651 KillPlayer: in place of S2's death jump
; (-$700), SMB1's: halted until TimerControl $F0 (ObjMario_DeadHard), then
; Y speed $FC under SMB1 gravity. Player_X_Speed is already 0 (S2 cleared
; x_vel). The falling force is the character's own (FallMForceData[0]):
; whatever SMB1 left in VerticalForce could be a swim force, a long float.
	clr.w	(Player_X_Speed).w	; halt player's horizontal movement by initializing speed
	clr.b	(Player_X_MoveForce).w
	clr.b	(PlayerChangeSizeFlag).w	; port: a shrink in progress ends here
	clr.b	(Mario_LaunchFlag).w
	clr.b	(Mario_SwimForces).w
	bsr.w	Mario_InitFallForce
	move.w	#$FC00,d0		; set new vertical speed
	bsr.w	Mario_SetYSpeed
	moveq	#MarioTask_Death,d0	; set subroutine to run on next frame
	move.b	#1,(Player_State).w	; set player's state
	bra.w	SetPRout		; (TimerControl $FF)
+	rts

; ---------------------------------------------------------------------------
; Obj24 (air bubbles)'s "tst.b obj_control(a1) / bmi.w return_1FBCA" (8 bytes,
; size-neutral hook): Mario never inhales a bubble (user decision; he doesn't
; drown). Skipping returns from the bubble's player check, as the branch did.
; ---------------------------------------------------------------------------
Mario_BubbleSkip:
	cmpi.b	#ObjID_Mario,id(a1)
	beq.s	.skip
	tst.b	obj_control(a1)		; (replaced instructions)
	bmi.s	.skip
	rts
.skip:
	addq.l	#4,sp			; return from the check (return_1FBCA is an rts)
	rts

; ---------------------------------------------------------------------------
; Set Mario's vertical speed from an SMB1 Y_Speed:Y_MoveForce value (d0.w),
; as his own code does: scaled, and remembered so Mario_SyncState doesn't
; take it for an S2 launch.
; ---------------------------------------------------------------------------
Mario_SetYSpeed:
	bsr.w	Mario_YForS2
	move.w	d0,y_vel(a0)
	move.w	d0,(Mario_LastYVel).w
	rts
