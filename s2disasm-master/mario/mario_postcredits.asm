; ===========================================================================
; Post-credits scene (user design, 2026-10-12)
; ---------------------------------------------------------------------------
; After the credits and the "Sonic 2" logo, Mario (or Luigi) walks through the
; end of Emerald Hill 2 to the prison capsule, jumps onto its button, and Peach
; comes out instead of the animals. He jumps off and walks up to her, and the
; SMB1 ending plays: the victory music starts as he jumps off (user's cue),
; "THANK YOU MARIO!", then the Lost Levels' world 8 message one line at a time. Then the screen fades to black
; and the game resets (the SEGA screen, as after S2's logo).
;
; The scene is a real EHZ2 level run on S2's old credits-demo path
; (Demo_mode_flag negative): Level skips the music fade, the title card, its
; PLCs and the HUD setup there, and the title screen clears the flag again.
;   H35 Mario_PostCreditsStart - EndgameCredits' "move.b #GameModeID_SegaScreen,
;       (Game_Mode).w" (6 bytes): set up EHZ2 and go to the level instead
;   H36 Mario_CapsuleOpen - Obj3E's "move.b #1,anim(a0)" when it opens
;       (6 bytes): Peach comes out; no animals, no end of act
; ObjMario_Init makes Mario big and spawns the director (ObjPostCredits
; subtype 0). The director scripts Mario through Ctrl_1_Logical (controls
; locked), draws the message (its own mapping frames) and fades.
; ===========================================================================

; Mario starts as if from a starpost (Obj79_LoadData puts him there and
; LevelSizeLoad places the camera), past EHZ2's last starpost and its Buzzer.
PostCredits_Starpost	= 5		; EHZ2's last starpost (lit, behind him)
PostCredits_StartX	= $28A0
PostCredits_StartY	= $430		; on the floor, big radius
; The camera stops where S2's boss fight leaves it (the capsule is at the
; screen's centre) and higher than the level's own framing, so the sky above
; the capsule holds the message (camera Y as the boss fight's $390 would put
; the last lines over the capsule).
PostCredits_CameraMaxX	= $2AB0
PostCredits_CameraY	= $380
; The hop onto the capsule's button: an arc of PostCredits_HopFrames under S2
; gravity from PostCredits_HopDX left of the button (as Mario_TornadoHopArc)
PostCredits_HopDX	= $60
PostCredits_HopFrames	= 48
; Peach hops out to the right and lands about PostCredits_PeachDX further on
PostCredits_PeachYVel	= -$500
PostCredits_PeachXVel	= $1EB		; ~$60 px over her ~50 frames in the air
; Mario's hop off the capsule lands him this far left of Peach
PostCredits_StopDX	= $1C
; SMB1's PrintVictoryMessages for world 8: the thanks line at once, then the
; next line once the counters reach 3 (3*64 frames), then a line every 64
; frames. (SMB1 starts the victory music with that second line; here it starts
; at the hop off the capsule, PC_HopOff.) SMB1 then waits for B; here the scene holds
; PostCredits_Hold frames and fades out.
PostCredits_FirstLine	= 3*64
PostCredits_LineFrames	= 64
PostCredits_Hold	= 8*60
PostCredits_FadeSteps	= $16		; as Pal_FadeToBlack / Pal_FadeFromBlack

; VRAM: the message and Peach go over EHZ's badnik, spike and spring art
; (nothing uses it at the end of act 2; the director stops EHZ's PLC 2)
ArtTile_PostCredits	= ArtTile_ArtNem_Buzzer
	if ArtTile_PostCredits+PostCredits_ArtTiles > ArtTile_ArtNem_Checkpoint
		fatal "The post-credits art would overwrite the starpost's tiles."
	endif

; ---------------------------------------------------------------------------
; H35 - the end of EndgameCredits (after the logo, or a button press there).
; Out: Game_Mode = Level (Level_Inactive_flag is already set, so the ending
; loop returns to the main loop).
; ---------------------------------------------------------------------------
Mario_PostCreditsStart:
	jsr	(Pal_FadeToBlack).l
	move	#$2700,sr
	jsr	(ClearScreen).l		; Level doesn't on this path (the logo would show)
	moveq	#PLCID_Capsule,d0	; normally loaded by the EHZ boss
	jsr	(RunPLC_ROM).l
	moveq	#PLCID_Explosion,d0	; (LoadPLC_AnimalExplosion, title card path only)
	jsr	(RunPLC_ROM).l
	move	#$2300,sr
	move.w	#MusID_Stop,d0
	jsr	(PlaySound).l
	move.w	#-1,(Demo_mode_flag).w	; the old credits-demo path through Level
	move.w	#emerald_hill_zone_act_2,(Current_ZoneAndAct).w
	move.w	#PlayerMode_Mario,(Player_mode).w	; (Level_SetPlayerMode is skipped)
	clr.w	(Two_player_mode).w
	clr.w	(Debug_placement_mode).w
	move.b	#PostCredits_Starpost,(Last_star_pole_hit).w
	move.b	#PostCredits_Starpost,(Saved_Last_star_pole_hit).w
	move.w	#PostCredits_StartX,(Saved_x_pos).w
	move.w	#PostCredits_StartY,(Saved_y_pos).w
	move.w	#make_art_tile(ArtTile_ArtUnc_Sonic,0,0),(Saved_art_tile).w
	move.w	#$0C0D,(Saved_Solid_bits).w	; top_solid_bit $C, lrb_solid_bit $D
	clr.w	(Saved_Ring_count).w
	clr.b	(Saved_Extra_life_flags).w
	move.l	#$100,(Saved_Timer).w	; 0:01 (Obj79_LoadData takes a second off)
	move.b	#6,(Saved_Dynamic_Resize_Routine).w	; EHZ2 events: past the boss
	move.w	#PostCredits_CameraY,(Saved_Camera_Max_Y_pos).w
	move.b	#GameModeID_Level,(Game_Mode).w
	rts

; ---------------------------------------------------------------------------
; H36 - Obj3E (capsule body) opening, loc_3F2FC: "move.b #1,anim(a0)" before
; it releases the animals and wakes the object that ends the act. In the
; scene, Peach comes out instead and nothing else happens.
; ---------------------------------------------------------------------------
Mario_CapsuleOpen:
	move.b	#1,anim(a0)		; (replaced instruction)
	tst.w	(Demo_mode_flag).w	; the post-credits scene?
	bpl.s	.done
	addq.w	#4,sp			; return from loc_3F2FC itself
	jsr	(AllocateObject).l
	bne.s	+
	move.b	#ObjID_PostCredits,id(a1)
	move.b	#2,subtype(a1)		; Peach
	move.w	x_pos(a0),x_pos(a1)
	move.w	y_pos(a0),y_pos(a1)
+	addq.b	#2,routine_secondary(a0)	; => return_3F352 (the capsule stays open)
.done:
	rts

; ---------------------------------------------------------------------------
; ObjMario_Init in the scene: Super Mario (0 rings keep him big: power-ups
; only go up) and the director. a0 = Mario.
; ---------------------------------------------------------------------------
Mario_PostCreditsInit:
	clr.b	(PlayerSize).w			; SMB1: 0 = big
	move.b	#MarioStatus_Super,(PlayerStatus).w
	jsr	(AllocateObject).l
	bne.s	+
	move.b	#ObjID_PostCredits,id(a1)	; subtype 0: the director
+	rts

; ===========================================================================
; Object 4E - the post-credits scene: subtype 0 the director (and the
; message's sprites), subtype 2 Peach
; ===========================================================================
pc_timer	= objoff_30	; word: frames in the current phase
pc_button	= objoff_32	; word: the capsule's button object (0 = not found yet)
pc_held		= objoff_34	; byte: the script's buttons last frame
pc_fade		= objoff_35	; byte: fade steps left
pc_lines	= objoff_36	; byte: message lines shown

ObjPostCredits:
	moveq	#0,d0
	move.b	routine(a0),d0
	move.w	ObjPostCredits_Index(pc,d0.w),d1
	jmp	ObjPostCredits_Index(pc,d1.w)
ObjPostCredits_Index:	offsetTable
	offsetTableEntry.w PC_Init	; 0
	offsetTableEntry.w PC_Main	; 2 - the director
	offsetTableEntry.w Peach_Main	; 4 - Peach
; ---------------------------------------------------------------------------
PC_Init:
	tst.b	subtype(a0)
	bne.w	Peach_Init
	addq.b	#2,routine(a0)		; => PC_Main
	move.l	#MapUnc_PostCreditsText,mappings(a0)
	move.w	#make_art_tile(ArtTile_PostCredits,0,1),art_tile(a0)
	clr.b	render_flags(a0)	; screen coordinates
	move.w	#128+320/2,x_pixel(a0)	; the mappings are relative to the screen's centre column
	move.w	#128,y_pixel(a0)
	clr.b	priority(a0)
	; EHZ's PLC 2 (spikes, springs) would overwrite the art below
	jsr	(ClearPLC).l
	move.l	#ArtUnc_PostCredits_Mario,d1
	tst.b	(Mario_IsLuigi).w
	beq.s	+
	move.l	#ArtUnc_PostCredits_Luigi,d1	; "LUIGI" in the message
+	move.w	#tiles_to_bytes(ArtTile_PostCredits),d2
	move.w	#tiles_to_bytes(PostCredits_ArtTiles)/2,d3
	jsr	(QueueDMATransfer).l
	move.w	#PostCredits_CameraMaxX,(Camera_Max_X_pos).w
	move.w	#PostCredits_CameraY,(Camera_Min_Y_pos).w	; (Max: the "starpost" data)
	bsr.w	PC_DrawFG
	; the level's palette is on screen already (PalLoad_Now): fade it in
	lea	(Normal_palette).w,a1
	lea	(Target_palette).w,a2
	moveq	#bytesToLcnt(palette_line_size*4),d0
-	move.l	(a1),(a2)+
	clr.l	(a1)+
	dbf	d0,-
	move.b	#PostCredits_FadeSteps,pc_fade(a0)
	move.w	#MusID_EHZ,d0
	jsr	(PlayMusic).l
	; fall through
; ---------------------------------------------------------------------------
PC_Main:
	clr.b	(Level_started_flag).w	; no HUD or ring sprites (BuildSprites)
	st.b	(Control_Locked).w	; ObjMario reads the script's Ctrl_1_Logical
	tst.b	pc_fade(a0)
	beq.s	+
	subq.b	#1,pc_fade(a0)
	move.l	a0,-(sp)
	jsr	(Pal_FadeFromBlack.UpdateAllColours).l
	movea.l	(sp)+,a0
+	moveq	#0,d6			; the script's held buttons this frame
	lea	(MainCharacter).w,a1
	moveq	#0,d0
	move.b	routine_secondary(a0),d0
	move.w	PC_Phases(pc,d0.w),d0
	jsr	PC_Phases(pc,d0.w)
	move.b	pc_held(a0),d0		; newly pressed = held now and not last frame
	not.b	d0
	and.b	d6,d0
	move.b	d6,pc_held(a0)
	move.b	d6,(Ctrl_1_Held_Logical).w
	move.b	d0,(Ctrl_1_Press_Logical).w
	tst.b	pc_lines(a0)
	beq.s	+
	move.b	pc_lines(a0),d0
	subq.b	#1,d0
	move.b	d0,mapping_frame(a0)
	jmp	(DisplaySprite).l
+	rts
; ---------------------------------------------------------------------------
PC_Phases:	offsetTable
	offsetTableEntry.w PC_Walk	;  0
	offsetTableEntry.w PC_Hop	;  2
	offsetTableEntry.w PC_WaitPeach	;  4
	offsetTableEntry.w PC_HopOff	;  6
	offsetTableEntry.w PC_Stop	;  8
	offsetTableEntry.w PC_Message	; $A
	offsetTableEntry.w PC_Fade	; $C
; ---------------------------------------------------------------------------
; Walk right (SMB1's victory walk: AutoControlPlayer) up to the capsule.
; In: a1 = Mario. Out: d6 = held buttons.
PC_Walk:
	moveq	#button_right_mask,d6
	tst.w	pc_button(a0)
	bne.s	+
	bsr.w	PC_FindButton
	beq.w	.done			; capsule not loaded yet: keep walking
+	movea.w	pc_button(a0),a2
	move.w	x_pos(a2),d0
	subi.w	#PostCredits_HopDX,d0
	cmp.w	x_pos(a1),d0
	bgt.w	.done
	btst	#status.player.in_air,status(a1)
	bne.w	.done
	; jump onto the button: an arc that ends on its top (Obj3E's SolidObject:
	; half height 8); the button's SolidObject lands him
	addq.b	#2,routine_secondary(a0)	; => PC_Hop
	moveq	#0,d6
	move.w	x_pos(a2),d4
	move.w	objoff_30(a2),d5	; the button's resting y
	subq.w	#8,d5			; its top
	bra.w	PC_StartHop
.done:
	rts

; ---------------------------------------------------------------------------
; A scripted jump (as Mario_TornadoHopArc): Mario's own movement off, S2's
; ObjectMoveAndFall carries him on an arc that puts his feet at (d4, d5)
; PostCredits_HopFrames later. In: a1 = Mario.
PC_StartHop:
	clr.w	pc_timer(a0)
	move.b	#1,obj_control(a1)
	bset	#status.player.in_air,status(a1)
	bclr	#status.player.on_object,status(a1)
	bclr	#status.player.x_flip,status(a1)	; facing right
	move.b	#AniIDSonAni_Spring,anim(a1)	; (Mario's jump frame)
	move.b	#SndID_MarioBigJump,d0
	tst.b	(PlayerSize).w
	beq.s	+
	move.b	#SndID_MarioSmallJump,d0
+	move.b	d0,(Sound_Queue.SFX2).w
	sub.w	x_pos(a1),d4		; x_vel = dx / T
	ext.l	d4
	asl.l	#8,d4
	divs.w	#PostCredits_HopFrames,d4
	move.w	d4,x_vel(a1)
	moveq	#0,d1
	move.b	y_radius(a1),d1
	sub.w	d1,d5			; Mario's y with his feet there
	sub.w	y_pos(a1),d5		; y_vel = dy / T - g*(T-1)/2
	ext.l	d5
	asl.l	#8,d5
	divs.w	#PostCredits_HopFrames,d5
	subi.w	#$38*(PostCredits_HopFrames-1)/2,d5
	move.w	d5,y_vel(a1)
	rts

PC_MoveHop:
	addq.w	#1,pc_timer(a0)
	move.l	a0,-(sp)
	movea.l	a1,a0
	jsr	(ObjectMoveAndFall).l
	movea.l	(sp)+,a0
	rts

; ---------------------------------------------------------------------------
; Plane A in its initial state, around the camera. On the normal path the
; title card draws it as it leaves (DrawLevelTitleCard); without one, the
; ground only appeared column by column as the camera scrolled. This is
; DrawInitialBG's loop with the foreground's camera, layout and plane. The
; screen is still black (the fade-in starts after this).
PC_DrawFG:
	movem.l	d0-d7/a0-a6,-(sp)
	lea	(VDP_control_port).l,a5
	lea	(VDP_data_port).l,a6
	lea	(Camera_X_pos).w,a3	; (x, then y at +4, as Camera_BG_X_pos)
	lea	(Level_Layout).w,a4	; foreground
	move.w	#vdpComm(VRAM_Plane_A_Name_Table,VRAM,WRITE)>>16,d2
	moveq	#-block_height,d4
	moveq	#gameplay_plane_height/block_height-1,d6	; height of plane in blocks minus 1
-	movem.l	d4-d6,-(sp)
	moveq	#0,d5
	move.w	d4,d1
	jsr	(CalculateVRAMAddressOfBlockForPlayer1).l
	move.w	d1,d4
	moveq	#0,d5
	moveq	#gameplay_plane_width/block_width-1,d6	; width of plane in blocks minus 1
	move	#$2700,sr
	jsr	(DrawBlockRow_CustomWidth).l
	move	#$2300,sr
	movem.l	(sp)+,d4-d6
	addi.w	#block_height,d4
	dbf	d6,-
	movem.l	(sp)+,d0-d7/a0-a6
	rts

; Find the capsule's button (Obj3E, routine 4). Out: Z clear if found.
PC_FindButton:
	lea	(Dynamic_Object_RAM).w,a2
	moveq	#(Dynamic_Object_RAM_End-Dynamic_Object_RAM)/object_size-1,d0
-	cmpi.b	#ObjID_EggPrison,id(a2)
	bne.s	+
	cmpi.b	#4,routine(a2)
	bne.s	+
	move.w	a2,pc_button(a0)
	rts				; (Z clear: a2's address isn't 0)
+	lea	next_object(a2),a2
	dbf	d0,-
	moveq	#0,d0			; Z set: not found
	rts
; ---------------------------------------------------------------------------
PC_Hop:
	btst	#status.player.in_air,status(a1)
	beq.s	.landed			; the button's SolidObject landed him
	cmpi.w	#PostCredits_HopFrames+16,pc_timer(a0)
	bhs.s	.landed			; (safety: missed it, let him fall normally)
	bra.w	PC_MoveHop
.landed:
	clr.b	obj_control(a1)
	clr.w	x_vel(a1)
	clr.w	inertia(a1)
	addq.b	#2,routine_secondary(a0)	; => PC_WaitPeach
	clr.w	pc_timer(a0)
	rts
; ---------------------------------------------------------------------------
; On the button: the capsule explodes and opens (Obj3E), Peach hops out.
PC_WaitPeach:
	move.w	(PostCredits_Peach).w,d0
	beq.s	.done
	movea.w	d0,a2
	tst.b	routine_secondary(a2)	; landed?
	beq.s	.done
	addq.w	#1,pc_timer(a0)
	cmpi.w	#30,pc_timer(a0)
	blo.s	.done
	addq.b	#2,routine_secondary(a0)	; => PC_HopOff
	clr.w	pc_timer(a0)
.done:
	rts
; ---------------------------------------------------------------------------
; Jump off to the right, landing PostCredits_StopDX left of Peach, on the
; floor she landed on. (A real SMB1 jump keeps his walking speed through the
; air, and he slid past her.) A frame before the arc ends his own movement
; takes over with no horizontal speed, so he lands on the terrain and stays.
PC_HopOff:
	tst.w	pc_timer(a0)
	bne.s	.flying
	tst.b	obj_control(a1)
	bne.s	.flying
	movea.w	(PostCredits_Peach).w,a2
	move.w	x_pos(a2),d4
	subi.w	#PostCredits_StopDX,d4
	move.w	y_pos(a2),d5
	moveq	#0,d0
	move.b	y_radius(a2),d0
	add.w	d0,d5			; the floor under Peach
	move.w	#MusID_MarioVictory,d0	; SMB1's VictoryMusic as he jumps off (user's cue;
	jsr	(PlayMusic).l		;  SMB1 starts it with its second message line)
	bra.w	PC_StartHop
.flying:
	cmpi.w	#PostCredits_HopFrames-1,pc_timer(a0)
	blo.w	PC_MoveHop
	clr.b	obj_control(a1)
	clr.w	x_vel(a1)
	clr.w	inertia(a1)
	addq.b	#2,routine_secondary(a0)	; => PC_Stop
	rts
; ---------------------------------------------------------------------------
PC_Stop:
	btst	#status.player.in_air,status(a1)
	bne.s	.done
	tst.w	inertia(a1)
	bne.s	.done
	addq.b	#2,routine_secondary(a0)	; => PC_Message
	clr.w	pc_timer(a0)
	move.b	#1,pc_lines(a0)		; "THANK YOU MARIO!"
.done:
	rts
; ---------------------------------------------------------------------------
PC_Message:
	addq.w	#1,pc_timer(a0)
	move.w	pc_timer(a0),d0
	subi.w	#PostCredits_FirstLine,d0
	bmi.s	.done
	cmpi.w	#(PostCredits_Lines-2)*PostCredits_LineFrames+PostCredits_Hold,d0
	bhs.s	.fade
	ext.l	d0
	divu.w	#PostCredits_LineFrames,d0
	addq.w	#2,d0
	cmpi.w	#PostCredits_Lines,d0
	bls.s	+
	moveq	#PostCredits_Lines,d0
+	move.b	d0,pc_lines(a0)
.done:
	rts
.fade:
	addq.b	#2,routine_secondary(a0)	; => PC_Fade
	clr.w	pc_timer(a0)
	move.w	#MusID_FadeOut,d0
	jmp	(PlaySound).l
; ---------------------------------------------------------------------------
; Fade to black (a step every 2 frames, as S2's level end), then reset.
PC_Fade:
	addq.w	#1,pc_timer(a0)
	move.w	pc_timer(a0),d0
	btst	#0,d0
	bne.s	.done
	cmpi.w	#2*PostCredits_FadeSteps,d0
	bhi.s	.reset
	move.l	a0,-(sp)
	jsr	(Pal_FadeToBlack.UpdateAllColours).l
	movea.l	(sp)+,a0
.done:
	rts
.reset:
	clr.w	(Demo_mode_flag).w
	clr.b	(Control_Locked).w
	move.b	#GameModeID_SegaScreen,(Game_Mode).w	; Level_MainLoop returns at the end of the frame
	rts

; ===========================================================================
; Peach: hops out of the capsule to the right and stands facing left (as
; SMB1 draws her: EnemyGraphicsTable's orientation, Mario on her left).
; ===========================================================================
Peach_Init:
	move.b	#4,routine(a0)		; => Peach_Main
	move.l	#MapUnc_Peach,mappings(a0)
	move.w	#make_art_tile(ArtTile_PostCredits+PostCredits_TextTiles,0,0),art_tile(a0)
	move.b	#1<<render_flags.level_fg,render_flags(a0)
	move.b	#3,priority(a0)		; in front of the capsule
	move.b	#8,width_pixels(a0)
	move.b	#$C,y_radius(a0)
	move.b	#8,x_radius(a0)
	move.w	#PostCredits_PeachXVel,x_vel(a0)
	move.w	#PostCredits_PeachYVel,y_vel(a0)
	move.w	a0,(PostCredits_Peach).w
Peach_Main:
	tst.b	routine_secondary(a0)
	bne.s	.show
	jsr	(ObjectMoveAndFall).l
	tst.w	y_vel(a0)
	bmi.s	.show
	jsr	(ObjCheckFloorDist).l
	tst.w	d1
	bpl.s	.show
	add.w	d1,y_pos(a0)		; on the ground
	clr.w	x_vel(a0)
	clr.w	y_vel(a0)
	move.b	#2,routine_secondary(a0)
.show:
	jmp	(DisplaySprite).l
