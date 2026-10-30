; ===========================================================================
; Mario (SMB1) RAM and constants
; ---------------------------------------------------------------------------
; Included from s2.constants.asm in place of the unused $C0-byte block at
; $FFFFE740-$FFFFE7FF (only when marioMode = 1). The block MUST stay exactly
; $C0 bytes so that no other RAM address moves.
;
; Variables keep their SMB1 names; the comment gives the original NES address.
; Values that were split across bytes on the NES (e.g. Y position) are words
; here, since S2 positions/speeds are words. Word variables come first so they
; stay on even addresses.
; ===========================================================================

Mario_RAM:
; --- words ---
Player_X_Speed:			ds.w	1	; NES $57 - signed 4.4 px/frame, widened to a word so S2 speeds fit.
						;   S2 inertia/x_vel = Player_X_Speed << 4.
JumpOrigin_Y:			ds.w	1	; NES $0707/$0708 (JumpOrigin_Y_HighPos/_Position) - full S2 y_pos
Mario_JumpSpeed:		ds.w	1	; port: Y_Speed:Y_MoveForce chosen by ProcJumping (8.8, negative)
Mario_LastXHand:		ds.w	1	; port: last horizontal speed exchanged with S2 (inertia or x_vel);
						;   Mario_SyncXSpeed folds in only what S2 changed since
Mario_LastYVel:			ds.w	1	; port: y_vel as Mario's own code left it; a different value next
						;   frame means S2 launched him (spring, tube, bumper...)
Mario_StarSaved:		ds.w	8	; port: palette line 0 entries $3/$A/$C/$F (Luigi: $2/$A/$C/$F;
						;   normal, then underwater)
						;   saved when the star flash starts, restored when it ends

; --- controller (SMB1 PlayerCtrlRoutine splits SavedJoypadBits into these) ---
SavedJoypadBits:		ds.b	1	; NES $06FC - SMB1 bit layout: A B Sel Start Up Down Left Right
A_B_Buttons:			ds.b	1	; NES $0A - bit 7 = A (jump), bit 6 = B (run/fire)
PreviousA_B_Buttons:		ds.b	1	; NES $0D
Up_Down_Buttons:		ds.b	1	; NES $0B - bit 3 = up, bit 2 = down
Left_Right_Buttons:		ds.b	1	; NES $0C - bit 1 = left, bit 0 = right

; --- player state ---
Player_State:			ds.b	1	; NES $1D - 0 on ground, 1 jumping/swimming, 2 falling, 3 climbing
PlayerSize:			ds.b	1	; NES $0754 - 0 = big, 1 = small (SMB1 polarity kept)
PlayerStatus:			ds.b	1	; NES $0756 - 0 = small, 1 = super, 2 = fiery
PlayerFacingDir:		ds.b	1	; NES $33 - 1 = right, 2 = left
Player_MovingDir:		ds.b	1	; NES $45 - 1 = right, 2 = left
Player_XSpeedAbsolute:		ds.b	1	; NES $0700
CrouchingFlag:			ds.b	1	; NES $0714
SwimmingFlag:			ds.b	1	; NES $0704

; --- horizontal physics ---
Player_X_MoveForce:		ds.b	1	; NES $0705 - extra fraction below Player_X_Speed (friction only;
						;   position uses SprObject_X_MoveForce $0400, i.e. S2's x_sub)
FrictionAdderHigh:		ds.b	1	; NES $0701
FrictionAdderLow:		ds.b	1	; NES $0702
MaximumLeftSpeed:		ds.b	1	; NES $0450 (SMB1 4.4 units)
MaximumRightSpeed:		ds.b	1	; NES $0456 (SMB1 4.4 units)
RunningSpeed:			ds.b	1	; NES $0703

; --- vertical physics ---
VerticalForce:			ds.b	1	; NES $0709
VerticalForceDown:		ds.b	1	; NES $070A
DiffToHaltJump:			ds.b	1	; NES $0706

; --- timers (SMB1 frame timers count down once per frame) ---
; (PlayerAnimTimer, JumpSwimTimer, RunningTimer must stay consecutive: Mario_FrameTimers walks them)
PlayerAnimTimer:		ds.b	1	; NES $0781
JumpSwimTimer:			ds.b	1	; NES $0782
RunningTimer:			ds.b	1	; NES $0783
InjuryTimer:			ds.b	1	; NES $079E (interval timer; ticks every 21 frames on the NES)

; --- animation / graphics ---
PlayerAnimTimerSet:		ds.b	1	; NES $070C
PlayerAnimCtrl:			ds.b	1	; NES $070D
PlayerChangeSizeFlag:		ds.b	1	; NES $070B
PlayerGfxOffset:		ds.b	1	; NES $06D5

; --- power-up / injury sequencing ---
TimerControl:			ds.b	1	; NES $0747 - master timer control: counts down once per frame
						;   and halts the frame timers while nonzero (only Mario's here)
Mario_PowerTask:		ds.b	1	; NES $0E (GameEngineSubroutine), Mario's part only:
						;   0 = control, 9 = PlayerChangeSize, $A = PlayerInjuryBlink, $C = PlayerFireFlower

; --- fireballs ---
FireballCounter:		ds.b	1	; NES $06CE
FireballThrowingTimer:		ds.b	1	; NES $0711
Fireball_State:			ds.b	2	; NES $24/$25 (port: nonzero while that slot's Obj D1 exists;
						;   the object keeps the real state in its own SST)

; --- S2-port-only variables (no SMB1 equivalent) ---
Mario_LaunchFlag:		ds.b	1	; set while airborne from a spring/launcher: use S2 gravity until the apex
Mario_JumpStart:		ds.b	1	; set by ProcJumping (InitJS) this frame
Mario_LastLoadedDPLC:		ds.b	1	; LoadMarioDynPLC: last mapping frame sent to VRAM
Mario_ArtBank:			ds.b	1	; 0 = normal colours, 1 = fire colours (DPLC source)
Mario_LastLoadedBank:		ds.b	1	; bank of the last DPLC upload (forces reload when the bank changes)
Mario_StarActive:		ds.b	1	; star flash running (palette entries saved)
Mario_StarFrame:		ds.b	1	; current colour set, 0-3 (0 = Mario's own colours)
Mario_StarTimer:		ds.b	1	; frames until the next colour set
Mario_InWater:			ds.b	1	; underwater status last frame (water entry detection)
Mario_SwimForces:		ds.b	1	; Mario is actually swimming: in water, or his last InitJS was a
						;   swim stroke, so VerticalForce/Down hold swim values. Cleared
						;   (forces reset) when swimming stops. SwimmingFlag alone only
						;   allows strokes: a C-held jump is a normal jump - forces, air
						;   control (JumpSwimSub) and frames - until its first stroke.
Mario_TornadoHop:		ds.b	1	; WFZ end cutscene: Mario is being carried onto the Tornado
						;   (Mario_TornadoHopArc, mario_polish.asm)
; --- WFZ boss: Bowser (mario/bowser.asm). Cleared with the rest on every life. ---
Bowser_AxeTouched:		ds.b	1	; Mario touched the axe (the fight is won)
Bowser_KillAll:			ds.b	1	; SMB1 KillAllEnemies: flames and hammers delete themselves
Bowser_HammerSlots:		ds.b	9	; SMB1's misc object slots used for hammers (SpawnHammerObj)
Bowser_FightOn:			ds.b	1	; the fight has started (Bowser spawned, axe live)
Mario_IsLuigi:			ds.b	1	; playing Luigi (SMB2J's physics, his colours); set by ObjMario_Init
						;   from Player_option, which persists while this block is cleared
Mario_HardMode:			ds.b	1	; MARIO MODE (hard mode, Phase 9); set by ObjMario_Init from
						;   Difficulty_option
	even
Bowser_Ptr:			ds.w	1	; Bowser's object (0 = none)
Mario_EndingPal:		ds.w	16	; ending: the current photo's palette (Mario_EndingPhoto; ObjC9
						;   subtypes 4/6 read it in place of Pal_AD1E)
PostCredits_Peach:		ds.w	1	; post-credits scene: Peach's object (0 = not out yet)
Mario_RAM_End:

	if Mario_RAM_End-Mario_RAM > $C0
		fatal "Mario RAM is $\{Mario_RAM_End-Mario_RAM} bytes; it must fit in $C0."
	endif
				ds.b	$C0-(Mario_RAM_End-Mario_RAM)	; pad the rest of the block

; ===========================================================================
; Constants
; ===========================================================================

; Collision radii. The generated mappings anchor Mario's feet at y_pos+y_radius
; using these symbols, so they can be retuned without regenerating art.
; Small is $0E, not 8: S2's ground wall sensor sits at y_pos+8 (CalcRoomInFront),
; so a smaller radius would make every floor bump read as a wall. $0E matches
; rolling Sonic, which S2's level geometry already accommodates.
Mario_BigYRadius	= $10
Mario_BigXRadius	= 7
Mario_SmallYRadius	= $0E
Mario_SmallXRadius	= 7

; SMB1 controller bits (constants/constants.asm)
A_Button		= %10000000	; Genesis B or C
B_Button		= %01000000	; Genesis A
Up_Dir			= %00001000
Down_Dir		= %00000100
Left_Dir		= %00000010
Right_Dir		= %00000001

; ---------------------------------------------------------------------------
; Speed tuning (user decision after playtesting: 1:1 SMB1 is too slow for S2's
; level design). SMB1's code still runs in its own units; these factors apply
; only where values are handed to/from S2, so the SMB1 feel is kept, scaled.
; ---------------------------------------------------------------------------
; Horizontal: S2 inertia/x_vel per SMB1 X_Speed unit. 16 = 1:1, 24 = 1.5x.
; (2.5x/40 was too fast; 24 makes the run speed $3C0 - the old walk speed -
; and the walk speed $240.)
Mario_XSpeedToS2	= 24
; inverse, for folding S2 speed changes back: (S2 units * this) >> 5 = Xs:MF units
Mario_S2ToXSpeed	= (256*32 + Mario_XSpeedToS2/2) / Mario_XSpeedToS2
; Vertical: jump speed, gravity and max fall speed multiplier (8.8). $100 = 1:1.
; Scaling speed and gravity together keeps SMB1's arc shape and airtime and
; multiplies the height by the same factor ($140 = 1.25x: halfway between
; SMB1's jump and the $180/1.5x Sonic-height jump).
Mario_YScale		= $140

; Hybrid physics: SMB1's fastest maximum (running, MaxRightXSpdData[0]).
; Speeds above this can only come from S2 (slopes, springs); ImposeFriction
; neither clamps nor accelerates them while the D-pad pushes the same way.
Mario_MaxSMBSpeed	= $28

; Swimming: SMB1 keeps a swimmer from rising past "Player_Y_Position $14"
; (the top of his 32 px box 12 px above the water surface metatile). Here the
; line is the top of his box at S2's water level + this many pixels: deep
; enough that his bob at the surface never takes his centre out of the water
; (S2's underwater test), which would make him splash in and out.
Mario_SwimSurface	= 4

; PlayerStatus values (SMB1)
MarioStatus_Small	= 0
MarioStatus_Super	= 1
MarioStatus_Fiery	= 2

; Mario_PowerTask values (SMB1 GameEngineSubroutine numbers)
MarioTask_ChangeSize	= $09
MarioTask_InjuryBlink	= $0A
MarioTask_FireFlower	= $0C

; Ring thresholds for the ring-based power-ups (port-only rule)
Mario_RingsForSuper	= 10
Mario_RingsForFiery	= 30

; WFZ boss sounds. TEMPORARY stand-ins from S2 until SMB1's Sfx_BowserFlame
; (noise), Sfx_BowserFall, Sfx_Blast and Sfx_BrickShatter are converted.
SndID_BowserFlame	= SndID_Fire
SndID_BowserFall	= SndID_Bonus
SndID_BowserBlast	= SndID_BossExplosion
SndID_BowserShatter	= SndID_Smash

; Player_mode value for Mario and Luigi (S2's own checks treat it like "Sonic alone")
PlayerMode_Mario	= 3

; Player_option values (the options menu): Sonic and Tails can't be chosen in
; the Mario build; Mario_SetPlayerMode turns every option into PlayerMode_Mario.
PlayerOpt_Mario		= 0
PlayerOpt_Luigi		= 1
PlayerOpt_Count		= 2

; Difficulty_option values (options menu box 0; s2.constants.asm, persists
; across lives and acts). The character is picked on the title screen (H29).
Difficulty_Hybrid	= 0	; "HYBRID MODE": the normal (easy) rules
Difficulty_Mario	= 1	; "MARIO MODE": hard mode (Phase 9)
Difficulty_Count	= 2

; Hard mode (MARIO MODE): SMB1's injured invincibility. InjuryTimer = 8 is an
; interval timer, which ticks every 21 frames: 8 * 21 frames, in S2's
; invulnerable_time (it doesn't count down while TimerControl halts timers).
Mario_InjuryFrames	= 8*21
; Hard mode: SMB1's GameEngineSubroutine for a dying player (KillPlayer)
MarioTask_Death		= $0B
