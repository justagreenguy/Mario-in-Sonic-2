; ===========================================================================
; Mario's fireballs (Phase 6)
; ---------------------------------------------------------------------------
; ProcFireball_Bubble (main.asm:3182) - called from ObjMario_Control: fiery
; Mario throws a fireball when B (Genesis A) is newly pressed. Like SMB1 there
; are two fireball slots, used alternately (FireballCounter & 1); a throw only
; happens when that slot's fireball is gone.
;
; Object D1 - one fireball (subtype = slot), translated from FireballObjCore
; (main.asm:3238), FireballBGCollision (10026), FireballEnemyCollision (8266)
; and DrawFireball / DrawExplosion_Fireball (11584, 11614). S2 provides the
; terrain (ObjCheckFloorDist / wall checks) and the enemy kill (Touch_Enemy_Attack,
; so points, chain bonus and boss hits are S2's).
;
; Speeds are SMB1's, scaled like Mario's own at the S2 boundary
; (Mario_XSpeedToS2 horizontally, Mario_YScale vertically).
; ===========================================================================

; The last 5 tiles of Mario's own 32-tile DPLC slot (Sonic's, $780-$79F):
; his frames use at most MarioFrame_MaxTiles of it. Not Tails' slots
; ($7A0-$7BF): in SCZ/WFZ the Tornado's pilot - Tails, in Mario mode - DPLCs
; his frames there (user report: corrupted fireballs in WFZ).
ArtTile_MarioFireball	= ArtTile_ArtUnc_Sonic+$20-5
	if MarioFrame_MaxTiles>$20-5
		fatal "Mario's largest frame (\{MarioFrame_MaxTiles} tiles) would overwrite the fireball tiles."
	endif

; SST scratch
fb_yspeed	= objoff_30	; word: Fireball_Y_Speed:Y_MoveForce (SMB1 8.8, unscaled)
fb_state	= objoff_32	; byte: Fireball_State (1 = flying, $80+ = exploding)
fb_bounce	= objoff_33	; byte: FireballBouncingFlag

; ---------------------------------------------------------------------------
ProcFireball_Bubble:
	cmpi.b	#MarioStatus_Fiery,(PlayerStatus).w	; check player's status
	blo.s	.done			; if not fiery, branch
	move.b	(A_B_Buttons).w,d0
	andi.b	#B_Button,d0		; check for b button pressed
	beq.s	.done			; branch if not pressed
	and.b	(PreviousA_B_Buttons).w,d0
	bne.s	.done			; if button pressed in previous frame, branch
	moveq	#1,d1
	and.b	(FireballCounter).w,d1	; get LSB and use as offset for buffer
	lea	(Fireball_State).w,a2
	tst.b	(a2,d1.w)		; load fireball state
	bne.s	.done			; if not inactive, branch
	tst.b	(CrouchingFlag).w	; if player crouching, branch
	bne.s	.done
	; (the "player too high or too low" and climbing checks have no S2 equivalent)
	jsr	(AllocateObject).l	; port: the fireball is an S2 object
	bne.s	.done
	move.b	#ObjID_MarioFireball,id(a1)
	move.b	d1,subtype(a1)
	move.b	#2,(a2,d1.w)		; load state
	move.b	#SndID_MarioFireball,(Sound_Queue.SFX2).w	; play fireball sound effect
	move.b	(PlayerAnimTimerSet).w,d0	; copy animation frame timer setting
	move.b	d0,(FireballThrowingTimer).w	; into fireball throwing timer
	subq.b	#1,d0
	move.b	d0,(PlayerAnimTimer).w	; decrement and store in player's animation timer
	addq.b	#1,(FireballCounter).w	; increment fireball counter
.done:
	rts

; ---------------------------------------------------------------------------
; Load the fireball/explosion tiles into Tails' tails VRAM slot (Mario init, debug exit).
Mario_LoadFireballArt:
	move.l	#ArtUnc_MarioFireball,d1
	move.w	#tiles_to_bytes(ArtTile_MarioFireball),d2
	move.w	#(ArtUnc_MarioFireball_End-ArtUnc_MarioFireball)/2,d3
	jmp	(QueueDMATransfer).l

; ===========================================================================
; Object D1 - Mario's fireball
; ===========================================================================
ObjMarioFireball:
	moveq	#0,d0
	move.b	routine(a0),d0
	move.w	ObjMarioFireball_Index(pc,d0.w),d1
	jmp	ObjMarioFireball_Index(pc,d1.w)
; ---------------------------------------------------------------------------
ObjMarioFireball_Index:	offsetTable
	offsetTableEntry.w ObjMarioFireball_Init	; 0
	offsetTableEntry.w ObjMarioFireball_Main	; 2
; ---------------------------------------------------------------------------
; FireballObjCore, state 2: place the fireball at the player and set it moving.
ObjMarioFireball_Init:
	addq.b	#2,routine(a0)
	move.l	#MapUnc_MarioFireball,mappings(a0)
	move.w	#make_art_tile(ArtTile_MarioFireball,0,0),art_tile(a0)
	move.b	#1<<render_flags.level_fg,render_flags(a0)
	move.b	#3,priority(a0)
	move.b	#8,width_pixels(a0)
	move.b	#4,y_radius(a0)
	move.b	#4,x_radius(a0)
	lea	(MainCharacter).w,a1
	; Fireball X = player X + 4 (SMB1 positions are left edges: 8 px fireball
	; on a 16 px player = centred); Y = top of the player's 32 px box
	move.w	x_pos(a1),x_pos(a0)
	moveq	#0,d0
	move.b	y_radius(a1),d0
	add.w	y_pos(a1),d0
	subi.w	#32-1-4,d0		; feet (y + radius + 1) - 32 + 4 (fireball centre)
	move.w	d0,y_pos(a0)
	move.w	#$40*Mario_XSpeedToS2,d0	; FireballXSpdData: $40 (4.4) -> S2 units, scaled as Mario's
	cmpi.b	#1,(PlayerFacingDir).w	; set horizontal speed of fireball accordingly
	beq.s	+
	neg.w	d0
+	move.w	d0,x_vel(a0)
	move.w	#$0400,fb_yspeed(a0)	; set vertical speed of fireball (4.00)
	move.b	#1,fb_state(a0)		; decrement state to 1 to skip this part from now on
	clr.b	fb_bounce(a0)
	bsr.w	MarioFireball_SetYVel
	bra.w	MarioFireball_Draw	; (SMB1 moves it from the next frame on)

; ---------------------------------------------------------------------------
ObjMarioFireball_Main:
	tst.b	fb_state(a0)		; check for d7 = 1
	bmi.w	MarioFireball_Explosion	; if so, branch to draw explosion
; RunFB: ImposeGravity (down force $50, max speed 3) + MoveObjectHorizontally
	jsr	(ObjectMove).l		; move by this frame's speed (SMB1 moves, then adds the force)
	move.w	fb_yspeed(a0),d0
	addi.w	#$50,d0			; add downward movement amount
	cmpi.w	#$0300,d0		; compare to maximum speed (3)
	blt.s	+			; if less than preset value, skip this part
	cmpi.b	#$80,d0			; if less positively than preset maximum, skip this part
	blo.s	+
	move.w	#$0300,d0		; keep vertical speed within maximum value, clear fractional
+	move.w	d0,fb_yspeed(a0)
	bsr.w	MarioFireball_SetYVel
	; offscreen: SMB1 erases fireballs that leave the screen
	tst.b	render_flags(a0)	; was it on screen last frame?
	bpl.w	MarioFireball_Delete
	bsr.s	FireballBGCollision
	tst.b	fb_state(a0)		; exploding now?
	bmi.w	MarioFireball_Draw
	bsr.w	FireballEnemyCollision
	bra.w	MarioFireball_Draw

; y_vel = fb_yspeed scaled for S2 (as Mario_YForS2)
MarioFireball_SetYVel:
	move.w	fb_yspeed(a0),d0
	muls.w	#Mario_YScale,d0
	asr.l	#8,d0
	move.w	d0,y_vel(a0)
	rts

; ---------------------------------------------------------------------------
; FireballBGCollision (main.asm:10026). SMB1 only tests the block under the
; fireball, so a fireball flying into a wall "bounces" inside it and then
; explodes; S2's walls are tested directly.
; ---------------------------------------------------------------------------
FireballBGCollision:
	; port: walls in the direction of travel explode it
	moveq	#4,d3
	tst.w	x_vel(a0)
	bmi.s	.left
	jsr	(ObjCheckRightWallDist).l
	bra.s	.wall
.left:
	moveq	#-4,d3
	jsr	(ObjCheckLeftWallDist).l
.wall:
	tst.w	d1
	bmi.s	InitFireballExplode
	jsr	(ObjCheckFloorDist).l	; do fireball to background collision detection on bottom of it
	tst.w	d1
	bpl.s	ClearBounceFlag		; if nothing underneath fireball, branch
	cmpi.w	#-8,d1			; port: deep inside terrain (steep slope / wall) - explode
	blt.s	InitFireballExplode
	tst.w	fb_yspeed(a0)		; if fireball's vertical speed set to move upwards,
	bmi.s	InitFireballExplode	; branch to set exploding bit in fireball's state
	tst.b	fb_bounce(a0)		; if bouncing flag already set,
	bne.s	InitFireballExplode	; branch to set exploding bit in fireball's state
	move.w	#$FD00,fb_yspeed(a0)	; otherwise set vertical speed to move upwards (give it bounce)
	bsr.s	MarioFireball_SetYVel
	move.b	#1,fb_bounce(a0)	; set bouncing flag
	add.w	d1,y_pos(a0)		; modify vertical coordinate to land it properly
	rts

ClearBounceFlag:
	clr.b	fb_bounce(a0)		; clear bouncing flag by default
	rts

InitFireballExplode:
	move.b	#$80,fb_state(a0)	; set exploding flag in fireball's state
	move.b	#SndID_MarioBump,(Sound_Queue.SFX2).w	; load bump sound
	rts

; ---------------------------------------------------------------------------
; FireballEnemyCollision (main.asm:8266): every other frame, test the
; fireball's 8x8 box against every object with a touch response.
;  - enemy class ($00-$3F): badniks die, bosses take a hit (S2's own code,
;    with Mario as the attacker), and the fireball explodes
;  - harmful class ($80-$BF: spikes, projectiles...): the fireball explodes
;  - items and specials: passed through
; (SMB1's fireproof Buzzy Beetle has no S2 counterpart.)
; ---------------------------------------------------------------------------
FireballEnemyCollision:
	btst	#0,(Level_frame_counter+1).w	; get LSB of frame counter
	bne.s	.exit			; branch to leave if set (do routine every other frame)
	lea	(Dynamic_Object_RAM).w,a1
	moveq	#(Dynamic_Object_RAM_End-Dynamic_Object_RAM)/object_size-1,d6
.loop:
	move.b	collision_flags(a1),d0
	beq.s	.next
	cmpa.l	a0,a1			; (not itself)
	beq.s	.next
	move.b	d0,d4
	andi.b	#$C0,d4
	beq.s	.test			; enemy class
	bpl.s	.next			; $40: items - pass through
	cmpi.b	#$C0,d4
	beq.s	.next			; $C0: specials - pass through
.test:
	; boxes overlap if the centres are closer than the half sizes added up
	; (fireball: 4x4 half size, SMB1's 8x8 bounding box)
	andi.w	#$3F,d0
	add.w	d0,d0
	lea	(Touch_Sizes).l,a2
	adda.w	d0,a2
	move.w	x_pos(a1),d0
	sub.w	x_pos(a0),d0
	bpl.s	+
	neg.w	d0
+	moveq	#4,d1
	add.b	(a2)+,d1		; half width + 4
	cmp.w	d1,d0
	bhs.s	.next
	move.w	y_pos(a1),d0
	sub.w	y_pos(a0),d0
	bpl.s	+
	neg.w	d0
+	moveq	#4,d1
	add.b	(a2),d1			; half height + 4
	cmp.w	d1,d0
	bhs.s	.next
.hit:
	move.b	#$80,fb_state(a0)	; set d7 in fireball state: it explodes
	tst.b	d4
	bpl.s	HandleEnemyFBallCol
	cmpi.b	#ObjID_Bowser,id(a1)	; harmful object: just explode - unless it's
	bne.s	.exit			; Bowser (HandleEnemyFBallCol's HurtBowser)
	bra.w	Bowser_FireballHit
.next:
	lea	next_object(a1),a1
	dbf	d6,.loop
.exit:
	rts

; HandleEnemyFBallCol (main.asm:8332): S2's attack code, as if Mario hit
; the enemy, but Mario's own speed is left untouched.
HandleEnemyFBallCol:
	move.l	a0,-(sp)		; (the fireball; S2's code uses a3 itself)
	lea	(MainCharacter).w,a0
	move.l	x_vel(a0),-(sp)		; x_vel and y_vel
	jsr	(Touch_Enemy_Attack).l	; badnik: points + explosion; boss: one hit
	move.l	(sp)+,x_vel(a0)
	movea.l	(sp)+,a0
	rts

; ---------------------------------------------------------------------------
; DrawFireball: tile $64/$65 alternate every 4 frames, flipped both ways every 8.
MarioFireball_Draw:
	move.b	(Level_frame_counter+1).w,d0
	lsr.b	#2,d0
	andi.b	#3,d0
	addi.b	#MarioFireballFrame_Ball,d0	; (= 0)
	move.b	d0,mapping_frame(a0)
	jmp	(DisplaySprite).l

; DrawExplosion_Fireball: tiles $68/$67/$66, two frames each, then gone.
MarioFireball_Explosion:
	move.b	fb_state(a0),d0		; load fireball state
	addq.b	#1,fb_state(a0)		; increment state for next frame
	lsr.b	#1,d0			; divide by 2
	andi.b	#7,d0			; mask out all but d3-d1
	cmpi.b	#3,d0			; check to see if time to kill fireball
	bhs.s	MarioFireball_Delete	; branch if so, otherwise continue to draw explosion
	addq.b	#MarioFireballFrame_Explosion,d0
	move.b	d0,mapping_frame(a0)
	jmp	(DisplaySprite).l

MarioFireball_Delete:
	moveq	#0,d0
	move.b	subtype(a0),d0
	lea	(Fireball_State).w,a2
	clr.b	(a2,d0.w)		; KillFireBall: clear fireball state to kill it
	jmp	(DeleteObject).l
