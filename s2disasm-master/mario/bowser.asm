; ===========================================================================
; WFZ boss: SMB1's Bowser (Phase 7.5, user design)
; ---------------------------------------------------------------------------
; The WFZ boss arena is kept: ObjC5's laser walls trap Mario, Robotnik watches
; from outside and sinks away at the end. But instead of the laser case,
; Bowser stands between Mario (entering from the left) and SMB1's axe (right).
; Touching the axe ends the fight as in SMB1 (Bowser's bridge collapses and he
; falls), then explosions fill the screen and S2's post-boss events run.
; Fireballs can kill Bowser (5 hits) but, as in SMB1, only the axe ends it.
;
; ObjBowser (ObjID_Bowser):
;   subtype $92 - the fight controller. ObjC5_Init turns the laser case into it
;                 (Mario_WFZBossInit), so the walls and Robotnik (children of
;                 that slot) still see its p1_pushing "defeated" bit.
;   subtype $10 - Bowser.
; ObjBowserMisc (ObjID_BowserMisc): subtype 0 flame, 2 hammer, 4 axe.
;
; Bowser's logic is SMB1's (main.asm: InitBowser 5545, BowserControl 7301,
; BridgeCollapse 7220, RunBowser 7283, InitBowserFlame 5597, ProcBowserFlame
; 7491, SpawnHammerObj 3824, ProcHammerObj 3856, HurtBowser 8351), as 8-4's
; Bowser: flames and hammers (user decision). SMB1 uses 8-bit screen
; coordinates; here they are S2 world coordinates, and these SMB1 constants
; become positions relative to the arena:
;   Bowser's ground (y $80, the top of his front half) -> the arena floor
;   "past $C8" (stop chasing right)                    -> Bowser_ChaseLimit
; All speeds are SMB1's, in pixels (no Mario_XSpeedToS2 scaling).
; ===========================================================================

; arena layout, relative to the laser case's position (x $2B80, y $450)
Bowser_ArenaTrigger	= -$88+$10	; Mario just inside the left laser wall (centre - $88) starts
					;   the fight (user: as soon as he enters the arena)
Bowser_ArenaTop		= 0		; ...at the arena's height (not passing high above it)
Bowser_StartX		= $18		; Bowser's front half (SMB1 x = its left edge, facing left)
Bowser_SpawnY		= $98		; near the floor (y $500); the floor check finds it
Bowser_AxeX		= $70		; axe centre, just inside the right laser wall (+$88)
Bowser_ChaseLimit	= $40		; SMB1 "cmp #$c8": no chasing right past centre + this

; SMB1 Bowser variables in his SST
bw_fx		= objoff_30	; word: Enemy_X_Position (front half's left edge)
bw_origx	= objoff_32	; word: BowserOrigXPos
bw_ground	= objoff_34	; word: y when standing (SMB1: y $80)
bw_body		= objoff_36	; byte: BowserBodyControls (d7 mouth open, d0 feet)
bw_feet		= objoff_37	; byte: BowserFeetCounter
bw_frametmr	= objoff_38	; byte: EnemyFrameTimer
bw_breath	= objoff_39	; byte: BowserFireBreathTimer
bw_speed	= objoff_3A	; byte: BowserMovementSpeed (signed)
bw_range	= objoff_3B	; byte: MaxRangeFromOrigin
bw_dir		= objoff_3C	; byte: Enemy_MovingDir (1 right, 2 left)
bw_hp		= objoff_3D	; byte: BowserHitPoints
bw_flamectl	= objoff_3E	; byte: BowserFlameTimerCtrl
bw_state	= objoff_3F	; byte: Enemy_State: 0 normal, $20 defeated (fireballs),
				;   $40 falling (axe), $80 port: bridge collapsing
bw_collapse	= objoff_2E	; byte: BridgeCollapseOffset

; fight controller (the laser case's slot; objoff_2A and objoff_38 get the
; walls' and Robotnik's pointers from LoadChildObject)
ar_timer	= objoff_30	; word
ar_artdone	= objoff_32	; byte: Bowser's art is in VRAM

; misc objects
fl_target	= objoff_30	; word: flame's target top y (FlameYPosData)
fl_top		= objoff_32	; word: flame's top y
fl_step		= objoff_34	; byte: Enemy_Y_MoveForce (+1/-1)
fl_xfrac	= objoff_35	; byte: Enemy_X_MoveForce
fl_left		= objoff_36	; word: flame's left x
hm_state	= objoff_30	; byte: Misc_State
hm_slot		= objoff_31	; byte: misc slot (Bowser_HammerSlots)
hm_xspd		= objoff_32	; byte: Misc_X_Speed (px/frame)

; ===========================================================================
ObjBowser:
	moveq	#0,d0
	move.b	routine(a0),d0
	move.w	ObjBowser_Index(pc,d0.w),d1
	jmp	ObjBowser_Index(pc,d1.w)
ObjBowser_Index:	offsetTable
	offsetTableEntry.w ObjBowser_Init	; 0
	offsetTableEntry.w Arena_Main		; 2
	offsetTableEntry.w Bowser_Main		; 4
; ---------------------------------------------------------------------------
ObjBowser_Init:
	moveq	#2,d0			; the converted laser case: the fight controller
	cmpi.b	#$10,subtype(a0)
	bne.s	+
	moveq	#4,d0			; Bowser
+	move.b	d0,routine(a0)
	clr.b	routine_secondary(a0)
	clr.b	collision_flags(a0)
	cmpi.b	#4,d0
	beq.w	Bowser_Init
	rts

; ===========================================================================
; The fight controller (replaces ObjC5's laser case)
; ===========================================================================
Arena_Main:
	moveq	#0,d0
	move.b	routine_secondary(a0),d0
	move.w	Arena_Index(pc,d0.w),d1
	jmp	Arena_Index(pc,d1.w)
Arena_Index:	offsetTable
	offsetTableEntry.w Arena_Setup		; 0
	offsetTableEntry.w Arena_WaitStart	; 2
	offsetTableEntry.w Arena_WaitMusic	; 4
	offsetTableEntry.w Arena_Fight		; 6
	offsetTableEntry.w Arena_WaitBowser	; 8
	offsetTableEntry.w Arena_Explosions	; $A
; ---------------------------------------------------------------------------
; ObjC5_CaseBoundary: the camera's floor for the fight
Arena_Setup:
	addq.b	#2,routine_secondary(a0)
	move.w	#$442,d0
	move.w	d0,(Camera_Max_Y_pos).w
	move.w	d0,(Camera_Max_Y_pos_target).w
	clr.b	ar_artdone(a0)
	rts
; ---------------------------------------------------------------------------
; ObjC5_CaseWaitStart, but the trigger is Mario entering from the left. The
; WFZ boss art (still needed for the laser walls) is loaded by the level's
; PLC; once that has finished Bowser's art goes over the laser case's tiles.
Arena_WaitStart:
	tst.b	ar_artdone(a0)
	bne.s	+
	tst.l	(Plc_Buffer).w		; PLCs still decompressing?
	bne.w	.done
	st.b	ar_artdone(a0)
	move.l	#ArtUnc_Bowser,d1
	move.w	#tiles_to_bytes(ArtTile_ArtNem_WFZBoss),d2
	move.w	#(ArtUnc_Bowser_End-ArtUnc_Bowser)/2,d3
	jsr	(QueueDMATransfer).l
+	move.w	(MainCharacter+x_pos).w,d0
	sub.w	x_pos(a0),d0
	cmpi.w	#Bowser_ArenaTrigger,d0
	blt.w	.done
	move.w	(MainCharacter+y_pos).w,d0
	sub.w	y_pos(a0),d0
	cmpi.w	#Bowser_ArenaTop,d0
	blt.w	.done
	tst.b	ar_artdone(a0)		; (Bowser's art must be in VRAM)
	beq.w	.done
	; ObjC5_CaseStart: laser walls, Robotnik, music fade - and (unlike the
	; laser case's wait) Bowser and the axe straight away
	addq.b	#2,routine_secondary(a0)
	bsr.w	Arena_SpawnBowser
	lea	(ChildObject_ObjC5LaserWall).l,a2
	jsr	(LoadChildObject).l
	subi.w	#$88,x_pos(a1)		; left laser wall
	addi.w	#$60,y_pos(a1)
	lea	(ChildObject_ObjC5LaserWall).l,a2
	jsr	(LoadChildObject).l
	addi.w	#$88,x_pos(a1)		; right laser wall
	addi.w	#$60,y_pos(a1)
	lea	(ChildObject_ObjC5Robotnik).l,a2
	jsr	(LoadChildObject).l
	move.w	#$5A,ar_timer(a0)
	move.w	#MusID_FadeOut,d0
	jsr	(PlaySound).l
.done:
	rts
; ---------------------------------------------------------------------------
; ObjC5_CaseWaitDown/SpeedDown: the boss music once the fade is done
Arena_WaitMusic:
	subq.w	#1,ar_timer(a0)
	bpl.s	.done
	addq.b	#2,routine_secondary(a0)
	move.w	#MusID_BowserCastle,d0	; SMB1's castle theme
	jsr	(PlayMusic).l
.done:
	rts

; Bowser and the axe (a0 = the fight controller)
Arena_SpawnBowser:
	jsr	(AllocateObjectAfterCurrent).l
	bne.s	+
	move.b	#ObjID_Bowser,id(a1)
	move.b	#$10,subtype(a1)
	move.w	x_pos(a0),d0
	addi.w	#Bowser_StartX,d0
	move.w	d0,x_pos(a1)
	move.w	y_pos(a0),d0
	addi.w	#Bowser_SpawnY,d0
	move.w	d0,y_pos(a1)
	move.w	x_pos(a0),objoff_2C(a1)	; arena centre x (for the chase limit)
+	jsr	(AllocateObjectAfterCurrent).l
	bne.s	+
	move.b	#ObjID_BowserMisc,id(a1)
	move.b	#4,subtype(a1)		; the axe
	move.w	x_pos(a0),d0
	addi.w	#Bowser_AxeX,d0
	move.w	d0,x_pos(a1)
	move.w	y_pos(a0),d0
	addi.w	#Bowser_SpawnY,d0
	move.w	d0,y_pos(a1)
+	st.b	(Bowser_FightOn).w
	rts
; ---------------------------------------------------------------------------
; Waiting for the axe. Touching it (SMB1 HandleAxeMetatile -> BridgeCollapse):
; Mario stops and is held, the music stops; a living Bowser loses his bridge
; and falls, otherwise (fireballs got him) the ending starts straight away.
Arena_Fight:
	tst.b	(Bowser_AxeTouched).w
	beq.s	.done
	addq.b	#2,routine_secondary(a0)
	st.b	(Control_Locked).w
	clr.w	(Ctrl_1_Logical).w
	lea	(MainCharacter).w,a1
	clr.w	x_vel(a1)
	clr.w	inertia(a1)
	move.w	#MusID_FadeOut,d0
	jsr	(PlaySound).l
	move.w	(Bowser_Ptr).w,d0
	beq.s	.done
	movea.w	d0,a1
	tst.b	bw_state(a1)		; Bowser still in his normal state?
	bne.s	.done
	move.b	#$80,bw_state(a1)	; RemoveBridge
	clr.b	collision_flags(a1)
	move.b	#4,bw_feet(a1)
	clr.b	bw_collapse(a1)
.done:
	rts
; ---------------------------------------------------------------------------
Arena_WaitBowser:
	tst.w	(Bowser_Ptr).w		; Bowser gone (fell off the screen)?
	bne.s	.done
	addq.b	#2,routine_secondary(a0)
	move.w	#$EF,ar_timer(a0)	; as ObjC5_NoHitPointsLeft
	bset	#status.npc.p1_pushing,status(a0)	; laser walls go, Robotnik sinks away
	moveq	#100,d0
	jsr	(AddPoints).l
.done:
	rts
; ---------------------------------------------------------------------------
; Explosions all over the screen (user design), then ObjC5_End.
Arena_Explosions:
	subq.w	#1,ar_timer(a0)
	bmi.s	.end
	move.b	(Vint_runcount+3).w,d0
	andi.b	#3,d0
	bne.s	.done
	jsr	(AllocateObject).l
	bne.s	.done
	move.b	#ObjID_BossExplosion,id(a1)
	jsr	(RandomNumber).l
	moveq	#0,d1
	move.b	d0,d1
	add.w	d1,d1
	addi.w	#32,d1			; 32..542: then clamp into the screen
	cmpi.w	#320-32,d1
	blo.s	+
	subi.w	#256,d1
+	add.w	(Camera_X_pos).w,d1
	move.w	d1,x_pos(a1)
	lsr.w	#8,d0
	andi.w	#$FF,d0
	cmpi.w	#224-32,d0
	blo.s	+
	subi.w	#128,d0
+	addi.w	#16,d0
	add.w	(Camera_Y_pos).w,d0
	move.w	d0,y_pos(a1)
.done:
	rts
.end:	; ObjC5_End: WFZ music, the way down to the Tornado opens
	move.w	#MusID_WFZ,d0
	jsr	(PlayMusic).l
	move.w	#$720,d0
	move.w	d0,(Camera_Max_Y_pos).w
	move.w	d0,(Camera_Max_Y_pos_target).w
	clr.b	(Control_Locked).w
	clr.b	(Bowser_FightOn).w
	jmp	(DeleteObject).l

; ===========================================================================
; Bowser
; ===========================================================================
PRandomRange:	dc.b $21, $41, $11, $31		; main.asm:7281
FlameTimerData:	dc.b $BF, $40, $BF, $BF, $BF, $40, $40, $BF	; main.asm:7478
	even

; InitBowser (main.asm:5545)
Bowser_Init:
	move.l	#MapUnc_Bowser,mappings(a0)
	move.w	#make_art_tile(ArtTile_ArtNem_WFZBoss,BowserPalLine,0),art_tile(a0)
	move.b	#1<<render_flags.level_fg,render_flags(a0)
	move.b	#4,priority(a0)
	move.b	#$20,width_pixels(a0)
	move.b	#$10,y_radius(a0)
	move.b	#$10,x_radius(a0)
	move.w	a0,(Bowser_Ptr).w
	; port: the ground is the arena floor under him
	jsr	(ObjCheckFloorDist).l
	add.w	d1,y_pos(a0)
	move.w	y_pos(a0),bw_ground(a0)
	clr.w	y_vel(a0)
	move.w	x_pos(a0),d0
	move.w	d0,bw_fx(a0)
	clr.b	bw_body(a0)		; initialize bowser's body controls
	clr.b	bw_collapse(a0)		; and bridge collapse offset
	move.w	d0,bw_origx(a0)		; store original horizontal position here
	move.b	#$DF,bw_breath(a0)	; store something here
	move.b	#2,bw_dir(a0)		; port: SMB1 stores $DF here too; every 16 frames it becomes 2 (left)
	move.b	#$20,bw_feet(a0)	; set bowser's feet timer and in enemy timer
	move.b	#$20,bw_frametmr(a0)
	move.b	#5,bw_hp(a0)		; give bowser 5 hit points
	move.b	#5/2,bw_speed(a0)	; set default movement speed here (lsr of the 5)
	clr.b	bw_flamectl(a0)
	clr.b	bw_state(a0)
	move.b	#$21,bw_range(a0)
	bra.w	Bowser_Draw

; ---------------------------------------------------------------------------
Bowser_Main:
	; SMB1's NMI: EnemyFrameTimer and BowserFireBreathTimer count down every frame
	tst.b	bw_frametmr(a0)
	beq.s	+
	subq.b	#1,bw_frametmr(a0)
+	tst.b	bw_breath(a0)
	beq.s	+
	subq.b	#1,bw_breath(a0)
+	move.b	bw_state(a0),d0
	bmi.w	RemoveBridge
	bne.w	MoveD_Bowser		; RunBowser: defeated or falling

; BowserControl (main.asm:7301)
BowserControl:
	tst.b	bw_body(a0)		; check bowser's mouth
	bmi.w	HammerChk		; if open, skip a whole section starting here
; FeetTmr:
	subq.b	#1,bw_feet(a0)		; decrement timer to control bowser's feet
	bne.s	ResetMDr		; if not expired, skip this part
	move.b	#$20,bw_feet(a0)	; otherwise, reset timer
	bchg	#0,bw_body(a0)		; and invert bit used to control bowser's feet
ResetMDr:
	move.b	(Level_frame_counter+1).w,d0
	andi.b	#%00001111,d0		; if not on every sixteenth frame, skip
	bne.s	B_FaceP			; ahead to continue code
	move.b	#2,bw_dir(a0)		; otherwise reset moving/facing direction every sixteen frames
B_FaceP:
	tst.b	bw_frametmr(a0)		; if timer set here expired,
	beq.s	GetPRCmp		; branch to next section
	move.w	bw_fx(a0),d0		; get horizontal difference between player and bowser,
	sub.w	(MainCharacter+x_pos).w,d0
	bpl.s	GetPRCmp		; and branch if bowser to the right of the player
	move.b	#1,bw_dir(a0)		; set bowser to move and face to the right
	move.b	#2,bw_speed(a0)		; set movement speed
	move.b	#$20,bw_frametmr(a0)	; set timer here
	move.b	#$20,bw_breath(a0)	; set timer used for bowser's flame
	move.w	bw_fx(a0),d0
	sub.w	objoff_2C(a0),d0	; port: SMB1 "cmp #$c8" - if bowser to the right past
	cmpi.w	#Bowser_ChaseLimit,d0	; a certain point,
	bge.s	HammerChk		; skip ahead to some other section
GetPRCmp:
	move.b	(Level_frame_counter+1).w,d0
	andi.b	#%00000011,d0
	bne.s	HammerChk		; execute this code every fourth frame, otherwise branch
	move.w	bw_fx(a0),d0
	cmp.w	bw_origx(a0),d0		; if bowser not at original horizontal position,
	bne.s	GetDToO			; branch to skip this part
	jsr	(RandomNumber).l
	andi.w	#%00000011,d0		; get pseudorandom offset
	lea	(PRandomRange).l,a2
	move.b	(a2,d0.w),bw_range(a0)	; load value using pseudorandom offset and store here
GetDToO:
	move.b	bw_speed(a0),d0		; add movement speed to bowser's horizontal
	ext.w	d0			; coordinate and save as new horizontal position
	add.w	d0,bw_fx(a0)
	cmpi.b	#1,bw_dir(a0)		; if bowser moving and facing to the right, skip ahead
	beq.s	HammerChk
	moveq	#-1,d1			; set default movement speed here (move left)
	move.w	bw_fx(a0),d0		; get difference of current vs. original
	sub.w	bw_origx(a0),d0		; horizontal position
	bpl.s	CompDToO		; if current position to the right of original, skip ahead
	neg.w	d0			; get two's compliment
	moveq	#1,d1			; set alternate movement speed here (move right)
CompDToO:
	moveq	#0,d2
	move.b	bw_range(a0),d2
	cmp.w	d2,d0			; compare difference with pseudorandom value
	blo.s	HammerChk		; if difference < pseudorandom value, leave speed alone
	move.b	d1,bw_speed(a0)		; otherwise change bowser's movement speed
HammerChk:
	tst.b	bw_frametmr(a0)		; if timer set here not expired yet, skip ahead to
	bne.s	MakeBJump		; some other section of code
	bsr.w	MoveEnemySlowVert	; otherwise start by moving bowser downwards
	move.b	(Level_frame_counter+1).w,d0
	andi.b	#%00000011,d0		; check to see if it's time to execute sub
	bne.s	SetHmrTmr		; if not, skip sub, otherwise
	bsr.w	SpawnHammerObj		; execute sub on every fourth frame to spawn misc object (hammer)
SetHmrTmr:
	move.w	y_pos(a0),d0		; get current vertical position
	cmp.w	bw_ground(a0),d0	; if still above a certain point
	blo.s	ChkFireB		; then skip to world number check for flames
	move.w	bw_ground(a0),y_pos(a0)	; port: stand on the floor exactly
	clr.w	y_vel(a0)
	jsr	(RandomNumber).l
	andi.w	#%00000011,d0		; get pseudorandom offset
	lea	(PRandomRange).l,a2
	move.b	(a2,d0.w),bw_frametmr(a0)	; get value using pseudorandom offset, set for timer here
	bra.s	ChkFireB		; jump to execute flames code
MakeBJump:
	cmpi.b	#1,bw_frametmr(a0)	; if timer not yet about to expire,
	bne.s	ChkFireB		; skip ahead to next part
	subq.w	#1,y_pos(a0)		; otherwise decrement vertical coordinate
	move.w	#-$200,y_vel(a0)	; set vertical speed to move bowser upwards (InitVStf, $FE)
ChkFireB:				; (world 8: flames)
	tst.b	bw_breath(a0)		; check timer here
	bne.s	Bowser_DrawCollide	; if not expired yet, skip all of this
	move.b	#$20,bw_breath(a0)	; set timer here
	bchg	#7,bw_body(a0)		; invert bowser's mouth bit to open and close bowser's mouth
	beq.s	Bowser_DrawCollide	; if bowser's mouth now open, loop back (the timer is set)
	moveq	#0,d0			; get timing for bowser's flame (SetFlameTimer)
	move.b	bw_flamectl(a0),d0
	addq.b	#1,bw_flamectl(a0)
	andi.b	#%00000111,bw_flamectl(a0)
	lea	(FlameTimerData).l,a2
	move.b	(a2,d0.w),bw_breath(a0)	; set value as timer here
	bsr.w	InitBowserFlame		; port: SMB1 queues the flame in the frenzy buffer
Bowser_DrawCollide:
	move.b	#$8E,collision_flags(a0)	; harmful: touching Bowser hurts (no stomping him)
	bra.w	Bowser_Draw

; ---------------------------------------------------------------------------
; MoveEnemySlowVert (main.asm:4631): downward force $0F, maximum speed 2
MoveEnemySlowVert:
	move.w	#$0F,d0
	move.w	#$0200,d1
	; (fall through)
; d0 = force, d1 = maximum speed (8.8). SMB1 ImposeGravity: move, then add the
; force; at the maximum whole speed with a fraction of $80 or more, clamp.
ImposeGravityS2:
	movem.w	d0-d1,-(sp)		; (ObjectMove uses d0/d1)
	jsr	(ObjectMove).l
	movem.w	(sp)+,d0-d1
	add.w	d0,y_vel(a0)
	move.w	d1,d2
	addi.w	#$80,d2
	cmp.w	y_vel(a0),d2
	bgt.s	+
	move.w	d1,y_vel(a0)
+	rts

; ---------------------------------------------------------------------------
; Bowser's position on screen: SMB1 draws the front at x (the head, left when
; facing left) and the rear 16 px behind; the mapping frame is the 32x32 pair.
Bowser_Draw:
	move.w	bw_fx(a0),d0
	bclr	#render_flags.x_flip,render_flags(a0)
	cmpi.b	#1,bw_dir(a0)
	beq.s	+
	addi.w	#16,d0			; facing left: front on the left half
	bra.s	++
+	bset	#render_flags.x_flip,render_flags(a0)	; facing right: front on the right half
+	move.w	d0,x_pos(a0)
	moveq	#BowserFrame_Bowser,d0
	tst.b	bw_body(a0)
	bpl.s	+
	addq.b	#2,d0			; mouth open
+	btst	#0,bw_body(a0)
	beq.s	+
	addq.b	#1,d0			; feet frame 2
+	move.b	d0,mapping_frame(a0)
	bclr	#render_flags.y_flip,render_flags(a0)
	cmpi.b	#$20,bw_state(a0)	; defeated by fireballs: upside down (FlipBowserOver)
	bne.s	+
	bset	#render_flags.y_flip,render_flags(a0)
+	jmp	(DisplaySprite).l

; ---------------------------------------------------------------------------
; BridgeCollapse's RemoveBridge (main.asm:7243). There is no bridge in WFZ: the
; collapse is its timing and sounds - the feet toggle every 4 frames, 15
; times - then Bowser falls.
RemoveBridge:
	subq.b	#1,bw_feet(a0)		; decrement timer to control bowser's feet
	bne.s	NoBFall			; if not expired, skip all of this
	move.b	#4,bw_feet(a0)		; otherwise, set timer now
	bchg	#0,bw_body(a0)		; invert bit to control bowser's feet
	move.b	#SndID_BowserBlast,(Sound_Queue.SFX0).w	; the fireworks/gunfire sound and
	move.b	#SndID_BowserShatter,(Sound_Queue.SFX1).w	; the brick shatter sound: the bridge collapsing
	addq.b	#1,bw_collapse(a0)	; increment bridge collapse offset
	cmpi.b	#$F,bw_collapse(a0)	; if bridge collapse offset has not yet reached
	bne.s	NoBFall			; the end, go ahead and skip this part
	clr.w	y_vel(a0)		; initialize whatever vertical speed bowser has
	move.b	#$40,bw_state(a0)	; set bowser's state to one of defeated states (d6 set)
	move.b	#SndID_BowserFall,(Sound_Queue.SFX2).w	; play bowser defeat sound
NoBFall:
	bra.w	Bowser_Draw

; MoveD_Bowser (main.asm:7239) / RunBowser: fall until off the screen, then
; KillAllEnemies.
MoveD_Bowser:
	clr.b	collision_flags(a0)
	bsr.w	MoveEnemySlowVert	; do a sub to move bowser downwards
	move.w	(Camera_Y_pos).w,d0
	addi.w	#224+32,d0
	cmp.w	y_pos(a0),d0		; low enough (SMB1: y $E0)?
	bhs.w	Bowser_Draw
	st.b	(Bowser_KillAll).w	; KillAllEnemies: flames and hammers go
	clr.w	(Bowser_Ptr).w
	jmp	(DeleteObject).l

; ---------------------------------------------------------------------------
; HurtBowser (main.asm:8351), from FireballEnemyCollision. a1 = Bowser.
Bowser_FireballHit:
	tst.b	bw_state(a1)
	bne.s	.done
	subq.b	#1,bw_hp(a1)		; decrement bowser's hit points
	bne.s	.done			; if bowser still has hit points, branch to leave
	move.w	#-$200,y_vel(a1)	; set vertical speed to make defeated bowser jump a little
	move.b	#$20,bw_state(a1)	; set defeated enemy state (world 8: Bowser himself, upside down)
	clr.b	collision_flags(a1)
	move.b	#SndID_BowserFall,(Sound_Queue.SFX2).w	; load bowser defeat sound
	move.l	a0,-(sp)
	move.l	#5000/10,d0		; award 5000 points to player for defeating bowser (S2 counts
					; tens; AddPoints adds all 32 bits - a .w here left junk above)
	jsr	(AddPoints).l
	movea.l	(sp)+,a0
.done:
	rts

; ---------------------------------------------------------------------------
; SpawnHammerObj (main.asm:3824): a random misc slot (d2-d0 of the LFSR, or
; d3 if those are all clear) gets a hammer if it is free.
SpawnHammerObj:
	jsr	(RandomNumber).l
	moveq	#%00000111,d1
	and.b	d0,d1			; if any bits are set, use as offset
	bne.s	SetMOfs
	moveq	#%00001000,d1		; get d3 from same part of LSFR
	and.b	d0,d1
SetMOfs:
	lea	(Bowser_HammerSlots).w,a2
	tst.b	(a2,d1.w)		; if a hammer is in that slot,
	bne.s	NoHammer		; leave
	jsr	(AllocateObject).l	; port: the hammer is an S2 object
	bne.s	NoHammer
	st.b	(a2,d1.w)
	move.b	#ObjID_BowserMisc,id(a1)
	move.b	#2,subtype(a1)
	move.b	d1,hm_slot(a1)
	move.b	#$10,hm_state(a1)	; save hammer's state here ($90, d7 masked off)
NoHammer:
	rts

; ---------------------------------------------------------------------------
; InitBowserFlame's SpawnFromMouth (main.asm:5634)
InitBowserFlame:
	jsr	(AllocateObject).l
	bne.s	.done
	move.b	#ObjID_BowserMisc,id(a1)
	clr.b	subtype(a1)
	move.w	bw_fx(a0),d0
	subi.w	#$E,d0			; subtract 14 pixels from bowser's horizontal position
	move.w	d0,fl_left(a1)
	move.w	y_pos(a0),d0
	subi.w	#16-8,d0		; add 8 pixels to bowser's vertical position (his top = y - 16)
	move.w	d0,fl_top(a1)
	jsr	(RandomNumber).l
	andi.w	#%00000011,d0		; get 2 LSB from first part of LSFR
	add.w	d0,d0
	move.w	FlameYPosData(pc,d0.w),d0	; get value here using bits as offset
	add.w	bw_ground(a0),d0	; port: relative to Bowser's top when standing
	subi.w	#16,d0
	move.w	d0,fl_target(a1)
	moveq	#1,d1			; load default offset
	cmp.w	fl_top(a1),d0		; compare value to flame's current vertical position
	bhs.s	+			; if less, do not increment offset
	moveq	#-1,d1
+	move.b	d1,fl_step(a1)		; to vertical movement force
	move.b	#SndID_BowserFlame,(Sound_Queue.SFX1).w	; load bowser's flame sound into queue
.done:
	rts
; FlameYPosData (main.asm:5591) $90, $80, $70, $90, relative to Bowser's
; standing top ($80)
FlameYPosData:	dc.w $10, 0, -$10, $10

; ===========================================================================
; Bowser's flame, hammers and the axe
; ===========================================================================
ObjBowserMisc:
	tst.b	(Bowser_KillAll).w	; KillAllEnemies (not the axe)
	beq.s	+
	cmpi.b	#4,subtype(a0)
	bne.w	BowserMisc_Delete
+	moveq	#0,d0
	move.b	routine(a0),d0
	move.w	ObjBowserMisc_Index(pc,d0.w),d1
	jmp	ObjBowserMisc_Index(pc,d1.w)
ObjBowserMisc_Index:	offsetTable
	offsetTableEntry.w BowserMisc_Init	; 0
	offsetTableEntry.w ProcBowserFlame	; 2
	offsetTableEntry.w ProcHammerObj	; 4
	offsetTableEntry.w Axe_Main		; 6
; ---------------------------------------------------------------------------
BowserMisc_Init:
	move.l	#MapUnc_Bowser,mappings(a0)
	move.w	#make_art_tile(ArtTile_ArtNem_WFZBoss,BowserPalLine,0),art_tile(a0)
	move.b	#1<<render_flags.level_fg,render_flags(a0)
	move.b	#3,priority(a0)
	move.b	#$10,width_pixels(a0)
	move.b	subtype(a0),d0
	addq.b	#2,d0
	move.b	d0,routine(a0)
	cmpi.b	#2,d0
	bne.s	+
	move.b	#$9B,collision_flags(a0)	; flame: harmful
	move.b	#BowserFrame_Flame,mapping_frame(a0)
	move.b	#$C,width_pixels(a0)
	bra.w	ProcBowserFlame
+	cmpi.b	#4,d0
	bne.s	+
	move.b	#$8B,collision_flags(a0)	; hammer: harmful
	move.b	#BowserFrame_Hammer,mapping_frame(a0)
	bra.w	ProcHammerObj
+	; the axe: standing on the floor (user: raising it 16 px was too high)
	move.b	#BowserFrame_Axe,mapping_frame(a0)
	move.b	#8,y_radius(a0)
	move.b	#8,x_radius(a0)
	jsr	(ObjCheckFloorDist).l
	add.w	d1,y_pos(a0)
	bra.w	Axe_Main

; ---------------------------------------------------------------------------
; ProcBowserFlame (main.asm:7491): left by 1 px + $40/256 a frame, towards
; its target height 1 px a frame; flipped vertically every 2 frames.
ProcBowserFlame:
	subi.b	#$40,fl_xfrac(a0)	; subtract value from movement force
	scs	d0			; (borrow)
	ext.w	d0
	subq.w	#1,d0			; subtract one from horizontal position to move to the left
	add.w	d0,fl_left(a0)
	move.w	fl_top(a0),d0		; load vertical coordinate
	cmp.w	fl_target(a0),d0	; compare against coordinate data
	beq.s	SetGfxF			; if equal, branch and do not modify coordinate
	move.b	fl_step(a0),d1
	ext.w	d1
	add.w	d1,fl_top(a0)		; otherwise add value here to coordinate and store as new vertical coordinate
SetGfxF:
	move.w	fl_left(a0),d0
	addi.w	#12,d0
	move.w	d0,x_pos(a0)
	move.w	fl_top(a0),d0
	addq.w	#4,d0
	move.w	d0,y_pos(a0)
	bclr	#render_flags.y_flip,render_flags(a0)
	btst	#1,(Level_frame_counter+1).w	; invert vertical flip bit every 2 frames
	beq.s	+
	bset	#render_flags.y_flip,render_flags(a0)
+	bsr.w	BowserMisc_Offscreen
	bne.w	BowserMisc_Delete
	jmp	(DisplaySprite).l

; ---------------------------------------------------------------------------
; ProcHammerObj (main.asm:3856): held over Bowser's head for a while, then
; thrown his way (1 px a frame) with a -2 jump, under gravity $10 / maximum 4.
HammerXSpdData:	dc.b 1, -1		; $10, $F0 (4.4) in px/frame
	even
ProcHammerObj:
	move.w	(Bowser_Ptr).w,d0
	movea.w	d0,a1
	move.b	hm_state(a0),d0		; otherwise get hammer's state
	andi.b	#%01111111,d0		; mask out d7
	cmpi.b	#2,d0			; check hammer's state
	beq.s	SetHSpd			; if currently at 2, branch
	bhi.s	SetHPos			; if greater than 2, branch elsewhere
	move.w	#$10,d0			; set downward movement force
	move.w	#$0400,d1		; set maximum vertical speed
	bsr.w	ImposeGravityS2		; do sub to impose gravity on hammer and move vertically
	move.b	hm_xspd(a0),d0		; move it horizontally
	ext.w	d0
	add.w	d0,x_pos(a0)
	bra.s	DrawHammer
SetHSpd:
	move.w	#-$200,y_vel(a0)	; set hammer's vertical speed
	moveq	#0,d1
	tst.w	(Bowser_Ptr).w
	beq.s	+
	move.b	bw_dir(a1),d1		; get enemy's moving direction
+	subq.b	#1,d1			; decrement to use as offset
	andi.w	#1,d1
	move.b	HammerXSpdData(pc,d1.w),hm_xspd(a0)	; get proper speed to use based on moving direction
SetHPos:
	subq.b	#1,hm_state(a0)		; decrement hammer's state
	tst.w	(Bowser_Ptr).w
	beq.s	DrawHammer
	move.w	bw_fx(a1),d0		; get enemy's horizontal position
	addi.w	#2+8,d0			; set position 2 pixels to the right (+8: the hammer's centre)
	move.w	d0,x_pos(a0)
	move.w	y_pos(a1),d0		; get enemy's vertical position
	subi.w	#16+$0A-8,d0		; move position 10 pixels upward (from his top; +8: centre)
	move.w	d0,y_pos(a0)
; DrawHammer (main.asm:10514): spinning (every 4 frames) once thrown
DrawHammer:
	moveq	#0,d0
	cmpi.b	#1,hm_state(a0)		; check to see if set to 1 yet
	bne.s	+
	move.b	(Level_frame_counter+1).w,d0
	lsr.b	#2,d0
	andi.b	#%00000011,d0		; changes every four frames
+	addi.b	#BowserFrame_Hammer,d0
	move.b	d0,mapping_frame(a0)
	cmpi.b	#1,hm_state(a0)
	bne.s	+
	bsr.w	BowserMisc_Offscreen	; offscreen: the slot is freed
	bne.s	BowserMisc_Delete
+	jmp	(DisplaySprite).l

; ---------------------------------------------------------------------------
; The axe: Mario touching it wins the fight (SMB1 checks the axe metatile in
; the player's block collision; here a box test). Then it disappears
; (RemoveCoin_Axe).
Axe_Main:
	tst.b	(Bowser_FightOn).w
	beq.s	.show
	lea	(MainCharacter).w,a1
	move.w	x_pos(a1),d0
	sub.w	x_pos(a0),d0
	bpl.s	+
	neg.w	d0
+	cmpi.w	#8+7,d0
	bhs.s	.show
	moveq	#0,d1
	move.b	y_radius(a1),d1
	addq.w	#8,d1
	move.w	y_pos(a1),d0
	sub.w	y_pos(a0),d0
	bpl.s	+
	neg.w	d0
+	cmp.w	d1,d0
	bhs.s	.show
	st.b	(Bowser_AxeTouched).w
	jmp	(DeleteObject).l
.show:
	jmp	(DisplaySprite).l

; ---------------------------------------------------------------------------
; Z clear (bne) if the object is out of the camera's view (with a margin).
BowserMisc_Offscreen:
	move.w	x_pos(a0),d0
	sub.w	(Camera_X_pos).w,d0
	cmpi.w	#-32,d0
	blt.s	.out
	cmpi.w	#320+32,d0
	bgt.s	.out
	move.w	y_pos(a0),d0
	sub.w	(Camera_Y_pos).w,d0
	cmpi.w	#-64,d0
	blt.s	.out
	cmpi.w	#224+32,d0
	bgt.s	.out
	moveq	#0,d0
	rts
.out:
	moveq	#1,d0
	rts

BowserMisc_Delete:
	cmpi.b	#4,routine(a0)		; a hammer frees its misc slot
	bne.s	+
	moveq	#0,d0
	move.b	hm_slot(a0),d0
	lea	(Bowser_HammerSlots).w,a2
	clr.b	(a2,d0.w)
+	jmp	(DeleteObject).l

; ---------------------------------------------------------------------------
; Hook: ObjC5_Init's "move.b subtype(a0),d0 / subi.b #$90,d0" (8 bytes, jsr +
; nop). The laser case (routine 2) becomes the Bowser fight controller; the
; rest of ObjC5 (walls, Robotnik) stays. (Sonic/Tails are being phased out,
; so the original fight doesn't need to remain in the Mario build.)
Mario_WFZBossInit:
	move.b	subtype(a0),d0		; (replaced instructions)
	subi.b	#$90,d0
	cmpi.b	#2,d0			; the laser case?
	bne.s	+
	move.b	#ObjID_Bowser,id(a0)
	moveq	#0,d0			; ObjBowser's init next frame
+	rts
