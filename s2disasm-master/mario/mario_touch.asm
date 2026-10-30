; ===========================================================================
; Mario touch/hurt handling
; ---------------------------------------------------------------------------
; Mario_TouchEnemy      - hook H8 (Touch_Enemy): SMB1 ChkForPlayerInjury /
;                         EnemyStomped (main.asm 8595-8703)
; Mario_TouchMonitor    - hook H7 (Touch_Monitor): break monitors by hitting
;                         them from below (a "? block") or stomping them
; Mario_MonitorPassable - hook H10 (SolidObject_Monitor): not solid while
;                         Mario is bumping/stomping it, so the touch happens
; Mario_HurtCharacter   - hook H9 (HurtCharacter): ring-based power state
; There is no hook for TouchResponse's duck check (H5/H6): it tests Sonic's
; mapping frame $4D, which Mario doesn't have, and Mario's crouch shrinks his
; radius - and with it his touch box - instead.
; ===========================================================================

; ---------------------------------------------------------------------------
; Mario touches an enemy (collision class $00-$3F). a0 = Mario, a1 = enemy.
; ---------------------------------------------------------------------------
Mario_TouchEnemy:
	btst	#render_flags.multi_sprite,render_flags(a1)	; multi-sprite boss?
	bne.w	Mario_TouchBoss
	tst.b	collision_property(a1)	; boss hit points?
	bne.w	Mario_TouchBoss
	btst	#status_secondary.invincible,status_secondary(a0)
	bne.s	Mario_StarKill
	; HandlePECollisions (main.asm:8563): in a water-type area there is no
	; stomping - touching an enemy injures the player. Here: under S2's water.
	btst	#status.player.underwater,status(a0)
	bne.s	InjurePlayer
; ChkForPlayerInjury (main.asm:8595)
	btst	#status.player.in_air,status(a0)	; port: on the ground SMB1's Y speed is 0
	beq.s	ChkInj
	cmpi.w	#Mario_YScale,y_vel(a0)	; check player's vertical speed (whole part, SMB1 units)
	bge.s	EnemyStomped		; if moving downwards, branch elsewhere
ChkInj:
	; hard mode (rule 5): only stomps while falling. SMB1 skips the
	; "12 pixels above" test for enemies below Bloober (Goombas, Koopas...).
	tst.b	(Mario_HardMode).w
	bne.s	InjurePlayer
	; Player_Y_Position + 12 < Enemy_Y_Position: SMB1 compares the tops of
	; the sprites; here the tops of the two touch boxes
	moveq	#0,d0
	move.b	y_radius(a0),d0
	subq.w	#3,d0			; TouchResponse's half height for Mario
	move.w	y_pos(a0),d1
	sub.w	d0,d1
	addi.w	#$0C,d1			; add 12 pixels to player's vertical position
	moveq	#0,d0
	move.b	collision_flags(a1),d0
	andi.w	#$3F,d0
	add.w	d0,d0
	lea	(Touch_Sizes+1).l,a2
	moveq	#0,d2
	move.b	(a2,d0.w),d2		; enemy's half height
	move.w	y_pos(a1),d0
	sub.w	d2,d0
	cmp.w	d0,d1			; compare modified player's position to enemy's position
	blt.s	EnemyStomped		; branch if this player's position above (less than) enemy's
; InjurePlayer (S2 checks invincibility and the injury timer)
InjurePlayer:
	jmp	(Touch_ChkHurt).l

; EnemyStomped (main.asm:8663): S2's points (chain bonus) and explosion,
; SMB1's bounce
EnemyStomped:
	jsr	(Touch_KillEnemy).l
	move.w	#$FD00,d0		; set player's vertical speed, to give bounce
	bra.w	Mario_SetYSpeed

; Star Mario (ShellOrBlockDefeat): the enemy dies, Mario doesn't bounce.
Mario_StarKill:
	move.w	y_vel(a0),-(sp)
	jsr	(Touch_KillEnemy).l
	move.w	(sp)+,y_vel(a0)
	rts

; Bosses (user decision): any airborne hit hurts them; touching one from the
; ground is a normal hurt check. The hit itself is S2's (Mario bounces back).
; Hard mode (rule 8): only while airborne and falling (y_vel > 0), as a stomp.
Mario_TouchBoss:
	btst	#status.player.in_air,status(a0)
	beq.s	+
	tst.b	(Mario_HardMode).w
	beq.s	.hit
	tst.w	y_vel(a0)
	ble.s	+			; rising (or at the apex): a hurt check
.hit:
	jmp	(Touch_Enemy_Attack).l
+	jmp	(Touch_ChkHurt).l

; ---------------------------------------------------------------------------
; Is Mario hitting monitor a1 from below (d0 = 1) or stomping it (d0 = 2)?
; d0 = 0 otherwise (a side touch, or standing). a0 = Mario. Uses d0-d1.
; From below: rising, centre at least 16 px under the monitor's centre
; (S2 Touch_Monitor's test). Stomp: falling, centre more than 8 px above it.
; ---------------------------------------------------------------------------
Mario_MonitorHit:
	moveq	#0,d0
	btst	#status.player.in_air,status(a0)
	beq.s	.done
	move.w	y_pos(a0),d1
	tst.w	y_vel(a0)
	beq.s	.done
	bmi.s	.up
	addq.w	#8,d1
	cmp.w	y_pos(a1),d1
	bhs.s	.done			; not above it
	moveq	#2,d0
	rts
.up:
	subi.w	#$10,d1
	cmp.w	y_pos(a1),d1
	blo.s	.done			; not under it
	moveq	#1,d0
.done:
	rts

; ---------------------------------------------------------------------------
; Touch_Monitor for Mario (H7). a0 = Mario, a1 = monitor.
; ---------------------------------------------------------------------------
Mario_TouchMonitor:
	bsr.s	Mario_MonitorHit
	beq.s	.done
	move.b	#4,routine(a1)		; break it; Mario gets the item
	move.w	a0,parent(a1)
	cmpi.b	#1,d0
	beq.s	.bump
	move.w	#$FD00,d0		; stomp: same bounce as on an enemy
	bra.w	Mario_SetYSpeed
.bump:
	move.w	#$0100,d0		; head bump (main.asm:9217 NYSpd): set player's
	bra.w	Mario_SetYSpeed		; vertical speed to nullify jump
.done:
	rts

; ---------------------------------------------------------------------------
; SolidObject_Monitor for Mario (H10). a0 = monitor, a1 = Mario.
; Returns Z clear (bne) if the monitor must not be solid this frame.
; ---------------------------------------------------------------------------
Mario_MonitorPassable:
	move.l	d1,-(sp)
	exg	a0,a1
	bsr.s	Mario_MonitorHit
	exg	a0,a1
	move.l	(sp)+,d1
	tst.b	d0
	rts

; ---------------------------------------------------------------------------
; HurtCharacter for Mario (H9). a0 = Mario, a2 = what hurt him.
;  - shield: S2 (the shield absorbs the hit)
;  - rings: scattered (all of them, S2), and a super/fiery Mario shrinks
;  - no rings: small Mario dies; a big one (whose rings were taken some other
;    way, e.g. CNZ slot machine bombs) shrinks, as in SMB1
; Then S2's knockback.
; ---------------------------------------------------------------------------
Mario_HurtCharacter:
	tst.b	(Mario_HardMode).w
	bne.s	Mario_HurtHard
	btst	#status_secondary.shield,status_secondary(a0)
	bne.s	.knockback
	tst.w	(Ring_count).w
	bne.s	.rings
	tst.b	(PlayerStatus).w	; ForceInjury: branch if small
	beq.s	.kill
	bsr.w	ForceInjury
	bra.s	.knockback
.rings:
	jsr	(AllocateObject).l
	bne.s	+
	move.b	#ObjID_LostRings,id(a1)	; load obj
	move.w	x_pos(a0),x_pos(a1)
	move.w	y_pos(a0),y_pos(a1)
	move.w	a0,parent(a1)
+	tst.b	(PlayerStatus).w
	beq.s	.knockback
	bsr.w	ForceInjury
.knockback:
	jmp	(Hurt_Shield).l		; remove shield, knockback, invulnerability, sound
.kill:
	jmp	(KillCharacter).l

; ---------------------------------------------------------------------------
; Hard mode (MARIO MODE) HurtCharacter: SMB1's InjurePlayer/ForceInjury
; (main.asm:8623). a0 = Mario, a2 = what hurt him.
;  - a shield still absorbs the hit first (user decision): it's gone, and
;    Mario gets the injured invincibility, size and rings kept
;  - small: dies, however many rings he has (rule 1)
;  - super/fiery: the rings are simply lost, no scatter (rule 2), and he
;    shrinks (ForceInjury)
; No knockback (rule 3): Mario stays in ObjMario_Control, halted by the injury
; task until the shrink is over (PlayerInjuryBlink). Invincibility: SMB1's
; InjuryTimer, 8 interval ticks (rule 4; Mario_Display blinks him).
; ---------------------------------------------------------------------------
Mario_HurtHard:
	btst	#status_secondary.shield,status_secondary(a0)
	bne.s	.shield
	tst.b	(PlayerStatus).w	; check player's status
	beq.s	.kill			; branch if small
	clr.w	(Ring_count).w		; rings lost (as Obj37 LostRings does, without the rings)
	move.b	#$80,(Update_HUD_rings).w
	clr.b	(Extra_life_flags).w
	bsr.w	ForceInjury		; small, pipedown/injury sound, injury task
	bra.s	.timer
.shield:
	bclr	#status_secondary.shield,status_secondary(a0)	; remove shield
	move.w	#SndID_Hurt,d0		; S2's hurt sound (as Hurt_ChkSpikes)
	cmpi.b	#ObjID_Spikes,id(a2)
	bne.s	+
	move.w	#SndID_HurtBySpikes,d0
+	jsr	(PlaySound).l
.timer:
	move.w	#Mario_InjuryFrames,invulnerable_time(a0)	; set injured invincibility timer
	moveq	#-1,d0
	rts
.kill:
	jmp	(KillCharacter).l
