; ===========================================================================
; Mario animation and DPLC
; ---------------------------------------------------------------------------
; Mario_Animate   - anim IDs whose MarioAniData script starts with $FF are
;                   Mario's own (walk/run/jump/skid/crouch...): they run SMB1's
;                   PlayerGfxHandler/ProcessPlayerAction (main.asm:11797-12102),
;                   then MAnim_Orient rotates the frame to the floor angle.
;                   Every other ID is set by S2 objects (springs, hang bars,
;                   bubbles, death...) and plays an S2-style script.
; MarioAniData    - covers every AniIDSonAni_* ID, because other objects
;                   write anim(a1) directly.
; LoadMarioDynPLC - LoadSonicDynPLC (s2.asm:38838) with a colour-bank select.
; ===========================================================================

; Big-Mario frame shorthands (PlayerGraphicsTable rows; see mario_frames.asm).
; Scripts are written with big frames; Mario_TranslateFrame converts them for
; small Mario, mirroring SMB1's GetGfxOffsetAdder (+8 bytes = +1 row block).
MF_Walk1	= MarioFrame_GfxBase+$00	; PlayerGfxOffset $00
MF_Walk2	= MarioFrame_GfxBase+$01	; $08
MF_Walk3	= MarioFrame_GfxBase+$02	; $10
MF_Skid		= MarioFrame_GfxBase+$03	; $18
MF_Jump		= MarioFrame_GfxBase+$04	; $20
MF_Swim1	= MarioFrame_GfxBase+$05	; $28
MF_Swim2	= MarioFrame_GfxBase+$06	; $30
MF_Swim3	= MarioFrame_GfxBase+$07	; $38
MF_Climb1	= MarioFrame_GfxBase+$08	; $40
MF_Climb2	= MarioFrame_GfxBase+$09	; $48
MF_Crouch	= MarioFrame_GfxBase+$0A	; $50
MF_Fire		= MarioFrame_GfxBase+$0B	; $58
MF_Killed	= MarioFrame_GfxBase+$16	; $B0 (small table; SMB1 uses it for both sizes)
MF_SmallStand	= MarioFrame_GfxBase+$17	; $B8
MF_GrowMid	= MarioFrame_GfxBase+$18	; $C0
MF_Stand	= MarioFrame_GfxBase+$19	; $C8 (big standing)
MF_SmallBase	= MarioFrame_GfxBase+$0C	; $60: first small-table row
MF_SmallJump	= MF_SmallBase+4		; $80

; ---------------------------------------------------------------------------
; Subroutine to animate Mario (Sonic_Animate equivalent)
; ---------------------------------------------------------------------------
Mario_Animate:
	lea	(MarioAniData).l,a1
	moveq	#0,d0
	move.b	anim(a0),d0
	cmp.b	prev_anim(a0),d0	; has the animation changed?
	beq.s	.do
	move.b	d0,prev_anim(a0)
	move.b	#0,anim_frame(a0)
	move.b	#0,anim_frame_duration(a0)
	bclr	#status.player.pushing,status(a0)
.do:
	; PlayerGfxHandler: if grow/shrink flag set, then branch to some other code
	; (port: whatever the anim, e.g. the shrink plays during S2's hurt knockback)
	tst.b	(PlayerChangeSizeFlag).w
	beq.s	+
	cmpi.b	#6,routine(a0)		; not once dead
	blo.w	MAnim_DoChangeSize
+
	move.w	d0,d1
	add.w	d1,d1
	movea.l	a1,a2
	adda.w	(a2,d1.w),a2
	cmpi.b	#$FF,(a2)		; one of Mario's own actions?
	beq.s	MAnim_SMB
	jsr	(SAnim_Do).l		; S2's generic script engine (d0 = anim, a1 = table)
	move.b	anim(a0),d0
	cmp.b	prev_anim(a0),d0	; did the script end with $FD (switch anim)?
	bne.s	Mario_Animate		; then show the new anim's frame right away
	bra.w	Mario_TranslateFrame

; ---------------------------------------------------------------------------
; PlayerGfxHandler (main.asm:11797-11846), minus the parts S2 already does
; (injury flicker: Sonic_Display; PlayerKilled: the Death scripts).
; Fireball-throw frames (PlayerGfxProcessing) come with the fireballs, Phase 6.
; ---------------------------------------------------------------------------
MAnim_SMB:
	btst	#status.player.rolling,status(a0)	; port: rolls are always forced by S2
	bne.w	MAnim_ForcedRoll			; (tubes, pinball), SMB1 has none
	bsr.w	ProcessPlayerAction		; find proper offset to graphics table by player's actions
	move.b	d0,(PlayerGfxOffset).w
	moveq	#0,d1
	move.b	d0,d1
	lsr.b	#3,d1				; row of PlayerGraphicsTable
	moveq	#MarioFrame_GfxBase,d0
	add.b	d1,d0				; upright mapping frame
	; swim kick: if swimming and not on the ground, every 8 frames out of 16
	; replace the feet with SwimKickTileNum (pre-composed kick frames)
	tst.b	(Mario_SwimForces).w		; (port: actually swimming - a C-held jump isn't, yet)
	beq.s	.orient
	tst.b	(Player_State).w
	beq.s	.orient
	btst	#2,(Level_frame_counter+1).w	; FrameCounter d2
	bne.s	.orient
	lea	MarioSwimKickXlat(pc),a1
	move.b	(a1,d1.w),d2		; 0 = no kick variant for this row
	beq.s	.orient				; (small swim 3 already shows the kick tile)
	move.b	d2,d0
.orient:
	; PlayerGfxProcessing (main.asm:11857): fireball throwing pose. Shown while
	; the animation timer is below the throw timer (a few frames); all four
	; rows from the throw graphics when still, else only the top three
	; (composite frames keep the current legs).
	move.b	(FireballThrowingTimer).w,d2	; if fireball throw timer not set, skip to the end
	beq.s	.noThrow
	clr.b	(FireballThrowingTimer).w	; initialize fireball throw timer
	move.b	(PlayerAnimTimer).w,d3		; get animation frame timer
	cmp.b	d2,d3				; compare to fireball throw timer
	bhs.s	.noThrow			; if animation frame timer => fireball throw timer skip to end
	move.b	d3,(FireballThrowingTimer).w	; otherwise store animation timer into fireball throw timer
	tst.b	(PlayerSize).w			; port: only big (fiery) Mario has the throw pose
	bne.s	.noThrow
	moveq	#MF_Fire,d0			; load offset for throwing, four rows
	tst.w	(Player_X_Speed).w
	bne.s	+
	tst.b	(Left_Right_Buttons).w		; check for horizontal speed or left/right button press
	beq.s	.throwPose
+	lea	MarioThrowXlat(pc),a1
	move.b	(a1,d1.w),d2		; otherwise only three rows: the composite
	beq.s	.throwPose			; (no composite for this row: full pose)
	move.b	d2,d0
.throwPose:
	bsr.w	MAnim_AngleQuadrant
	andi.w	#2,d1				; no rotated throw art: upright or upside down
	bra.w	MAnim_Orient
.noThrow:
	bsr.w	MAnim_AngleQuadrant
	bra.w	MAnim_Orient

; Big rows -> throw composite (fire rows 1-3 over this row's 4th), 0 = none.
MarioThrowXlat:
	dc.b	MarioFrame_Throw_Walk1, MarioFrame_Throw_Walk2, MarioFrame_Throw_Walk3
	dc.b	MarioFrame_Throw_Skid, MarioFrame_Throw_Jump
	dc.b	MarioFrame_Throw_Swim1, MarioFrame_Throw_Swim2, MarioFrame_Throw_Swim3
	dc.b	0, 0, 0, 0			; climb 1-2, crouch, fire
	dc.b	0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0	; small rows, grow mid
	dc.b	MarioFrame_Throw_Stand
MarioThrowXlat_End:
	if MarioThrowXlat_End-MarioThrowXlat<>26
		fatal "MarioThrowXlat must have one entry per PlayerGraphicsTable row."
	endif
	even

; Grow/shrink: during the change Mario keeps the big radius, so small rows use
; the "tall" frames anchored to it.
MAnim_DoChangeSize:
	bsr.w	HandleChangeSize		; find proper offset to graphics table for grow/shrink
	move.b	d0,(PlayerGfxOffset).w
	lsr.b	#3,d0
	moveq	#MarioFrame_GfxBase,d1
	cmpi.b	#$60/8,d0
	blo.s	+
	cmpi.b	#$B8/8,d0
	bhi.s	+
	moveq	#MarioFrame_TallSmallBase,d1
+	add.b	d1,d0
	moveq	#0,d1				; upright
	bra.w	MAnim_Orient

; Rows -> swim-kick frames (SwimKickTileNum on sprite 7), 0 = none.
MarioSwimKickXlat:
	dc.b	0, 0, 0, 0, 0
	dc.b	MarioFrame_Big_Swim1_Kick, MarioFrame_Big_Swim2_Kick, MarioFrame_Big_Swim3_Kick
	dc.b	0, 0, 0, 0, 0, 0, 0, 0, 0
	dc.b	MarioFrame_Small_Swim1_Kick, MarioFrame_Small_Swim2_Kick
	dc.b	0, 0, 0, 0, 0, 0, 0
MarioSwimKickXlat_End:
	if MarioSwimKickXlat_End-MarioSwimKickXlat<>26
		fatal "MarioSwimKickXlat must have one entry per PlayerGraphicsTable row."
	endif

; ---------------------------------------------------------------------------
; ProcessPlayerAction (main.asm:11955-12060)
; Output: d0.b = PlayerGfxOffset. (Climbing, Player_State 3, is not ported.)
; ---------------------------------------------------------------------------
PlayerGfxTblOffsets:
	dc.b	$20, $28, $C8, $18, $00, $40, $50, $58
	dc.b	$80, $88, $B8, $78, $60, $A0, $B0, $B8

ProcessPlayerAction:
	move.b	(Player_State).w,d0	; get player's state
	cmpi.b	#2,d0
	beq.s	ActionFalling		; if falling, branch here
	cmpi.b	#1,d0
	bne.s	ProcOnGroundActs	; if not jumping, branch here
	tst.b	(Mario_SwimForces).w	; (port: actually swimming - a C-held jump isn't, yet)
	bne.s	ActionSwimming		; if swimming flag set, branch elsewhere
	moveq	#6,d1			; load offset for crouching
	tst.b	(CrouchingFlag).w	; get crouching flag
	bne.s	NonAnimatedActs		; if set, branch to get offset for graphics table
	moveq	#0,d1			; otherwise load offset for jumping
	bra.s	NonAnimatedActs		; go to get offset to graphics table

ProcOnGroundActs:
	moveq	#6,d1			; load offset for crouching
	tst.b	(CrouchingFlag).w	; get crouching flag
	bne.s	NonAnimatedActs		; if set, branch to get offset for graphics table
	moveq	#2,d1			; load offset for standing
	tst.w	(Player_X_Speed).w	; check player's horizontal speed
	bne.s	+
	tst.b	(Left_Right_Buttons).w	; and left/right controller bits
	beq.s	NonAnimatedActs		; if no speed or buttons pressed, use standing offset
+	cmpi.b	#$09,(Player_XSpeedAbsolute).w	; load walking/running speed
	blo.s	ActionWalkRun		; if less than a certain amount, branch, too slow to skid
	move.b	(Player_MovingDir).w,d0	; otherwise check to see if moving direction
	and.b	(PlayerFacingDir).w,d0	; and facing direction are the same
	bne.s	ActionWalkRun		; if moving direction = facing direction, branch, don't skid
	addq.w	#1,d1			; otherwise increment to skid offset ($03)

NonAnimatedActs:
	bsr.s	GetGfxOffsetAdder	; do a sub here to get offset adder for graphics table
	clr.b	(PlayerAnimCtrl).w	; initialize animation frame control
	move.b	PlayerGfxTblOffsets(pc,d1.w),d0	; load offset to graphics table using size as offset
	rts

ActionFalling:
	moveq	#4,d1			; load offset for walking/running
	bsr.s	GetGfxOffsetAdder	; get offset to graphics table
	bra.s	GetCurrentAnimOffset	; execute instructions for falling state

ActionWalkRun:
	moveq	#4,d1			; load offset for walking/running
	bsr.s	GetGfxOffsetAdder	; get offset to graphics table
	bra.s	FourFrameExtent		; execute instructions for normal state

ActionSwimming:
	moveq	#1,d1			; load offset for swimming
	bsr.s	GetGfxOffsetAdder
	move.b	(JumpSwimTimer).w,d0	; check jump/swim timer
	or.b	(PlayerAnimCtrl).w,d0	; and animation frame control
	bne.s	FourFrameExtent		; if any one of these set, branch ahead
	tst.b	(A_B_Buttons).w		; check for A button pressed (bit 7)
	bmi.s	FourFrameExtent		; branch to same place if A button pressed

GetCurrentAnimOffset:
	move.b	(PlayerAnimCtrl).w,d0	; get animation frame control
	bra.s	GetOffsetFromAnimCtrl	; jump to get proper offset to graphics table

FourFrameExtent:
	moveq	#3,d2			; load upper extent for frame control
; AnimationControl:
	bsr.s	GetCurrentAnimOffset	; get proper offset to graphics table
	tst.b	(PlayerAnimTimer).w	; load animation frame timer
	bne.s	ExAnimC			; branch if not expired
	move.b	(PlayerAnimTimerSet).w,(PlayerAnimTimer).w	; get animation frame timer amount
	move.b	(PlayerAnimCtrl).w,d3
	addq.b	#1,d3			; add one to animation frame control
	cmp.b	d2,d3			; compare to upper extent
	blo.s	SetAnimC		; if frame control + 1 < upper extent, use as next
	moveq	#0,d3			; otherwise initialize frame control
SetAnimC:
	move.b	d3,(PlayerAnimCtrl).w	; store as new animation frame control
ExAnimC:
	rts				; offset to graphics table is in d0

GetGfxOffsetAdder:
	tst.b	(PlayerSize).w		; get player's size
	beq.s	SzOfs			; if player big, use current offset as-is
	addq.w	#8,d1			; otherwise add eight bytes to offset for small player
SzOfs:
	rts

ChangeSizeOffsetAdder:
	dc.b	$00, $01, $00, $01, $00, $01, $02, $00, $01, $02
	dc.b	$02, $00, $02, $00, $02, $00, $02, $00, $02, $00
	even

; HandleChangeSize (main.asm:12066-12102). Output: d0.b = PlayerGfxOffset.
HandleChangeSize:
	moveq	#0,d1
	move.b	(PlayerAnimCtrl).w,d1	; get animation frame control
	move.b	(Level_frame_counter+1).w,d0
	andi.b	#%00000011,d0		; get frame counter and execute this code every
	bne.s	GorSLog			; fourth frame, otherwise branch ahead
	addq.b	#1,d1			; increment frame control
	cmpi.b	#$0A,d1			; check for preset upper extent
	blo.s	CSzNext			; if not there yet, skip ahead to use
	moveq	#0,d1			; otherwise initialize both grow/shrink flag
	clr.b	(PlayerChangeSizeFlag).w	; and animation frame control
CSzNext:
	move.b	d1,(PlayerAnimCtrl).w	; store proper frame control
GorSLog:
	tst.b	(PlayerSize).w		; get player's size
	bne.s	ShrinkPlayer		; if player small, skip ahead to next part
	move.b	ChangeSizeOffsetAdder(pc,d1.w),d0	; get offset adder based on frame control as offset
	moveq	#$F,d1			; load offset for player growing

GetOffsetFromAnimCtrl:
	lsl.b	#3,d0			; multiply animation frame control by eight
	lea	PlayerGfxTblOffsets(pc),a1
	add.b	(a1,d1.w),d0		; add to offset to graphics table
	rts				; and return with result in d0

ShrinkPlayer:
	addi.w	#$0A,d1			; add ten bytes to frame control as offset
	moveq	#9,d2			; load offset for small player swimming
	move.b	ChangeSizeOffsetAdder(pc,d1.w),d0	; get what would normally be offset adder
	bne.s	ShrPlF			; and branch to use offset if nonzero
	moveq	#1,d2			; otherwise load offset for big player swimming
ShrPlF:
	lea	PlayerGfxTblOffsets(pc),a1
	move.b	(a1,d2.w),d0		; get offset to graphics table based on offset loaded
	rts

; ---------------------------------------------------------------------------
; Port: forced rolls (CPZ tubes, CNZ pinball...). SMB1 has no roll, so Mario
; tumbles in his jump pose, a quarter turn per step, forwards. Step timing is
; SAnim_Roll's: ($400 - |inertia|) >> 8 frames.
; ---------------------------------------------------------------------------
MAnim_ForcedRoll:
	subq.b	#1,anim_frame_duration(a0)
	bpl.s	.draw
	mvabs.w	inertia(a0),d2
	neg.w	d2
	addi.w	#$400,d2
	bpl.s	+
	moveq	#0,d2
+	lsr.w	#8,d2
	move.b	d2,anim_frame_duration(a0)
	addq.b	#1,anim_frame(a0)
.draw:
	moveq	#0,d1
	move.b	anim_frame(a0),d1
	btst	#status.player.x_flip,status(a0)
	bne.s	+
	neg.b	d1			; facing right: turn clockwise
+	andi.w	#3,d1
	moveq	#MF_Jump,d0
	tst.b	(PlayerSize).w
	beq.s	MAnim_Orient
	moveq	#MF_SmallJump,d0
	bra.s	MAnim_Orient

; ---------------------------------------------------------------------------
; Port: floor angle -> quarter turn (counter-clockwise on screen), d1.w = 0-3.
; S2 angles: 0 floor, $C0 right wall, $80 ceiling, $40 left wall. Each quarter
; spans 45 degrees either side; positive angles are nudged down by one like
; SAnim_WalkRun so both 45-degree slopes stay upright.
; ---------------------------------------------------------------------------
MAnim_AngleQuadrant:
	move.b	angle(a0),d1
	bmi.s	+
	beq.s	+
	subq.b	#1,d1
+	neg.b	d1
	addi.b	#$1F,d1
	lsr.b	#6,d1
	andi.w	#3,d1
	rts

; ---------------------------------------------------------------------------
; Port: draw upright frame d0 turned by d1 (0-3) quarter turns CCW.
; Only 0 and 90 degrees exist as art; 180/270 are those flipped both ways,
; and facing left is a mirror image:
;   facing right: 0 up       90 rot       180 up+HV   270 rot+HV
;   facing left:  0 up+H     90 rot+V     180 up+V    270 rot+H
; Frames with no rotated art use the nearest upright orientation.
; ---------------------------------------------------------------------------
MAnim_Orient:
	andi.w	#$FF,d0
	btst	#0,d1
	beq.s	.upright
	moveq	#0,d2
	cmpi.w	#MarioRot90Xlat_End-MarioRot90Xlat,d0	; frames past the table (swim kicks,
	bhs.s	+					; throw composites) have no rotated art
	move.b	MarioRot90Xlat(pc,d0.w),d2
+	tst.b	d2
	bne.s	.rot
	andi.w	#2,d1			; no rotated art: 90 -> 0, 270 -> 180
	bra.s	.upright
.rot:
	move.b	d2,d0
.upright:
	move.b	d0,mapping_frame(a0)
	btst	#status.player.x_flip,status(a0)
	beq.s	+
	addq.w	#4,d1
+	andi.b	#~(1<<render_flags.x_flip|1<<render_flags.y_flip),render_flags(a0)
	move.b	MarioOrientFlips(pc,d1.w),d2
	or.b	d2,render_flags(a0)
	rts

MarioOrientFlips:
	dc.b	0, 0, 3, 3	; facing right: q0..q3
	dc.b	1, 2, 2, 1	; facing left
	; (bit 0 = x_flip, bit 1 = y_flip)

; Upright mapping frame (blank + PlayerGraphicsTable rows) -> 90-degree frame, 0 = none.
MarioRot90Xlat:
	dc.b	0				; blank
	dc.b	MarioFrame_Big_Walk1_Rot90, MarioFrame_Big_Walk2_Rot90, MarioFrame_Big_Walk3_Rot90
	dc.b	MarioFrame_Big_Skid_Rot90, MarioFrame_Big_Jump_Rot90
	dc.b	0, 0, 0, 0, 0			; swim 1-3, climb 1-2
	dc.b	MarioFrame_Big_Crouch_Rot90, 0	; crouch, fire
	dc.b	MarioFrame_Small_Walk1_Rot90, MarioFrame_Small_Walk2_Rot90, MarioFrame_Small_Walk3_Rot90
	dc.b	MarioFrame_Small_Skid_Rot90, MarioFrame_Small_Jump_Rot90
	dc.b	0, 0, 0, 0, 0, 0		; swim 1-3, climb 1-2, killed
	dc.b	MarioFrame_Small_Stand_Rot90, 0, MarioFrame_Big_Stand_Rot90	; small stand, grow mid, big stand
MarioRot90Xlat_End:
	if MarioRot90Xlat_End-MarioRot90Xlat<>MarioFrame_GfxBase+26
		fatal "MarioRot90Xlat must cover the blank frame and every PlayerGraphicsTable row."
	endif
	even

; ---------------------------------------------------------------------------
; Convert a big-Mario frame to its small-Mario equivalent when small (scripts).
; Idempotent: small frames map to themselves.
Mario_TranslateFrame:
	tst.b	(PlayerSize).w		; 0 = big
	beq.s	.done
	moveq	#0,d0
	move.b	mapping_frame(a0),d0
	move.b	MarioSmallFrameXlat(pc,d0.w),mapping_frame(a0)
.done:
	rts

; Big -> small frame translation, indexed by mapping frame.
MarioSmallFrameXlat:
	dc.b	MarioFrame_Blank
	; big rows $00-$48 (walk..climb) -> the same row in the small table
	dc.b	MF_SmallBase+0, MF_SmallBase+1, MF_SmallBase+2, MF_SmallBase+3, MF_SmallBase+4
	dc.b	MF_SmallBase+5, MF_SmallBase+6, MF_SmallBase+7, MF_SmallBase+8, MF_SmallBase+9
	dc.b	MF_SmallStand		; crouch: small Mario can't crouch (SMB1 only sets CrouchingFlag when big)
	dc.b	MF_SmallBase+0		; fire throw: only fiery (big) Mario throws
	; small rows $60-$B0, small stand, grow mid: unchanged
	dc.b	MF_SmallBase+0, MF_SmallBase+1, MF_SmallBase+2, MF_SmallBase+3, MF_SmallBase+4
	dc.b	MF_SmallBase+5, MF_SmallBase+6, MF_SmallBase+7, MF_SmallBase+8, MF_SmallBase+9
	dc.b	MF_SmallBase+$A, MF_SmallStand, MF_GrowMid
	dc.b	MF_SmallStand		; big standing
	; tall small frames: unchanged
MarioXlat_Tall := MarioFrame_TallSmallBase+$0C
	rept 12
	dc.b	MarioXlat_Tall
MarioXlat_Tall := MarioXlat_Tall+1
	endm
	; swim kick: big swim 1/2/3 -> small swim 1/2 kick, small swim 3 (already has its kick tile)
	dc.b	MarioFrame_Small_Swim1_Kick, MarioFrame_Small_Swim2_Kick, MF_SmallBase+7
	dc.b	MarioFrame_Small_Swim1_Kick, MarioFrame_Small_Swim2_Kick
	; rotations: big -> small
	dc.b	MarioFrame_Small_Walk1_Rot90, MarioFrame_Small_Walk2_Rot90
	dc.b	MarioFrame_Small_Walk3_Rot90, MarioFrame_Small_Stand_Rot90
	dc.b	MarioFrame_Small_Walk1_Rot90, MarioFrame_Small_Walk2_Rot90
	dc.b	MarioFrame_Small_Walk3_Rot90, MarioFrame_Small_Stand_Rot90
	dc.b	MarioFrame_Small_Skid_Rot90, MarioFrame_Small_Jump_Rot90	; big skid, jump
	dc.b	MarioFrame_Small_Stand_Rot90					; big crouch
	dc.b	MarioFrame_Small_Skid_Rot90, MarioFrame_Small_Jump_Rot90	; small skid, jump
	; fireball-throw composites (only fiery = big Mario throws): small walk 1
	rept 9
	dc.b	MF_SmallBase+0
	endm
MarioSmallFrameXlat_End:
	if MarioSmallFrameXlat_End-MarioSmallFrameXlat<>MarioFrame_Count
		fatal "MarioSmallFrameXlat has \{MarioSmallFrameXlat_End-MarioSmallFrameXlat} entries; expected \{MarioFrame_Count}."
	endif
	even

; ---------------------------------------------------------------------------
; Animation scripts - Mario (one per AniIDSonAni_* ID, in the same order)
; Format is S2's: duration, frames..., then $FF (loop) / $FE n / $FD anim.
; A first byte of $FF means "Mario's own action": SMB1's ProcessPlayerAction
; picks the frame (MAnim_SMB). Mario's movement code sets Walk, Stop (skid,
; so Obj08 makes skid dust) and Duck; S2 sets Roll for forced rolls.
; ---------------------------------------------------------------------------
MarioAniData:		offsetTable
	offsetTableEntry.w MarAni_SMB		;  0 Walk
	offsetTableEntry.w MarAni_SMB		;  1 Run
	offsetTableEntry.w MarAni_SMB		;  2 Roll (Mario's jump; forced rolls)
	offsetTableEntry.w MarAni_SMB		;  3 Roll2
	offsetTableEntry.w MarAni_SMB		;  4 Push (SMB1 Mario just walks into walls)
	offsetTableEntry.w MarAni_SMB		;  5 Wait
	offsetTableEntry.w MarAni_Stand		;  6 Balance
	offsetTableEntry.w MarAni_Stand		;  7 LookUp
	offsetTableEntry.w MarAni_SMB		;  8 Duck
	offsetTableEntry.w MarAni_Duck		;  9 Spindash
	offsetTableEntry.w MarAni_Stand		; $A Blink
	offsetTableEntry.w MarAni_Stand		; $B GetUp
	offsetTableEntry.w MarAni_Stand		; $C Balance2
	offsetTableEntry.w MarAni_SMB		; $D Stop (skid)
	offsetTableEntry.w MarAni_Jump		; $E Float
	offsetTableEntry.w MarAni_Jump		; $F Float2
	offsetTableEntry.w MarAni_Jump		; $10 Spring
	offsetTableEntry.w MarAni_Hang		; $11 Hang
	offsetTableEntry.w MarAni_Stand		; $12 Dash2 (unused)
	offsetTableEntry.w MarAni_Stand		; $13 Dash3 (unused)
	offsetTableEntry.w MarAni_Hang2		; $14 Hang2
	offsetTableEntry.w MarAni_Bubble	; $15 Bubble
	offsetTableEntry.w MarAni_Killed	; $16 DeathBW
	offsetTableEntry.w MarAni_Killed	; $17 Drown
	offsetTableEntry.w MarAni_Killed	; $18 Death
	offsetTableEntry.w MarAni_Jump		; $19 Hurt
	offsetTableEntry.w MarAni_Jump		; $1A Hurt2
	offsetTableEntry.w MarAni_Skid		; $1B Slide
	offsetTableEntry.w MarAni_Blank		; $1C Blank
	offsetTableEntry.w MarAni_Stand		; $1D Balance3
	offsetTableEntry.w MarAni_Stand		; $1E Balance4
	offsetTableEntry.w MarAni_Stand		; $1F Transform (Super Sonic)
	offsetTableEntry.w MarAni_Stand		; $20 Lying
	offsetTableEntry.w MarAni_Stand		; $21 LieDown
MarioAniData_End:
	if MOMPASS>1	; AniIDSonAni_* are forward references on the first pass
		if (MarioAniData_End-MarioAniData)/2<>AniIDSonAni_LieDown+1
			fatal "MarioAniData must have one entry per AniIDSonAni_* ID."
		endif
	endif

MarAni_SMB:	dc.b $FF, $FF
MarAni_Stand:	dc.b $7F, MF_Stand, $FF
MarAni_Jump:	dc.b $7F, MF_Jump, $FF
MarAni_Duck:	dc.b $7F, MF_Crouch, $FF
MarAni_Skid:	dc.b $7F, MF_Skid, $FF
MarAni_Hang:	dc.b $7F, MF_Climb1, $FF			; holding on (EHZ/HTZ/WFZ bars)
MarAni_Hang2:	dc.b  $F, MF_Climb1, MF_Climb2, $FF	; hand over hand (MTZ/WFZ moving bars)
MarAni_Bubble:	dc.b  $B, MF_Swim1, MF_Swim1, $FD, AniIDSonAni_Walk
MarAni_Killed:	dc.b $7F, MF_Killed, $FF
MarAni_Blank:	dc.b $7F, MarioFrame_Blank, $FF
	even

; ---------------------------------------------------------------------------
; Star flash (user request), modelled on PalCycle_SuperSonic's normal loop.
; SMB1's star cycles Mario's sprite through its four sprite palettes; here,
; while Mario is invincible, the palette line 0 entries his art uses ($C/$F/$3
; normal, $A/$F/$C fiery - see tools/chr2md.py) cycle through four colour
; sets, normal and underwater palettes alike: fast, then slower for the last
; two seconds (as SMB1 slows the flash when the star is about to run out).
; Mario's own colours are saved at the start and restored at the end.
; Other sprites that use those line 0 entries flash too, as with Super Sonic.
;
; Hook: the first 6 bytes of PalCycle_SuperSonic (size-neutral, see CLAUDE.md
; "Hooking S2") call Mario_PalCycleStar, which does the star flash and then
; performs the replaced "move.b (Super_Sonic_palette).w,d0 / beq.s .return".
; ---------------------------------------------------------------------------
MarioStarEntries:	dc.w	$3*2, $A*2, $C*2, $F*2	; palette line 0 entries (byte offsets)
; colour sets 1-3 for entries $3, $A, $C, $F (set 0 = Mario's saved colours)
MarioStarColours:
	dc.w	$0EEE, $0EEE, $00A0, $06AE	; white and green (Luigi-like)
	dc.w	$000E, $000E, $0EEE, $06AE	; red and white (fire-like)
	dc.w	$0000, $0000, $046A, $00AE	; black, brown and orange (SMB1's enemy palette)

; Luigi: his overalls are LuigiPalSlot (his green) instead of $3. His cap and
; shirt are white ($6), which explosions, monitors etc. use too, so they stay.
; Entries: overalls, fiery shirt/cap, fiery overalls, skin.
LuigiStarEntries:	dc.w	LuigiPalSlot*2, $A*2, $C*2, $F*2
	dc.w	$0C42, $000E, $0C42, $06AE	; blue and red (Mario-like)
	dc.w	$000E, $0EEE, $000E, $06AE	; red and white (fire-like)
	dc.w	$0000, $046A, $0000, $00AE	; black, brown and orange (SMB1's enemy palette)

; a2 = the entries of the character being played; his colour sets follow them
Mario_StarEntries:
	lea	MarioStarEntries(pc),a2
	tst.b	(Mario_IsLuigi).w
	beq.s	+
	lea	LuigiStarEntries(pc),a2
+	rts
	if MarioStarColours-MarioStarEntries<>8
		fatal "Mario_StarFlash expects the colour sets right after the entries."
	endif

Mario_PalCycleStar:
	bsr.s	Mario_StarFlash
	move.b	(Super_Sonic_palette).w,d0	; (replaced instruction) is Sonic super?
	bne.s	+
	addq.l	#4,sp			; (replaced "beq.s .return") no: leave PalCycle_SuperSonic
+	rts				; flags still from the move.b, for its "bmi.w .normal"

Mario_StarFlash:
	cmpi.b	#ObjID_Mario,(MainCharacter+id).w
	bne.w	.done
	btst	#status_secondary.invincible,(MainCharacter+status_secondary).w
	beq.s	.off
	tst.b	(Mario_StarActive).w
	bne.s	.running
	; start: save Mario's colours, normal and underwater
	st.b	(Mario_StarActive).w
	clr.b	(Mario_StarFrame).w
	clr.b	(Mario_StarTimer).w
	bsr.w	Mario_StarEntries
	lea	(Mario_StarSaved).w,a3
	moveq	#4-1,d1
-	move.w	(a2)+,d0
	lea	(Normal_palette).w,a1
	move.w	(a1,d0.w),(a3)
	lea	(Underwater_palette).w,a1
	move.w	(a1,d0.w),8(a3)
	addq.w	#2,a3
	dbf	d1,-
.running:
	subq.b	#1,(Mario_StarTimer).w
	bpl.w	.done
	moveq	#2-1,d0			; next set every 2 frames...
	cmpi.w	#2*60,(MainCharacter+invincibility_time).w
	bhs.s	+
	moveq	#4-1,d0			; ...every 4 for the last two seconds
+	move.b	d0,(Mario_StarTimer).w
	move.b	(Mario_StarFrame).w,d0
	addq.b	#1,d0
	andi.w	#3,d0
	move.b	d0,(Mario_StarFrame).w
	beq.s	.restore		; set 0: Mario's own colours
	subq.w	#1,d0
	lsl.w	#3,d0			; 4 words per set
	bsr.w	Mario_StarEntries
	lea	8(a2),a3		; the colour sets
	adda.w	d0,a3
	movea.l	a3,a4			; same colours underwater
	bra.s	.write
.off:
	tst.b	(Mario_StarActive).w
	beq.s	.done
	clr.b	(Mario_StarActive).w
.restore:
	lea	(Mario_StarSaved).w,a3
	lea	8(a3),a4
.write:					; a3 = 4 normal colours, a4 = 4 underwater colours
	bsr.w	Mario_StarEntries
	moveq	#4-1,d1
-	move.w	(a2)+,d0
	lea	(Normal_palette).w,a1
	move.w	(a3)+,(a1,d0.w)
	lea	(Underwater_palette).w,a1
	move.w	(a4)+,(a1,d0.w)
	dbf	d1,-
.done:
	rts

; ---------------------------------------------------------------------------
; Mario pattern loading subroutine (LoadSonicDynPLC equivalent)
; Uploads the current frame's tiles into Sonic's VRAM slot. The source bank
; is ArtUnc_MarioFire while Mario_ArtBank is set (fiery Mario), else
; ArtUnc_Mario (ArtUnc_Luigi for Luigi); all have the same tile order. A bank
; change forces a reload.
; ---------------------------------------------------------------------------
LoadMarioDynPLC:
	moveq	#0,d0
	move.b	mapping_frame(a0),d0
	move.b	(Mario_ArtBank).w,d1
	cmp.b	(Mario_LastLoadedBank).w,d1
	bne.s	.load
	cmp.b	(Mario_LastLoadedDPLC).w,d0
	beq.s	.done
.load:
	move.b	d1,(Mario_LastLoadedBank).w
	move.b	d0,(Mario_LastLoadedDPLC).w
	move.l	#ArtUnc_Mario,d6
	tst.b	(Mario_IsLuigi).w
	beq.s	+
	move.l	#ArtUnc_Luigi,d6	; Luigi's colours (fire Luigi shares MarioFire, as in SMB1)
+	tst.b	d1
	beq.s	+
	move.l	#ArtUnc_MarioFire,d6
+
	lea	(MapRUnc_Mario).l,a2
	add.w	d0,d0
	adda.w	(a2,d0.w),a2
	move.w	(a2)+,d5
	subq.w	#1,d5
	bmi.s	.done
	move.w	#tiles_to_bytes(ArtTile_ArtUnc_Sonic),d4
.readEntry:
	moveq	#0,d1
	move.w	(a2)+,d1
	move.w	d1,d3
	lsr.w	#8,d3
	andi.w	#$F0,d3
	addi.w	#$10,d3
	andi.w	#$FFF,d1
	lsl.l	#5,d1
	add.l	d6,d1
	move.w	d4,d2
	add.w	d3,d4
	add.w	d3,d4
	jsr	(QueueDMATransfer).l
	dbf	d5,.readEntry
.done:
	rts
