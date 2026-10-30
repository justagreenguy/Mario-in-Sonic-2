; ===========================================================================
; Phase 7 polish: S2 hooks that make the rest of the game treat Mario as Mario
; ---------------------------------------------------------------------------
; Every hook in s2.asm replaces an existing instruction of the same size with
; "jsr (Mario_X).l" (size-neutral, see CLAUDE.md "Hooking S2"); the routine
; does the replaced instruction's job for the other characters.
;   H11 Mario_StarpostRings  - no Special Stage stars from starposts
;   H13 Mario_LoadLifeIcon   - HUD life counter: Mario's face and name
;   H14 Mario_TornadoRadius  - the Tornado (end of SCZ) uses Mario's radius
;   H15 Mario_CameraBias     - the camera follows Mario's feet like Sonic's
;   H16 Mario_SignpostFace   - the signpost shows Mario
;   H16 Mario_ResultsName    - "MARIO GOT THROUGH" ("LUIGI GOT THROUGH")
;   H21 Mario_SetPlayerMode  - every options-menu character is Mario or Luigi
;   H22 Mario_PalPointers    - Luigi's green in palette line 0
; ===========================================================================

; ---------------------------------------------------------------------------
; H11 - Obj79 (starpost)'s "cmpi.w #50,(Ring_count).w / blo.s": in Mario's
; mode the stars are never made, so the Special Stage can't be reached (some
; of its code indexes tables by Player_mode). Returns carry set (blo taken).
; ---------------------------------------------------------------------------
Mario_StarpostRings:
	cmpi.w	#PlayerMode_Mario,(Player_mode).w
	bne.s	+
	move	#1,ccr			; carry: "fewer than 50 rings"
	rts
+	cmpi.w	#50,(Ring_count).w	; (replaced instruction)
	rts

; ---------------------------------------------------------------------------
; H13 - Mario's life counter over Sonic's in VRAM (ObjMario_Init: every life
; and act). The art has the layout of "Sonic lives counter.nem": the face
; (tiles 0-3), then the 4x2 name piece. Hud_Lives draws the lives digits into
; name-piece tiles 9 and 11, so those two are left alone.
; ---------------------------------------------------------------------------
Mario_LoadLifeIcon:
	move.l	#ArtUnc_MarioLife,d1
	tst.b	(Mario_IsLuigi).w
	beq.s	+
	move.l	#ArtUnc_LuigiLife,d1		; Luigi's face and "LUIGI" (same layout)
+	move.l	d1,-(sp)
	move.w	#tiles_to_bytes(ArtTile_ArtNem_life_counter),d2
	move.w	#tiles_to_bytes(9)/2,d3		; face, name top/bottom, name top/bottom, name top
	jsr	(QueueDMATransfer).l
	move.l	(sp)+,d1
	addi.l	#tiles_to_bytes(10),d1
	move.w	#tiles_to_bytes(ArtTile_ArtNem_life_counter+10),d2
	move.w	#tiles_to_bytes(1)/2,d3		; name top, last column
	jmp	(QueueDMATransfer).l

; ---------------------------------------------------------------------------
; H14 - ObjB2 (Tornado) landing on the ship at the end of SCZ:
; "move.b #$13,y_radius(a1)" (a1 = main character) - Sonic's standing radius.
; ---------------------------------------------------------------------------
Mario_TornadoRadius:
	move.b	#$13,y_radius(a1)	; (replaced instruction)
	cmpi.b	#ObjID_Mario,id(a1)
	bne.s	+
	exg	a0,a1
	bsr.w	Mario_SetRadius
	exg	a0,a1
+	rts

; ---------------------------------------------------------------------------
; H20 - WFZ end cutscene (ObjB2, routine 6). The script drives "the player"
; for Sonic: it writes Sonic's standing mapping frame into him every frame,
; and its jump onto the Tornado is a held A (Mario's run button) - and an
; SMB1 jump from a standstill couldn't cover that distance anyway.
; ---------------------------------------------------------------------------
; "move.l #(1<<24)|(0<<16)|(AniIDSonAni_Wait<<8)|AniIDSonAni_Wait,mapping_frame(a1)"
; (ObjB2_Waiting_animation and ObjB2_Landed_on_plane; 8 bytes: jsr + nop).
; Sonic's frame 1 drawn with Mario's tiles was garbage: Mario gets his own
; standing anim. In Landed_on_plane this also ends Mario's hop.
Mario_TornadoWait:
	cmpi.b	#ObjID_Mario,id(a1)
	beq.s	.mario
	move.l	#(1<<24)|(0<<16)|(AniIDSonAni_Wait<<8)|(AniIDSonAni_Wait<<0),mapping_frame(a1)	; (replaced instruction)
	rts
.mario:
	move.b	#AniIDSonAni_Wait,anim(a1)	; Mario's own standing frame (MAnim_SMB)
	tst.b	(Mario_TornadoHop).w
	beq.s	+
	clr.b	(Mario_TornadoHop).w	; on the Tornado: his own movement back on
	clr.b	obj_control(a1)
+	rts

; ObjB2_Jump_to_plane's "clr.w (Ctrl_1_Logical).w / addq.w #1,objoff_2A(a0)"
; (8 bytes: jsr + nop). a0 = the Tornado. Mario hops onto it on an arc: on
; the first frame his own movement is switched off (obj_control) and x_vel /
; y_vel are set so that, moving with S2's ObjectMoveAndFall, he reaches the
; Tornado's top Mario_HopFrames later, wherever the Tornado has moved to by
; then; ObjB2's own SolidObject lands him and the script carries on.
Mario_HopFrames = 40

Mario_TornadoHopArc:
	clr.w	(Ctrl_1_Logical).w	; (replaced instructions)
	addq.w	#1,objoff_2A(a0)
	cmpi.b	#ObjID_Mario,(MainCharacter+id).w
	bne.w	.done
	movem.l	d0-d1/a1,-(sp)
	lea	(MainCharacter).w,a1
	tst.b	(Mario_TornadoHop).w
	bne.s	.flying
	st.b	(Mario_TornadoHop).w
	move.b	#1,obj_control(a1)	; Mario's own movement off for the hop
	bset	#status.player.in_air,status(a1)
	bclr	#status.player.on_object,status(a1)
	move.b	#AniIDSonAni_Spring,anim(a1)	; (Mario's jump frame)
	move.b	#SndID_MarioBigJump,d0
	tst.b	(PlayerSize).w
	beq.s	+
	move.b	#SndID_MarioSmallJump,d0
+	move.b	d0,(Sound_Queue.SFX2).w
	; x_vel = (Tornado x - Mario x) / T + Tornado x_vel
	move.w	x_pos(a0),d0
	sub.w	x_pos(a1),d0
	ext.l	d0
	asl.l	#8,d0
	divs.w	#Mario_HopFrames,d0
	add.w	x_vel(a0),d0
	move.w	d0,x_vel(a1)
	; y_vel = (feet onto the Tornado's top - y) / T + Tornado y_vel - g*(T-1)/2
	; (ObjectMoveAndFall moves, then adds g = $38)
	move.w	y_pos(a0),d0
	subi.w	#9,d0			; Tornado top (SolidObject height $9)
	moveq	#0,d1
	move.b	y_radius(a1),d1
	sub.w	d1,d0			; Mario's y with his feet there
	sub.w	y_pos(a1),d0
	ext.l	d0
	asl.l	#8,d0
	divs.w	#Mario_HopFrames,d0
	add.w	y_vel(a0),d0
	subi.w	#$38*(Mario_HopFrames-1)/2,d0
	move.w	d0,y_vel(a1)
.flying:
	move.l	a0,-(sp)
	movea.l	a1,a0
	jsr	(ObjectMoveAndFall).l
	movea.l	(sp)+,a0
	; safety: far below the Tornado (missed) - his own movement back, so he
	; falls and dies normally instead of falling forever
	move.w	y_pos(a1),d0
	sub.w	y_pos(a0),d0
	cmpi.w	#$80,d0
	blt.s	+
	clr.b	(Mario_TornadoHop).w
	clr.b	obj_control(a1)
+	movem.l	(sp)+,d0-d1/a1
.done:
	rts

; ---------------------------------------------------------------------------
; H15 - ScrollVerti's "btst #rolling / beq.s / subq.w #5,d0": the camera is
; placed relative to Sonic's standing centre, i.e. his feet - $13; a rolling
; Sonic's centre is 5 px lower. For Mario, use his feet - $13 likewise, so the
; camera doesn't jump when his radius changes (size, crouch, forced rolls)
; and frames him as it frames Sonic. In: d0 = y_pos - camera Y, a0 = player.
; ---------------------------------------------------------------------------
Mario_CameraBias:
	cmpi.b	#ObjID_Mario,id(a0)
	bne.s	.sonic
	move.l	d2,-(sp)
	moveq	#0,d2
	move.b	y_radius(a0),d2
	subi.w	#$13,d2
	add.w	d2,d0			; d0 = feet - $13 - camera Y
	move.l	(sp)+,d2
	rts
.sonic:					; (replaced instructions)
	btst	#status.player.rolling,status(a0)
	beq.s	.done
	subq.w	#5,d0
    if fixBugs
	cmpi.b	#ObjID_Tails,id(a0)
	bne.s	.done
	addq.w	#4,d0
    endif
.done:
	rts

; ---------------------------------------------------------------------------
; H16 - Obj0D (signpost)'s "cmpi.w #2,(Player_mode).w" when the player passes
; it: the final face is frame 0 (Sonic's). In Mario's mode Mario's panel is
; DMA'd over that frame's tiles ($22-$39). The signpost is showing Robotnik
; and then spins (frames that don't use those tiles) for 3 seconds first.
; ---------------------------------------------------------------------------
Mario_SignpostFace:
	cmpi.w	#PlayerMode_Mario,(Player_mode).w
	bne.s	++
	move.l	#ArtUnc_MarioSignpost,d1
	tst.b	(Mario_IsLuigi).w
	beq.s	+
	move.l	#ArtUnc_LuigiSignpost,d1	; same size and layout
+	move.w	#tiles_to_bytes(ArtTile_ArtNem_Signpost+$22),d2
	move.w	#(ArtUnc_MarioSignpost_End-ArtUnc_MarioSignpost)/2,d3
	jsr	(QueueDMATransfer).l
+	cmpi.w	#2,(Player_mode).w	; (replaced instruction)
	rts

; ---------------------------------------------------------------------------
; H16 - Obj3A (results screen) name object's "cmpi.w #2,(Player_mode).w":
; in Mario's mode it draws "MARIO GOT" from its own mappings (frame 0, which
; the code that follows picks, since the mode isn't 2). All the letters are
; in the results text art already: M (MILES), A, R (THROUGH), I, O.
; In: a0 = the name object.
; ---------------------------------------------------------------------------
Mario_ResultsName:
	cmpi.w	#PlayerMode_Mario,(Player_mode).w
	bne.s	+
	move.l	#MapUnc_MarioEOLName,mappings(a0)
	tst.b	(Mario_IsLuigi).w
	beq.s	+
	move.l	#MapUnc_LuigiEOLName,mappings(a0)	; "LUIGI GOT": L (MILES), U (THROUGH), I, G
+	cmpi.w	#2,(Player_mode).w	; (replaced instruction)
	rts

; spacing as EOL_Sonic ("SONIC GOT")
MapUnc_LuigiEOLName:	mappingsTable
	mappingsTableEntry.w	.luigi
.luigi:	spriteHeader	; LUIGI GOT
	spritePiece	-$3C, 0, 2, 2, $5C2, 0, 0, 0, 1	; L
	spritePiece	-$2C, 0, 2, 2, $5D8, 0, 0, 0, 1	; U
	spritePiece	-$1C, 0, 1, 2, $5C0, 0, 0, 0, 1	; I
	spritePiece	-$14, 0, 2, 2, $5B8, 0, 0, 0, 1	; G
	spritePiece	 -4, 0, 1, 2, $5C0, 0, 0, 0, 1	; I

	spritePiece	 $10, 0, 2, 2, $5B8, 0, 0, 0, 1	; G
	spritePiece	 $20, 0, 2, 2, $588, 0, 0, 0, 1	; O
	spritePiece	 $2F, 0, 2, 2, $5D4, 0, 0, 0, 1	; T
.luigi_End

; spacing as EOL_Miles ("MILES GOT")
MapUnc_MarioEOLName:	mappingsTable
	mappingsTableEntry.w	.mario
.mario:	spriteHeader	; MARIO GOT
	spritePiece	-$44, 0, 3, 2, $5C6, 0, 0, 0, 1	; M
	spritePiece	-$2C, 0, 2, 2, $5B0, 0, 0, 0, 1	; A
	spritePiece	-$1C, 0, 2, 2, $5CC, 0, 0, 0, 1	; R
	spritePiece	 -$C, 0, 1, 2, $5C0, 0, 0, 0, 1	; I
	spritePiece	  -4, 0, 2, 2, $588, 0, 0, 0, 1	; O

	spritePiece	 $14, 0, 2, 2, $5B8, 0, 0, 0, 1	; G
	spritePiece	 $24, 0, 2, 2, $588, 0, 0, 0, 1	; O
	spritePiece	 $33, 0, 2, 2, $5D4, 0, 0, 0, 1	; T
.mario_End
	even

; ---------------------------------------------------------------------------
; H24 - the opening text: "lea (off_B2B0).l,a1" before "jsr (loc_B272).l" in
; the title screen setup points here instead (same size). Same layout as S2's
; "SONIC / AND / MILES 'TAILS' PROWER / IN", in the same font and charset
; (copied from s2.asm's intro text block). Columns centre each line on the
; 40-cell screen: I and ' are 1 cell wide, a space 1, other letters 2.
; ---------------------------------------------------------------------------
vram_pnt := VRAM_TtlScr_Plane_A_Name_Table
Mario_IntroText: creditsPtrs	MarioIntro_Mario,textLoc($02,$09), MarioIntro_And,textLoc($11,$0C), \
			MarioIntro_Luigi,textLoc($04,$0F), MarioIntro_In,textLoc($12,$12)

 charset '@',"\x3A\1\3\5\7\9\xB\xD\xF\x11\x12\x14\x16\x18\x1A\x1C\x1E\x20\x22\x24\x26\x28\x2A\x2C\x2E\x30\x32"
 charset 'a',"\2\4\6\8\xA\xC\xE\x10\x11\x13\x15\x17\x19\x1B\x1D\x1F\x21\x23\x25\x27\x29\x2B\x2D\x2F\x31\x33"
 charset '!',"\x3C\x38\x3E\x35"
 charset '\H',"\x38\x36\x37"
 charset '9',"\x3D\x3F\x40"
 charset '1',"\x3B\x34"
 charset '.',"\x39"
 charset ' ',0

vram_src := ArtTile_ArtNem_CreditText
MarioIntro_Mario:	creditText   0,"MARIO 'JUMPMAN' MARIO"	; 36 cells
MarioIntro_And:		creditText   0,"AND"
MarioIntro_Luigi:	creditText   0,"LUIGI 'GREEN' MARIO"	; 31 cells
MarioIntro_In:		creditText   0,"IN"

 charset ; revert character set
	even

; ---------------------------------------------------------------------------
; H25 - the ending cutscene. ObjCA loads "the player" as Obj01 (Sonic) with
; obj_control $81 and only moves it around: at a fixed spot with the Float2
; anim during the free fall, then onto the rescue plane with the Wait anim
; (ObjCC, loc_A53A). Mario/Luigi takes Sonic's place as a puppet: ObjMario's
; routine $C shows the killed frame while falling and small standing on the
; plane.
;
; Mario_EndingLoad replaces loc_A2E0's "move.b #ObjID_Sonic,id(a1)" (6 bytes;
; Sonic's and Super Sonic's ending both pass through it). Keeps d0.
; ---------------------------------------------------------------------------
Mario_EndingLoad:
	move.b	#ObjID_Mario,id(a1)
	move.b	#$C,routine(a1)		; => ObjMario_Ending
	rts

; ---------------------------------------------------------------------------
; Mario_EndingStand replaces loc_A53A's "move.l #(1<<24)|...|Wait,mapping_frame(a1)"
; (8 bytes, jsr + nop), run every frame while he stands on the plane, after
; ObjMario_Ending (so the frame must be set here too). ObjCC has just put the
; player $1C above the plane's centre, Sonic's feet $13 below that; Mario's
; small radius is smaller, so he goes lower by the difference.
; In: a1 = the player.
; ---------------------------------------------------------------------------
Mario_EndingStand:
	move.l	#(MF_SmallStand<<24)|(0<<16)|(AniIDSonAni_Wait<<8)|(AniIDSonAni_Wait<<0),mapping_frame(a1)
	addi.w	#$13-Mario_SmallYRadius,y_pos(a1)
	rts

; ---------------------------------------------------------------------------
; ObjMario routine $C: the ending puppet. No physics, input or touches; the
; cutscene sets the position and the anim ID, which picks the frame.
; ---------------------------------------------------------------------------
ObjMario_Ending:
	tst.l	mappings(a0)		; first frame?
	bne.s	+
	cmpi.w	#PlayerOpt_Luigi,(Player_option).w
	seq.b	(Mario_IsLuigi).w
	clr.b	(Mario_ArtBank).w	; normal colours, even if he finished DEZ fiery
	st.b	(Mario_LastLoadedDPLC).w	; force the first DPLC upload
	st.b	(Mario_LastLoadedBank).w
	move.l	#MapUnc_Mario,mappings(a0)
	move.w	#make_art_tile(ArtTile_ArtUnc_Sonic,0,0),art_tile(a0)
	move.b	#2,priority(a0)
	move.b	#$18,width_pixels(a0)
	move.b	#1<<render_flags.level_fg,render_flags(a0)
+
	; the ending palette's line 0 is Sonic's: Luigi's green goes in entry $2
	; (H22 only covers levels). Written to the target every frame, so the
	; cutscene's palette fades (ObjC9) bring it in.
	tst.b	(Mario_IsLuigi).w
	beq.s	+
	move.w	#LuigiGreen,(Target_palette+2*2).w
+
	moveq	#MF_Killed,d0		; free fall
	cmpi.b	#AniIDSonAni_Wait,anim(a0)	; standing on the plane?
	bne.s	+
	moveq	#MF_SmallStand,d0
+	move.b	d0,mapping_frame(a0)
	jsr	(DisplaySprite).l
	bra.w	LoadMarioDynPLC

; ---------------------------------------------------------------------------
; H26 - the ending's art comes from ending_art/*.aseprite (tools/ending_art.py
; generates mario/mario_ending_art.asm). The other H26 hooks only swap a label
; (art, map or mappings pointer); this one loads the photos:
;
; Mario_EndingPhoto replaces ObjCA loc_A256's "movea.l off_A29C(pc,d0.w),a0 /
; lea (Chunk_Table).l,a1" (10 bytes, jsr + 2 nops), which runs while the
; screen is faded out before each photo. S2 loads all four photos' tiles at
; once (363 tiles, the whole VRAM gap); here each photo brings its own tiles
; (NemDec over ArtTile_ArtNem_EndingPics) and palette (into Mario_EndingPal,
; which ObjC9's photo fades read).
; In: d0 = photo * 4. Out: a0 = the photo's Enigma map, a1 = Chunk_Table.
; ---------------------------------------------------------------------------
; The character frames ($07-$0E: on the small Tornado, the jump at the camera)
; come in two sets: while Luigi plays, palette line 0 entry $2 is his green,
; so he has his own (ending_art/luigi/). Player_option is read directly: the
; ending can start from the level select, without a level (Mario's RAM).
; Mario_EndingCharArt replaces EndingSequence_LoadCharacterArt_Sonic's
; "lea (ArtNem_...).l,a0" (6 bytes); Mario_EndingCFMap replaces the
; "move.l #MapUnc_...,mappings(a0)" in ObjCC (loc_A4B6) and ObjCE_Init
; (8 bytes, jsr + nop).
Mario_EndingCharArt:
	lea	(ArtNem_MarioEndingChar).l,a0
	cmpi.w	#PlayerOpt_Luigi,(Player_option).w
	bne.s	+
	lea	(ArtNem_LuigiEndingChar).l,a0
+	rts

Mario_EndingCFMap:
	move.l	#MapUnc_MarioEndingCF,mappings(a0)
	cmpi.w	#PlayerOpt_Luigi,(Player_option).w
	bne.s	+
	move.l	#MapUnc_LuigiEndingCF,mappings(a0)
+	rts

Mario_EndingPhoto:
	movem.l	d1/a2,-(sp)
	move.w	d0,d1
	add.w	d0,d0
	add.w	d1,d0			; * 12: art, map, palette
	lea	(Mario_EndingPhotoTable).l,a2
	adda.w	d0,a2
	move	#$2700,sr		; NemDec writes the VDP directly: no VInt in between
	move.l	#vdpComm(tiles_to_bytes(ArtTile_ArtNem_EndingPics),VRAM,WRITE),(VDP_control_port).l
	movea.l	(a2)+,a0
	jsr	(NemDec).l
	move	#$2300,sr
	movea.l	(a2)+,a0		; the map
	movea.l	(a2)+,a1		; the palette
	lea	(Mario_EndingPal).w,a2
	moveq	#16/2-1,d1
-	move.l	(a1)+,(a2)+
	dbf	d1,-
	lea	(Chunk_Table).l,a1
	movem.l	(sp)+,d1/a2
	rts

; ---------------------------------------------------------------------------
; H27 - the title screen's art comes from title_art/*.aseprite
; (tools/title_art.py generates mario/mario_title_art.asm). The other H27
; hooks swap the logo map, Obj0E's mappings, the logo map's base palette line
; and three palette files; this one loads the art:
;
; Mario_TitleLoadArt replaces the title setup's two "move.l #vdpComm(...),
; (VDP_control_port).l / lea (ArtNem_X).l,a0 / bsr.w NemDec" loads of
; ArtNem_Title and ArtNem_TitleSprites (40 bytes, jsr + 17 nops). The new art
; can be bigger than S2's, so it comes in up to four banks (the title art
; slot, $40C+, $150+ and $4BE+; Mario_TitleArtTable). Interrupts are already
; off there.
; ---------------------------------------------------------------------------
; ---------------------------------------------------------------------------
; H29 - the title menu offers MARIO GAME / LUIGI GAME instead of 1 PLAYER /
; 2 PLAYER VS (OPTIONS is unchanged).
;
; Mario_TitleChoice replaces "move.b (Title_screen_option).w,d0 / bne.s
; TitleScreen_CheckIfChose2P" (6 bytes) after Start is pressed: options 0/1
; pick the character (Player_option, which Mario_SetPlayerMode and
; ObjMario_Init read) and fall into S2's 1-player start (or the level select
; with the cheat and A held); option 2 still goes to the options menu.
; In: d0 = 0.
; ---------------------------------------------------------------------------
Mario_TitleChoice:
	move.b	(Title_screen_option).w,d0
	cmpi.b	#2,d0
	bne.s	+
	addq.w	#4,sp			; OPTIONS: S2's own branch target
	jmp	(TitleScreen_ChoseOptions).l
+	ext.w	d0			; 0 = MARIO GAME, 1 = LUIGI GAME
	move.w	d0,(Player_option).w	; = PlayerOpt_Mario / PlayerOpt_Luigi
	moveq	#0,d0			; continue as a 1-player game
	rts

; Obj0F's mappings for the Mario build (Obj0F_Init points here): S2's frames
; with the two game lines written in the standard font, like S2's OPTIONS
; frame. The highlighted line uses palette line 3, the other line 0. Each
; letter is a 1x1 piece (the font's letters aren't consecutive in VRAM).
 charset 'A','Z',$E	; the standard font's layout (see CopyrightText)
 charset '0','9',0
titleMenuText macro xpos,ypos,pal,str
.x := xpos
	irpc ch,str
	if "ch"<>" "
	; ('ch'|0: forces a number; inside dc.w, AS would emit 'ch' as a string)
	spritePiece	.x, ypos, 1, 1, ArtTile_ArtNem_FontStuff_TtlScr+('ch'|0), 0, 0, pal, 0
	endif
.x := .x+8
	endm
	endm

MapUnc_MarioTitleMenu:	mappingsTable
	mappingsTableEntry.w	.mario
	mappingsTableEntry.w	.luigi
	mappingsTableEntry.w	.options
.mario:	spriteHeader		; MARIO GAME highlighted
	titleMenuText	-$2C, -$C, 3, "MARIO GAME"
	titleMenuText	-$2C, 4, 0, "LUIGI GAME"
	spritePiece	-$44, -$C, 2, 1, $3FA, 0, 0, 3, 0	; the selection arrow (MenuJunk)
.mario_End
.luigi:	spriteHeader		; LUIGI GAME highlighted
	titleMenuText	-$2C, -$C, 0, "MARIO GAME"
	titleMenuText	-$2C, 4, 3, "LUIGI GAME"
	spritePiece	-$44, 4, 2, 1, $3FA, 0, 0, 3, 0
.luigi_End
.options:	spriteHeader	; S2's OPTIONS frame
	spritePiece	-$24, -8, 1, 1, $69C, 0, 0, 3, 0
	spritePiece	-$1C, -8, 1, 1, $69D, 0, 0, 3, 0
	spritePiece	-$14, -8, 1, 1, $6A1, 0, 0, 3, 0
	spritePiece	-$C, -8, 1, 1, $696, 0, 0, 3, 0
	spritePiece	-4, -8, 1, 1, $69C, 0, 0, 3, 0
	spritePiece	4, -8, 1, 1, $69B, 0, 0, 3, 0
	spritePiece	$C, -8, 1, 1, $6A0, 0, 0, 3, 0
	spritePiece	-$44, -8, 2, 1, $3FA, 0, 0, 3, 0
.options_End
	even
 charset	; revert character set

Mario_TitleLoadArt:
	movem.l	d0/a3,-(sp)
	lea	(Mario_TitleArtTable).l,a3	; (NemDec saves a3)
-	move.l	(a3)+,d0		; Nemesis art (0 = end)
	beq.s	+
	movea.l	d0,a0
	move.l	(a3)+,(VDP_control_port).l
	jsr	(NemDec).l
	bra.s	-
+	movem.l	(sp)+,d0/a3
	rts

; ---------------------------------------------------------------------------
; H23 - Obj2F (HTZ smashable rock floors)' "cmpi.b #$E,(MainCharacter+top_solid_bit).w"
; (6 bytes, size-neutral; two places, each followed by "beq.s <break>"). The
; rock breaks when the player stands on it with the Roll anim AND (subtype
; bit 7 or the player is on collision path $E); otherwise it switches him to
; path $C. Sonic rolls onto it along the loop's path; Mario can't roll, and
; his landings ("Roll" while falling, Mario_StompAnimID) were never on path $E
; there, so the floors in HTZ's loops could not be broken: a softlock. For
; Mario a falling stomp breaks it on any path; walking onto it doesn't.
; Returns Z set (beq taken) to break.
; ---------------------------------------------------------------------------
Mario_SmashGroundPath:
	cmpi.b	#ObjID_Mario,(MainCharacter+id).w
	beq.s	+
	cmpi.b	#$E,(MainCharacter+top_solid_bit).w	; (replaced instruction)
+	rts

; ---------------------------------------------------------------------------
; H34 - the level select's "move.b #GameModeID_SpecialStage,(Game_Mode).w"
; (6 bytes, size-neutral). Mario's mode never enters the Special Stage (its
; code indexes by Player_mode and isn't set up for mode 3); the entry is
; CREDITS instead (MapEng_MarioLevSel, the Death Egg's icon) and starts the
; ending sequence.
; The ending normally follows DEZ and relies on what the level left behind:
; its falling scene scrolls plane B with LoadTilesAsYouMove over DEZ's tiles
; (VRAM), blocks, chunks and layout (RAM) and the background already drawn
; at $E000. So DEZ's level data is loaded here first, with Level's own
; routines and in its order, behind a black screen. Then the S2 code after
; the hook sets the lives, score and player mode and returns to the main
; loop, which runs EndingSequence (it sets Current_ZoneAndAct to DEZ itself).
; ---------------------------------------------------------------------------
Mario_LevSelCredits:
	jsr	(Pal_FadeToBlack).l
	move	#$2700,sr		; (as Level: the menu's planes would show
	jsr	(ClearScreen).l		;  through the parts DrawInitialBG doesn't draw)
	move	#$2300,sr
	move.w	#death_egg_zone_act_1,(Current_ZoneAndAct).w
	jsr	(LevelSizeLoad).l
	jsr	(DeformBgLayer).l
	clr.w	(Vscroll_Factor_FG).w
	jsr	(LoadZoneTiles).l	; DEZ's 8x8 tiles (DMA'd during title card V-ints)
	jsr	(loadZoneBlockMaps).l	; blocks, chunks, layout (and DEZ's PLC 2 and palette)
	jsr	(LoadAnimatedBlocks).l
	jsr	(DrawInitialBG).l	; plane B, as Level draws it
	jsr	(ClearPLC).l		; (DEZ's object art isn't needed)
	lea	(Normal_palette).w,a1	; keep the screen black: loadZoneBlockMaps
	moveq	#bytesToLcnt(palette_line_size*4),d0	; loaded DEZ's palette for display
-	clr.l	(a1)+
	dbf	d0,-
	move.b	#GameModeID_EndingSequence,(Game_Mode).w ; => EndingSequence
	rts

; the level select's foreground with CREDITS (generated by tools/levsel_art.py)
	even
MapEng_MarioLevSel:	BINCLUDE "mappings/misc/mario/Level Select.eni"
	even

; ---------------------------------------------------------------------------
; H37 - letting go of a hang bar (user, 2026-10-12). Obj7F (MCZ vine switch),
; Obj80 (MCZ vine pulley, WFZ chain hooks) and ObjD9 (WFZ handles) drop the
; player with "move.w #-$300 / #-$380,y_vel(a1)" (6 bytes, size-neutral): a
; weak hop that Sonic turns into distance with his fast air acceleration.
; SMB1's air control from a standstill is far slower, so Mario couldn't make
; WFZ's jumps from them. For Mario, letting go is his own standing jump
; (InitJS: SMB1's jump speed and forces, the jump sound, variable height
; while B is held). Obj80's sideways push (x_vel +-$200) is kept.
; (Their button checks, and ObjC1's, take only B in the Mario build.)
; In: a1 = the player.
; ---------------------------------------------------------------------------
Mario_HangRelease300:
	cmpi.b	#ObjID_Mario,id(a1)
	beq.s	Mario_HangJump
	move.w	#-$300,y_vel(a1)	; (replaced instruction)
	rts

Mario_HangRelease380:
	cmpi.b	#ObjID_Mario,id(a1)
	beq.s	Mario_HangJump
	move.w	#-$380,y_vel(a1)	; (replaced instruction)
	rts

Mario_HangJump:
	movem.l	d0-d7/a0-a6,-(sp)
	movea.l	a1,a0
	move.b	(SwimmingFlag).w,-(sp)	; (holding C must not make it a swim stroke)
	clr.b	(SwimmingFlag).w
	clr.b	(Player_State).w	; as from the ground
	clr.b	(Player_XSpeedAbsolute).w	; a standing jump (he was hanging still)
	jsr	(InitJS_Swim).l		; (no headroom check: he hangs below the handle)
	move.b	(sp)+,(SwimmingFlag).w
	move.w	(Mario_JumpSpeed).w,d0
	jsr	(Mario_YForS2).l
	move.w	d0,y_vel(a0)
	move.w	d0,(Mario_LastYVel).w	; his own jump, not an S2 launch (Mario_SyncState)
	clr.b	(Mario_LaunchFlag).w
	clr.b	(Mario_JumpStart).w
	bset	#status.player.in_air,status(a0)
	move.b	#1,jumping(a0)
	movem.l	(sp)+,d0-d7/a0-a6
	rts

; ---------------------------------------------------------------------------
; H32 - Obj26_Init's "move.b subtype(a0),anim(a0)" (6 bytes, size-neutral).
; Hard mode (rule 7): SMB1 has no speed shoes, so a speed shoes monitor is a
; 10-ring monitor (icon and contents: Obj2E takes anim). Difficulty_option is
; read directly: the monitors of a new act can be set up before ObjMario_Init.
; ---------------------------------------------------------------------------
Mario_MonitorContents:
	move.b	subtype(a0),anim(a0)	; (replaced instruction) subtype = icon to display
	cmpi.b	#ObjID_Mario,(MainCharacter+id).w
	bne.s	+
	cmpi.w	#Difficulty_Mario,(Difficulty_option).w
	bne.s	+
	cmpi.b	#5,anim(a0)		; speed shoes?
	bne.s	+
	move.b	#4,anim(a0)		; -> super ring
+	rts

; ---------------------------------------------------------------------------
; Character select: Level_SetPlayerMode's and the level select's
; "move.w (Player_option).w,(Player_mode).w" (6 bytes, size-neutral). Sonic
; and Tails can't be chosen in the Mario build: the options menu only offers
; PlayerOpt_Mario and PlayerOpt_Luigi, and both play as ObjMario in
; PlayerMode_Mario (ObjMario_Init reads Player_option for Luigi).
; Demos and 2P mode still force Sonic and Tails (S2's own code).
; ---------------------------------------------------------------------------
Mario_SetPlayerMode:
	move.w	#PlayerMode_Mario,(Player_mode).w
	rts

; ---------------------------------------------------------------------------
; Luigi's palette: the first instruction of PalLoad_Now, PalLoad_ForFade,
; PalLoad_Water_Now and PalLoad_Water_ForFade, "lea (PalPointers).l,a1" (6
; bytes, size-neutral). In: d0 = palette ID, which they then index a1 with.
; While Luigi is playing a level, the player palette line (Pal_BGND) and the
; underwater palettes are loaded from Luigi's copies, which differ only in
; entry LuigiPalSlot: his green (tools/luigi_palette.py freed that entry).
; a1 is offset so that "a1 + ID*8" lands on Luigi's entry.
; ---------------------------------------------------------------------------
Mario_PalPointers:
	lea	(PalPointers).l,a1	; (replaced instruction)
	cmpi.w	#PlayerOpt_Luigi,(Player_option).w
	bne.s	.done
	cmpi.w	#PlayerMode_Mario,(Player_mode).w
	bne.s	.done
	cmpi.b	#GameModeID_Level,(Game_Mode).w
	beq.s	.level
	cmpi.b	#GameModeID_TitleCard|GameModeID_Level,(Game_Mode).w
	bne.s	.done
.level:
	cmpi.b	#PalID_BGND,d0
	bne.s	+
	lea	(LuigiPalPtr_BGND-PalID_BGND*8).l,a1
	rts
+	cmpi.b	#PalID_HPZ_U,d0
	bne.s	+
	lea	(LuigiPalPtr_HPZ_U-PalID_HPZ_U*8).l,a1
	rts
+	cmpi.b	#PalID_CPZ_U,d0
	bne.s	+
	lea	(LuigiPalPtr_CPZ_U-PalID_CPZ_U*8).l,a1
	rts
+	cmpi.b	#PalID_ARZ_U,d0
	bne.s	.done
	lea	(LuigiPalPtr_ARZ_U-PalID_ARZ_U*8).l,a1
.done:
	rts

LuigiPalPtr_BGND:	palptr Pal_Luigi_BGND,  0
LuigiPalPtr_HPZ_U:	palptr Pal_Luigi_HPZ_U, 0
LuigiPalPtr_CPZ_U:	palptr Pal_Luigi_CPZ_U, 0
LuigiPalPtr_ARZ_U:	palptr Pal_Luigi_ARZ_U, 0

; S2's palette files with entry LuigiPalSlot replaced
luigiPalette macro file,green,file2
	BINCLUDE "art/palettes/file",0,LuigiPalSlot*2
	dc.w	green
	BINCLUDE "art/palettes/file",LuigiPalSlot*2+2
    if "file2"<>""
	BINCLUDE "art/palettes/file2"
    endif
	endm

Pal_Luigi_BGND:		luigiPalette SonicAndTails.bin,LuigiGreen,SonicAndTails2.bin
Pal_Luigi_BGND_End:
Pal_Luigi_HPZ_U:	luigiPalette HPZ underwater.bin,LuigiGreen_HPZ_U
Pal_Luigi_HPZ_U_End:
Pal_Luigi_CPZ_U:	luigiPalette CPZ underwater.bin,LuigiGreen_CPZ_U
Pal_Luigi_CPZ_U_End:
Pal_Luigi_ARZ_U:	luigiPalette ARZ underwater.bin,LuigiGreen_ARZ_U
Pal_Luigi_ARZ_U_End:
	if (Pal_Luigi_BGND_End-Pal_Luigi_BGND<>Pal_BGND_End-Pal_BGND)||(Pal_Luigi_CPZ_U_End-Pal_Luigi_CPZ_U<>Pal_CPZ_U_End-Pal_CPZ_U)
		fatal "Luigi's palettes must be the same size as S2's."
	endif
