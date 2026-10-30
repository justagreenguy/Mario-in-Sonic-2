# Project: Mario (SMB1) as a playable character in Sonic 2

This file is the plan we agreed on for the project, plus reference notes. Read it before starting any work. When a phase is finished, update **Status** below.

## Status
- [x] Phase 0: Scaffolding (done 2026-10-09)
  - `marioMode` flag in s2.asm options. **Since Phase 2 it defaults to 1**, so `s2built.bin` is the Mario build. Set it to 0 only to run `chkbitperfect`, then set it back.
  - `mario/` holds the stub files. `ObjMario` and `ObjMarioFireball` currently just `jmp (DeleteObject).l`.
  - The RAM block is `mario/mario.constants.asm`, at $FFFFE740 (uses $26 of $C0, padded, with a `fatal` if it overflows).
  - Obj_Index $D0/$D1 are filled; `ObjID_Mario`/`ObjID_MarioFireball` are in s2.constants.asm.
  - Verified:
    - flag=0 is bit-perfect with REV01.
    - The flag=1 ROM differs only in the checksum, the two Obj_Index pointers, and the stubs in the tail padding.
    - The flag=1 ROM is still 1 MB: only ~$650 bytes of padding remain before $100000, so the ROM grows to 2 MB in Phase 1/2.
  - Toggle the flag by editing the `marioMode = ` line in s2.asm (the file is pure ASCII).
  - BlastEm is contained in "C:\Users\derps\Documents\so-retro\blastem-win64-1.0.0\blastem.exe"
- [x] Phase 1: Art converter (done 2026-10-09)
  - `tools/chr2md.py` generates the art, mappings, DPLCs and frame IDs; `tools/verify_mario_art.py` checks them in the built ROM. See "Art pipeline" below.
  - Verified:
    - flag=1 builds, giving a 2 MB ROM with the art at $100000.
    - All 52 Mario frames and 7 fireball/explosion frames decode from the ROM identically to SMB1's composition.
    - flag=0 is still bit-perfect.
  - The last flag=1 build is saved as `s2disasm-master/s2built_mario.bin` (gitignored) for boot tests. Mario isn't reachable until Phase 2.
  - Boot-tested in Fusion: both `s2built.bin` (flag=0) and `s2built_mario.bin` (flag=1, 2 MB) run SEGA screen → title screen → the 2P Emerald Hill attract demo at 60 fps. The 2 MB ROM reaches the title slightly later because the boot checksum covers twice as much ROM.
  - **How to boot-test without the user:**
    1. `Start-Process` `C:\Users\derps\Documents\Fusion\Fusion.exe` with the ROM path as the argument.
    2. Wait, then capture the window with `System.Drawing` `CopyFromScreen` on `GetWindowRect(MainWindowHandle)`.
    3. Read the PNG.
    4. `Stop-Process` Fusion.
- [x] Phase 2: Basic Mario object (done 2026-10-09)
  - **ObjMario** (`mario/mario.asm`) clones Obj01, with the routine layout identical to `Obj01_Index`.
    - Control dispatches on in_air/rolling through a table of long pointers: `Mario_MdNormal`, `Obj01_MdAir`, `Obj01_MdRoll`, `Obj01_MdJump`.
    - `Mario_MdNormal` (`mario_glue.asm`) is Obj01_MdNormal minus spindash, roll and the idle-blink checks, calling Sonic's routines with `jsr (X).l`. Sonic physics are a placeholder until Phase 3.
    - Hurt, Dead, Gone and Respawning reuse `Sonic_HurtStop`, `CheckGameOver`, `Sonic_LevelBound` and `Sonic_RecordPos`.
  - **Radius handling:**
    - `Mario_FixJumpRadius` undoes `Sonic_Jump`'s $E radius and +5 y shift on take-off. Mario keeps his own radius in the air, and his jump still counts as "rolling" (it kills badniks) until Phase 3/5.
    - `Mario_ResetOnFloor_Part2` (the H4 target) restores the radius from `PlayerSize` and corrects y by the real radius change.
  - **Animation** (`mario_anim.asm`):
    - `MarioAniData` has one script per `AniIDSonAni_*` ID (an assembly-time check enforces this). A first byte of $FF triggers `MAnim_Walk`; every other script runs through S2's own `SAnim_Do`.
    - Scripts use big-Mario frames. `Mario_TranslateFrame` maps them to small frames through `MarioSmallFrameXlat` (52 entries, also checked at assembly time).
  - **DPLC:** `LoadMarioDynPLC` is LoadSonicDynPLC with an art-bank select (`Mario_ArtBank`). A bank change forces a reload.
  - **Hooks done:**
    - H1: Obj_Index.
    - H2: `InitPlayers_MarioAlone`, for `Player_mode` 3.
    - H3: options choices 3→4, "MARIO ALONE" in both text tables.
    - H4: `cmpi.b #ObjID_Mario` → `jmp Mario_ResetOnFloor_Part2`.
    - H12: `Debug_ExitDebugMode` → `Mario_DebugExit`.
  - Mario currently starts small (`PlayerSize` = 1) and never changes size until Phase 5.
  - **Verified** with `python -I tools/test_phase2.py` (24/24 checks, screenshots in `tools/out/phase2/`):
    - Real menus: options → MARIO ALONE → Emerald Hill 1.
    - ObjD0 with MapUnc_Mario and radius $0E.
    - Walks, jumps and lands with the radius kept.
    - Debug in/out restores mappings and radius.
    - Time-over death shows the killed frame, then Gone, then a life lost and a respawn.
    - flag=0 still bit-perfect.
  - Known/expected for now:
    - Sonic's physics and jump.
    - Upright sprite on loops (Phase 4).
    - HUD life icon still Sonic (H13, Phase 7).
    - Special Stage still reachable through starposts until H11 (Phase 7). Some Special Stage code indexes by `Player_mode` and could misbehave with mode 3, so avoid taking starposts with 50+ rings while testing.
- **Testing tools (use BlastEm, not Fusion, for automation):**
  - `tools/blastem_gdb.py` launches BlastEm with `-D` (GDB stub on port 1234) and controls it frame by frame:
    - **Input:** a breakpoint at `ReadJoypads+12` (between the pad reads, hit once per frame) overwrites `Ctrl_1` held/press with the scripted buttons.
    - **API:** `frames(n, "right|c")`, `tap()`, `r8/r16/r32/read/write`, `sym()` (from `s2.lst`), `screenshot()`.
    - Speed is about 40 frames per second.
  - BlastEm's built-in text debugger (`-d`) does NOT read piped stdin on Windows, so use the GDB stub.
  - `tools/fusion_test.ps1` (keyboard injection into Fusion) works, but timing is unreliable for menus. Prefer BlastEm.
  - `blastem_gdb.boot_to_level(emu, option)` does the whole menu sequence.
  - **Warp to another zone:** write `Current_ZoneAndAct` (e.g. $0D00 = CPZ1), set `Level_Inactive_flag` = 1, then wait for the restart.
  - **Live play sessions with logging:** `python -I tools/watch_session.py <minutes> [option] [zoneact]`.
    - The user plays; the script logs every 8 frames to `tools/out/session.csv`.
    - It samples on a breakpoint at `ChangeRingFrame`'s ring-counter reset, because BlastEm's stub ignores Ctrl-C while running.
    - Summarise with `tools/analyze_session.py` (or `--dump A B` for raw samples).
  - **Teleport tests:** set `invulnerable_time` (SST $30) so badniks don't kill 0-ring Mario.
  - Menu timing: after `Game_Mode` = 4 (title), wait about 420 frames before menu input. On the options screen, wait about 60 frames, then step Right until `Player_option` reads the target value. Fixed counts dropped the first press once and started Tails alone.
- [x] Phase 3: SMB1 physics (done 2026-10-09)
  - **`mario/mario_physics.asm`** holds line-by-line translations of:
    - `PlayerCtrlRoutine`'s input split.
    - The crouch flag.
    - `PlayerPhysicsSub`, `CheckForJumping`, `ProcJumping`, `X_Physics`.
    - `OnGroundStateSub`, `GetPlayerAnimSpeed`, `ImposeFriction`.
    - `FallingSub`, `JumpSwimSub`, `LRAir`.
    - `MovePlayerVertically`/`ImposeGravity`.
    - The frame timers.

    The tables are verbatim. Not ported: climbing, whirlpools, jumpsprings, pipe intros. Swimming is wired in but `SwimmingFlag` stays 0 until Phase 7.
  - **Units:**
    - `Player_X_Speed` is a word (SMB1 4.4); S2 `inertia`/`x_vel` = `Player_X_Speed << 4`.
    - `Player_X_MoveForce` ($0705) is SMB1's separate friction fraction. It is NOT shared with the position subpixel (that's $0400 = S2 `x_sub`), so the plan's "decoupling" note was wrong. No compromise was needed.
    - `y_vel` = `Y_Speed:Y_MoveForce` exactly. The gravity cap is SMB1's: `Y_Speed` ≥ 4 AND `Y_MoveForce` ≥ $80 → $04:00.
  - **Hybrid glue** (`mario_glue.asm`):
    - **Speed sync:** `Mario_SyncXSpeed` folds any S2 change to `inertia` (ground) or `x_vel` (air) back into `Player_X_Speed:Player_X_MoveForce` at full precision.
    - **Soft cap:** above $28 (the run max), `ImposeFriction` neither accelerates nor clamps in the direction of motion. Below that it's pure SMB1, including the hard drop to walk speed when run is released.
    - **Ground (`Mario_MdNormal`):** SMB1 code, then `Sonic_SlopeResist` → `Obj01_Traction` → `AnglePos` → `SlopeRepel`.
    - **Jump:** applied perpendicular to the floor like `Sonic_Jump`, with `Sonic_Jump`'s headroom check. The air routine runs in the same frame, as SMB1 does.
    - **`Player_State` from S2:** on the ground → 0. In the air, if `y_vel` ≠ `Mario_LastYVel` (S2 moved him: spring/tube/bumper) or he left the ground without jumping → 2. If that's upward → `Mario_LaunchFlag` → S2 gravity $38 until the apex. This was fixed after the user's CPZ test: tube exits and springs had been using SMB1 gravity.
    - **Facing:** S2 changes to `x_flip` (springs) are adopted.
    - **`move_lock`** masks the D-pad only on the ground. Air control ignores it, as S2 does. This bug stranded Mario on the first steep EHZ slope.
    - **`Mario_FixSonicRadius`** turns any S2 reset to Sonic's $13 radius into Mario's, keeping the feet in place.
  - **Placeholders until Phase 4/5:**
    - Mario's jump sets anim `AniIDSonAni_Roll`, so S2 still treats it as an attack: it kills badniks and breaks monitors.
    - Ground anim is Walk/Duck/Stop (skid).
  - **Verified:**
    - `python -I tools/test_phase3.py` compares the ROM frame by frame with `tools/smb1_ref.py`, a byte-level Python transliteration of the 6502 routines. 473 flat-ground frames, **0 mismatches**, covering walk/run/release/skid/run-skid/held jump/short hop/walk-jump/run-jump/crouch/down+direction.
    - The user played EHZ1 and CPZ1 (`tools/watch_session.py`):
      - Both EHZ loops completed, with speed up to 2656 through the soft cap.
      - Vertical wall runs and wall jumps work.
      - Horizontal springs, spin tube transport, and a forced roll ending in a clean landing.
    - Sonic at the same $280 top speed takes the same routes.
    - A simulated mid-jump spring gives $38 per frame while rising, then SMB1's $70.
    - flag=0 is still bit-perfect.
  - Not yet checked: the CNZ pinball, bottomless pits (HTZ/MCZ), and every boss.
  - **Speed tuning (user decision, 2026-10-09):** 1:1 SMB1 was too slow for S2's levels.
    - **Constants** in `mario.constants.asm`:
      - `Mario_XSpeedToS2` = 40: S2 speed per SMB1 X unit, i.e. **2.5× horizontal**. Walk $3C0, run $640.
      - `Mario_YScale` = $180: **1.5× jump speed and gravity together**. SMB1's arc shape and airtime are kept, height ×1.5: a held standing jump is 99 px (about Sonic's), a tap is 33 px. The fall cap is 6 px/frame.
    - **Where they apply:** SMB1 code still runs in its own units. The scaling is only at the exchange points: `Mario_XSpeedForS2` and `Mario_YForS2`, the inverse inside `Mario_SyncXSpeed`, and the max-fall check done in SMB1 units.
    - **To retune,** change those two constants. `test_phase3.py` reads them from the listing.
    - **Drift bug found and fixed at the same time:** S2 values that aren't a multiple of the scale (e.g. `x_vel` after a slope jump) were being re-added every frame, slowly accelerating Mario in the air. `Mario_LastXHand` now records the last speed exchanged with S2, so each S2 change is folded in exactly once.
    - Re-verified: 385 flat frames with 0 mismatches against the 6502 model; Phase 2 tests pass; flag=0 still bit-perfect.
    - **Retuned after the user's playtest:** 2.5× felt too fast.
      - Now `Mario_XSpeedToS2` = **24** (1.5×: run $3C0, which was the old walk speed; walk $240).
      - `Mario_YScale` = **$140** (1.25×, halfway between SMB1 and the $180 Sonic-height jump).
      - At the user's request this was built but not tested by me; the user is playtesting it.
- [x] Phase 4: Animation (done 2026-10-09)
  - **`Mario_Animate`** (`mario_anim.asm`): a `MarioAniData` script whose first byte is $FF (`MarAni_SMB`: Walk, Run, Roll, Roll2, Push, Wait, Duck, Stop) runs the SMB1 path. Every other anim ID is set by S2 objects and plays an S2 script through `SAnim_Do` + `Mario_TranslateFrame`. If a script ends in `$FD`, the new anim is drawn in the same frame.
  - **SMB1 path:** line-by-line translations of:
    - `PlayerGfxHandler` (swim-kick frames every 8 of 16 frames, ready for Phase 7).
    - `ProcessPlayerAction`, `AnimationControl`, `GetGfxOffsetAdder`.
    - `HandleChangeSize`, ready for Phase 5. While `PlayerChangeSizeFlag` is set, small rows use the "tall" frames (big radius).

    `PlayerGfxOffset/8 + MarioFrame_GfxBase` gives the mapping frame. Climbing (state 3) is not ported. The fireball-throw override (`PlayerGfxProcessing`) is deferred to Phase 6.
  - **Floor rotation (`MAnim_AngleQuadrant`/`MAnim_Orient`):** the angle is quantised into 4 quarters at ±45°, using `SAnim_WalkRun`'s nudge on positive angles.
    - Facing right: q0 upright, q1 rot90, q2 upright+HV, q3 rot90+HV.
    - Facing left: q0 +H, q1 rot90+V, q2 +V, q3 rot90+H.
    - Frames without rotated art fall back to the nearest upright orientation.
    - The same rotation applies in the air, so leaving a wall eases back upright as `Sonic_JumpAngle` returns the angle to 0.
  - **Forced rolls** (`status.rolling` is only ever set by S2): the jump frame tumbles a quarter turn per step, using `SAnim_Roll`'s timing.
  - **`Mario_GroundAnim`** still sets the S2 anim ID (Walk/Duck/Stop) for other objects. At skid start it plays `SndID_Skidding` and starts Obj08 skid dust, the way `Sonic_Move` does (SMB1 has neither). While `move_lock` is set, it keeps an object's non-Mario anim, e.g. Bubble (Obj24 sets `move_lock`=$23).
  - **Scripts:** Hang = climb 1; Hang2 = climb 1/2; Bubble = swim 1, then Walk; Spring/Hurt = jump; Death/Drown = killed.
  - **Verified:**
    - `python -I tools/test_phase4.py`: 2971 frames match a Python model of `ProcessPlayerAction`/`AnimationControl` plus the orientation rules (frame, flips, `PlayerAnimCtrl`, `PlayerAnimTimer`), with 0 failures.
    - Walk cadence 4.7 frames per step, run 2.5.
    - Skid frame with dust objects.
    - Crouch only when big.
    - EHZ1 loop: all 4 quarters on the ground.
    - Forced roll shows 4 orientations.
    - Hang, Hang2 and Bubble scripts.
    - Close-ups of the loop: `tools/out/phase4/loop_sheet.png`.
    - Art verifies (57 frames). Phase 2 tests pass. flag=0 is bit-perfect.
  - The test gives Mario a one-off `inertia` $C00 boost before the loop at x≈$1680. At the 1.5× tuning, a run from standing ($3C0) can't make that loop. That's a physics/tuning question for the user.
  - `test_phase3.py` now reports 1 mismatch ("land f5", S2 speed −$F5 is not a multiple of 24). It is unchanged with Phase 4's `Mario_GroundAnim` reverted, so it predates Phase 4. It comes from the 1.5× retune: on a landing frame S2 sets `inertia` from `x_vel` and Mario hasn't written the speed back yet. The test assumes "on ground" means Mario wrote it. Look at this when the tuning is settled.
- [x] Phase 5: Combat and power-ups (done 2026-10-09)
  - **Power state** (`mario_glue.asm`, "Power state" section): translations of SMB1's `TimerControl` sequencing.
    - `TimerControl` counts $FF down and halts Mario's frame timers while nonzero (`Mario_TimerTick`).
    - `Mario_PowerTask` = GameEngineSubroutine: $09 `PlayerChangeSize` (size flips at $F8, done at $C4), $0C `PlayerFireFlower` (done at $C0), $0A `PlayerInjuryBlink` (shrink at $F0, done at $C8).
    - Plus `InitChangeSize`, `DonePlayerTask`, `GetPlayerColors` (fiery → `Mario_ArtBank` 1), `SetPRout`, `ForceInjury`.
  - **Rings → power** (`Mario_UpdatePower`, in place of `HandlePowerUpCollision`): 10 rings → super (grow), 30 → fiery (the two colour banks alternate every 4 frames; SMB1 cycles 4 palettes). Small → fiery takes two steps. **Upgrades only:** losing rings without a hit (e.g. CNZ slot bombs) never shrinks him. Sound: `SndID_Shield` stands in for the power-up sound.
  - **Halting:** during grow and fire, only Mario halts (`ObjMario_Frozen`): no movement, no input, no `TouchResponse`. S2 keeps running. Injury never halts him; S2's knockback runs, and the shrink plays during it (the change-size frames take priority over any anim while alive).
  - **Radius** (`Mario_SetRadius`/`Mario_ApplyRadius`): big while `PlayerChangeSizeFlag` is set; small when small or crouching. Changes keep the feet in place, towards whichever side Mario stands on (floor/wall/ceiling quarter). Forced rolls keep S2's radius.
  - **Hooks:**
    - H7 `Touch_Monitor` → `Mario_TouchMonitor`: rising with his centre ≥ 16 px under the monitor's breaks it (head bump: SMB1 `NYSpd`, Y speed 1); falling with his centre > 8 px above it is a stomp ($FD bounce). Side touches do nothing.
    - H8 `Touch_Enemy` → `Mario_TouchEnemy`:
      - Bosses (multi-sprite or `collision_property` ≠ 0) are hit by any airborne touch (user rule, revised 2026-10-09: the falling-only rule moved to hard mode, Phase 9), through S2's own code (new label `Touch_Enemy_Attack`, which emits no bytes). Any other boss touch is a hurt check.
      - Star Mario kills with no bounce.
      - Badniks: `ChkForPlayerInjury`. Stomp if airborne with SMB1 Y speed ≥ 1 (`y_vel` ≥ `Mario_YScale`), or if his touch-box top + 12 is above the enemy's touch-box top. Otherwise `Touch_ChkHurt`.
      - A stomp is S2's `Touch_KillEnemy` (points, chain, explosion), then the SMB1 $FD bounce (`Mario_SetYSpeed` also updates `Mario_LastYVel`, so it isn't taken for an S2 launch).
      - Collision class $80+ (spikes, projectiles) never reaches `Touch_Enemy`, so it always hurts.
    - H9 `HurtCharacter` → `Mario_HurtCharacter`: a shield absorbs the hit (S2). With rings, S2's ring scatter plus `ForceInjury` if powered. With 0 rings: small → `KillCharacter`; big → `ForceInjury` (SMB1 rule; only reachable after the slot machine takes his rings). Then `Hurt_Shield` (knockback).
    - H10 `SolidObject_Monitor_Sonic` → `Mario_MonitorPassable`: not solid while bumping or stomping, so the touch happens.
    - H5/H6 aren't needed: S2's duck check tests mapping frame $4D, which Mario doesn't have, and his crouch radius shrinks his touch box anyway.
  - **Speed shoes** (end of `X_Physics`): double `MaximumLeft/RightSpeed` and the friction adder. The soft cap (`Mario_SoftCap`) doubles with them.
  - **Breakables / stomp anim ID (fix 2026-10-09, user report: CPZ tube caps wouldn't break):**
    - **Which objects:** Obj32 (CPZ caps, HTZ rocks), Obj2F (HTZ smashable ground) and Obj3D (OOZ striped blocks). Each frame they copy `MainCharacter+anim` into their own RAM, then break if the player who just landed on them had Roll. The audit grep (`#AniIDSonAni_Roll,anim(a1)`) missed them because they compare `objoff_32`/`breakableblock_mainchar_anim`.
    - **Fix:** `Mario_StompAnimID`, at the end of `Mario_MdAir`. While airborne and showing one of his own anims, Mario's anim ID reads Roll when falling and Walk when rising. Landing on a breakable while falling is a stomp that breaks it, like monitors and badniks; from below or the side it stays solid. Frames don't change (both IDs go through `MAnim_SMB`). Anims set by S2 objects and forced rolls are left alone.
    - **Other Roll readers:** monitors and `Touch_Enemy` are hooked; the `SolidObject` push reset is cosmetic; CNZ's Crawl now treats a falling Mario as attacking (a stomp).
    - **Notes:** Obj2F also needs subtype bit 7 or the player on collision layer $E, even for Sonic. Obj3D's invisible launcher grabs the player after breaking (`obj_control` $81), as for Sonic.
    - **Verified:** `tools/test_breakables.py` (6/6; objects spawned in EHZ1, logic only). Phase 5 re-run: 0 failures (two of its checks needed test-geometry fixes).
  - **Jump anim ID:** Mario's jump sets Walk (Roll while falling, see above), not Sonic's Roll.
  - **Star flash (user request, 2026-10-09; hook H18):** modelled on `PalCycle_SuperSonic`'s normal loop. While Mario is invincible, the palette line 0 entries his art uses ($3, $A, $C, $F) cycle through four colour sets in both the normal and underwater palettes:
    - his own colours (saved when the flash starts);
    - white and green (Luigi-like);
    - red and white (fire-like);
    - black, brown and orange (SMB1's enemy palette).

    The set changes every 2 frames, slowing to every 4 for the last 2 seconds, like SMB1's star. The saved colours are restored when invincibility ends, including when it's cleared by death.
    - Not 1:1 with SMB1, which cycles the sprite's palette-select bits instead. User: "flash colours across his sprite".
    - Side effect, as with Super Sonic: other sprites using those line 0 entries flash too.
    - The colour sets are `MarioStarColours`.
    - Verified by `tools/test_star.py` (4/4: four sets, 2-frame then 4-frame steps, exact restore). Screenshots in `tools/out/star/`. Audit: the remaining `AniIDSonAni_Roll` checks are monitors (hooked), `Touch_Enemy` (hooked), a cosmetic push reset in `SolidObject`, and CNZ's Crawl badnik (collision $D7 special: Mario can't destroy it; check in Phase 8). Breakables check the `rolling` *status*, which Mario's jump never set.
  - **Verified:**
    - `python -I tools/test_phase5.py`, 34/34 checks:
      - Grow and fire timing; halted; feet kept; flicker; crouch radius.
      - Monitor: side solid; broken from below (Obj2E item to Mario); stomped.
      - Stomps on Buzzer, Coconuts and Masher. A hurt-class object hurts.
      - Boss rule (revised): rising and falling both hit; a ground touch hurts. Re-run and passing (2026-10-09).
      - Fiery side hit: rings lost; shrink at $F0; small radius after.
      - Star kill; shield; shoes ($50); big with 0 rings shrinks; small with 0 rings dies.
    - Badniks for the test are spawned into free slots; EHZ1's only Buzzer patrols away.
    - Phase 2 and 4 tests pass; Phase 4's model now knows `TimerControl` halts the timers, because its EHZ run grows Mario at 10 real rings.
    - Phase 3 still shows only its pre-existing mismatch.
    - Art verifies; flag=0 is bit-perfect.
  - SMB1 quirk kept: the last frame of growing shows small standing Mario, because `HandleChangeSize` wraps to entry 0 of `ChangeSizeOffsetAdder`.
  - Test harness fix: `blastem_gdb.read` treated a byte of $EF (reply "EF") as a GDB error.
  - **SMB1 sounds converted (user request):** `python -I tools/nes_sfx2smps.py` generates `sound/sfx/D2 - Mario Power Up.asm` (`Sfx_PowerUpGrab`) and `D1 - Mario Power Down.asm` (`Sfx_PipeDown`, SMB1's injury sound) from SMB1's own data. Never hand-edit them.
    - **Pitch:** PSG3 tone. The PSG divider equals NES timer + 1 (exact), written as an S2 PSG-table note + `smpsDetune`.
    - **Volume:** full PSG volume (attenuation 0, `PSG_FULL_VOLUME` in the converter; user decision 2026-10-09). The NES-relative mapping (attenuation 1 and 2) was too quiet next to S2's FM sounds. The 25% duty of the power-up can't be represented; the power-down is 50% on both.
    - **Power-down:** the NES hardware sweep (shift 1, one step per frame, muted when the target exceeds $7FF) is simulated. There are 6 register writes; shared sweep subroutines are called with one nesting level, which overlaps only the gosub/loop-counter bytes.
    - **Sound bank:** it's full, so with `marioMode`, Mario's sounds replace unused S2 sounds: $D1 power-down, $D2 power-up, (Phase 6) $B8 fireball, $C7 bump, (Phase 7) $A9 swim/stomp. The power-down and power-up are described here; the others in their phases. $B1 and $A5 were freed in Phase 7 (aliased to `Sound40`). Remaining candidate, if more are needed: $C3 ("enter giant ring", only partly unused, check first). Their `zSFXPriority` entries are raised from 60h to 70h. The unused `BA` sound's pointer aliases `Sound40` to free its bytes. All of this is in `if marioMode` (s2.asm `SoundIndex`/includes, s2.constants.asm, s2.sounddriver.asm).
    - **Where they play:** power-up in `Mario_UpdatePower`; power-down in `ForceInjury`. Both write `Sound_Queue.SFX2` directly: the third queue slot, which no S2 code writes but `sndDriverInput` and the driver both handle. **Bug fixed 2026-10-09:** the power-down used `PlaySound2` (`SFX1`), and `LostRings` overwrote it with the ring-spill sound in the same frame, so it never played.
    - **Testing:** `tools/test_powerup_sound.py` checks the power-up's 27 dividers and 54 frames in the driver's track RAM. `tools/test_power_pause.py` checks both sounds frame by frame against an interpretation of the generated SMPS files (14/14 pass). **Not yet re-verified:** flag=0 bit-perfect (sound-driver and s2.asm changes) and a Phase 5 re-run.
  - **World pause (H17, user request, 2026-10-09):** while `Mario_PowerTask` runs (grow 58 frames, fire flower ~62, injury 54), everything but Mario pauses, as SMB1's `TimerControl` does:
    - Objects outside the reserved slots only display (S2's own dead-player split, `RunObjectsWhenPlayerIsDead`), so Mario's shield, dust and stars keep running.
    - `OscillateNumDo` and `ChangeRingFrame` are skipped: platform positions, ring animation and the lost-ring lifetime.
    - The level clock stops.
    - **Mario holds still during the injury task too (fix 2026-10-10, user report):** he used to keep moving with S2's knockback while the world was paused, so paused solid objects (the SCZ Tornado, any platform) stopped holding him up and he fell off the Tornado and died. `ObjMario_Hurt` now shows him frozen while `Mario_PowerTask` runs (`ObjMario_HurtFrozen`), as SMB1 does (its injury routine replaces player control). The knockback runs after the ~54 frames. The earlier note that SMB1 Mario keeps moving during the injury was wrong. `test_power_pause.py` checks it (y may shift by the radius difference as he shrinks); Phase 5 still passes.
    - Code: `Mario_WorldPaused` (also checks that the main character *is* Mario: in other modes the Mario RAM block is never initialised), `Mario_RunObjects`, `Mario_OscillateAndRings`, `Mario_HudTimePaused`, in `mario_glue.asm`.
    - Scattered rings freeze mid-burst for the injury pause, then carry on.
    - Verified by `tools/test_power_pause.py`.

## Hooking S2 (assembler trap, found 2026-10-09)
**Inserting bytes into S2's main code can make AS fail**, depending on how many bytes are added: +2 and +8 built, +4/+6/+16 didn't. The errors are a wall of "symbol undefined" in pass 2, in macro-generated labels: `begin_animpat`'s `APM_*_Blocks`, `plrlistheader`'s `__LABEL__Plc`, `mvabs`'s `.skip`, starting around `AnimPatMaps`. The cause looks like address-dependent macro expansion (`jmpTosInternal` expands `align 4` only when `*&2`), which shifts AS's two-pass bookkeeping for macro labels.
- **Rule:** prefer **size-neutral hooks**. Replace an existing instruction or sequence of the same size with `jsr (Mario_X).l` (6 bytes), padding with `nop` if needed, inside `if marioMode / else / endif`. To skip a branch target, the Mario routine can pop its return address and `jmp` to the target (see `Mario_HudTimePaused`).
- Earlier hooks (H1–H12) insert bytes and happen to build. If a future hook triggers this, convert it, or another one, to the size-neutral form rather than chasing the byte count.
- [x] Phase 6: Fireballs (done 2026-10-09)
  - **Code** (`mario/mario_fireball.asm`), line-by-line translations of:
    - **`ProcFireball_Bubble`**, called from `ObjMario_Control` before the A/B buttons are saved; skipped under `obj_control`. Fiery Mario, a new B (Genesis A) press, not crouching. Two slots used alternately (`FireballCounter & 1`); a throw happens only if that slot is free (`Fireball_State`). It sets `FireballThrowingTimer`/`PlayerAnimTimer` as SMB1 does.
    - **Obj D1:**
      - `FireballObjCore`: starts at Mario's centre x, y = top of his 32 px box + 4. Then `ImposeGravity` ($50 force, cap 3 once the fraction reaches $80, so 4.00 → 4.50 → 3.00).
      - `FireballBGCollision`: bounce with Y speed $FD; a second floor hit, or a floor hit while rising, explodes it.
      - `FireballEnemyCollision`: every other frame, 8×8 box against `Touch_Sizes`.
      - `DrawFireball` (4 frames), `DrawExplosion_Fireball` (3 frames × 2).
  - **Port details:**
    - Speeds are SMB1's scaled like Mario's: x ±`$40*Mario_XSpeedToS2` = ±$600, y through `Mario_YScale`.
    - S2 walls are tested directly (`ObjCheckRight/LeftWallDist`), and so is ground more than 8 px deep (steep slopes). SMB1 only tests below the fireball.
    - Deleted when off screen (`render_flags` bit 7), which frees its slot.
    - Enemy class $00 → S2's `Touch_Enemy_Attack` with Mario as the attacker (badnik kill with points and chain; boss: one hit), with Mario's `x_vel`/`y_vel` saved and restored. Harmful class $80 → the fireball just explodes. Items and specials are passed through.
    - Art: `ArtUnc_MarioFireball` DMA'd at Mario init and debug exit, to Tails' tails VRAM slot ($7B0) since Phase 7 (was $7A0, which the SCZ/WFZ Tornado pilot uses).
  - **Throw pose** (Phase 4's deferred `PlayerGfxProcessing` part, in `MAnim_SMB`): while `PlayerAnimTimer` < `FireballThrowingTimer`, the $58 throw frame is shown. When moving, SMB1 redraws only rows 1–3, so `chr2md.py` generates 9 composites (`MarioFrame_Throw_*`: walk 1–3, skid, jump, swim 1–3, stand; frames $39–$41, 66 frames total; `verify_mario_art.py` checks them). Throw frames have no rotation (upright or upside down only). `MAnim_Orient` now ignores the rotation table for frames past it.
  - **Sounds** (`tools/nes_sfx2smps.py`, new general square/sweep simulation `simulate_square`: negate, sweep period, mid-sound register writes):
    - `Sfx_Fireball` (5 frames, rising) → `SndID_MarioFireball` in unused slot B8.
    - `Sfx_Bump` (10 frames, sweep changes at counter 6) → `SndID_MarioBump` in unused slot C7, played on wall and ground explosions.
    - Both use `Sound_Queue.SFX2`, full PSG volume, `if marioMode`.
  - **Verified:**
    - `python -I tools/test_phase6.py`, 15/15:
      - Throwing: small can't throw; the throw makes ±$600; the throw pose shows; at most 2; no throw while crouching.
      - Motion: SMB1 bounce and fall cap; off-screen deletion frees the slot.
      - Hits: badnik kill with Mario's speed untouched; boss hit and explode; harmful object explodes it; the wall at EHZ1's underground pillar (x≈$77C) explodes it; the explosion finishes.
    - Phase 4 (2932 frames, 0 failures) and Phase 5 (0 failures) still pass; art verifies (66 frames). Screenshots in `tools/out/phase6/`.
  - **Not yet:** real bosses (Phase 8). (Fireballs in water and flag=0 bit-perfect were verified in Phase 7.)
- [x] Phase 7: Water and polish (done 2026-10-10)
  - **Swimming** (`mario_physics.asm`):
    - `Mario_SwimCheck` sets `SwimmingFlag` each frame (before `Mario_ReadJoypad`): under S2's water (status underwater bit), or (user rule, below) airborne with C held. SMB1 sets it for a whole water-type area.
    - The SMB1 swim code is translated: `ProcJumping`'s mid-air strokes, swim data index 5, `Sfx_EnemyStomp` on each stroke, the "Player_Y_Position < $14" surface rules (Y speed zeroed at a stroke, `VerticalForce` $18 in `JumpSwimSub`), `X_Physics`' water ground speed ($10, also when running), swim frames and swim-kick feet.
    - **Surface line** (`Mario_NearSurface`): the top of Mario's 32 px box (feet + 1 − 32) above S2's `Water_Level_1` + `Mario_SwimSurface` (4). Deep enough that the bob at the surface never takes his centre out of the water. If it did, S2's `Sonic_Water` would splash him in and out.
    - **Forces:** entering water sets the swim falling force ($0A), as if his last stroke had been in water. When swimming stops (out of the water, or C released in the air), swim forces go back to $70 (`Mario_SwimForces`).
    - **`Mario_SwimForces`** means "actually swimming": in water, or the last `InitJS` was a stroke. It gates `JumpSwimSub`'s swim branch and the swim frames. `SwimmingFlag` alone only allows strokes, so a C-held jump is a normal jump (forces, air control, frames) until its first stroke. Phase 4's test caught C jumps drawing swim frames before this.
    - **Jump out of the water (user change, 2026-10-10):** SMB1's surface clamp (Y speed zeroed at a stroke above the line) is replaced: a press above the surface line, or on the floor of shallow water with the head above it, is a normal SMB1 jump (land jump data, S2 jump sound, `Mario_SwimForces` cleared) that carries him out. `Mario_Water` wraps `Sonic_Water` and undoes S2's ×2 exit speed for that jump (S2 doubles because Sonic's underwater jump is weaker); C-held swim strokes out keep the boost. The $18 surface force is unchanged. `test_phase7.py`'s "never out of the water" check is now obsolete (not re-run; the user is testing by hand).
    - **Water rule for enemies** (SMB1 `HandlePECollisions`, AreaType water): under water there is no stomping; touching a badnik hurts (`Mario_TouchEnemy`). Bosses keep the airborne-hit rule. So underwater badniks (e.g. ARZ's Chop Chop) only die to fireballs or a star.
    - Fireballs work under water unchanged (SMB1 does the same).
  - **Hold C to swim in the air (user requirement, softlock prevention):**
    - While Mario is airborne and C is held, `SwimmingFlag` is set: B presses are swim strokes (SMB1 swim physics), anywhere.
    - In water, holding C lifts the surface rules, so his strokes carry him out of the water and on up. Without C, B strokes are SMB1's and keep him under the surface.
    - **C doesn't jump (user, 2026-10-12):** only Genesis B is SMB1's A; C is just the air-swim hold. (Before this, B and C were both A, and `Mario_ReadJoypad` cleared A from `PreviousA_B_Buttons` on any B/C press so B counted while C was held; that workaround is gone.) The tests jump with B; `test_phase7.py` now checks that C doesn't jump. Its two obsolete checks were updated at the same time: a press at the surface now must jump out of the water, and drowning must not happen. The starpost/signpost section now restarts EHZ1 itself; it had relied on the drowning death. All of Phase 7 passes again.
    - Hang bars take only B too (H37, below). Other S2 objects that read the jump buttons still accept A/B/C, as for Sonic.
    - Releasing C in the air ends the swim (normal falling force).
    - Holding C through a B jump only enables strokes; the jump itself is unchanged.
    - Leaving the water upward, S2 doubles `y_vel` (its own exit rule) and `Mario_SyncState` treats that as a launch; a stroke clears `Mario_LaunchFlag`.
  - **Drowning: disabled (user decision, 2026-10-10; it was "a little broken").** `Mario_Water` refills `air_left` to 30 every frame, so S2's Obj0A never warns, counts down or drowns him (breathing bubbles still appear). Air bubbles (Obj24) ignore Mario: hook `Mario_BubbleSkip` replaces the bubble's `tst.b obj_control(a1) / bmi.w` (8 bytes, `jsr` + `nop`). Built, not tested (the user is testing). `test_phase7.py`'s drowning check is now obsolete.
  - **New sound:** `Sfx_EnemyStomp` (swim stroke) → `SndID_MarioSwimStomp` in unused slot **A9** (`tools/nes_sfx2smps.py` `swim_stomp()`: sweep plus SMB1's per-frame volume envelope as `smpsPSGAlterVol` steps, peak 15 = full volume; `simulate_square` learned `timer_lo` writes). Only played for strokes; stomps still use S2's explosion sound.
    - The bank was then 49 bytes over: with `marioMode` the never-played **B1** (zap) and **A5** (missile dissolve) now point at `Sound40` like BA, freeing their bytes. Only **$C3** (partly unused, check first) is left as a free candidate.
  - **Sound polish (user request, 2026-10-10; built, flag=0 still bit-perfect, not tested in the emulator; the user is testing):**
    - **Jumps:** `Sfx_BigJump`/`Sfx_SmallJump` (`nes_sfx2smps.py` `jumps()`) replace S2's jump (**A0**, `SndID_MarioBigJump`) and skid (**A4**, `SndID_MarioSmallJump`) sounds; the user allowed this because Sonic and Tails will be disabled later. `PJumpSnd` picks by `PlayerSize`, on `Sound_Queue.SFX2`. Sonic's jumps/skids would now play these too.
      - The user found them a little quiet: `JUMP_VOLUME_BOOST` (2 PSG steps = 4 dB) is applied to every step of their envelope, clamped at full volume.
    - **Skid:** SMB1 has no skid sound, so Mario's skid is silent (the S2 dust stays). User confirmed: keep it silent.
    - **Death music:** user-approved as is.
    - **APU model:** the converter now has a full NES channel model (`Pulse`/`Triangle`: volume envelope with start/loop/constant, length counter and $4015 stops, sweep incl. its always-on mute, triangle linear counter; frames = engine writes, then 4 quarter / 2 half clocks, sampled after the first quarter clock). The older sounds still use their own simpler simulations.
    - **Death music:** `death_music()` runs SMB1's music engine (`audio/engine.asm`) for `DeathMusic` frame by frame and writes `sound/music/Mario Death.asm`: an uncompressed S2 song (tempo $FF = one tick per frame for its 180 frames), square 1/2 and triangle on PSG1–3 (triangle an octave below a pulse, fixed attenuation `TRIANGLE_ATTENUATION`), a dummy DAC track. `build.lua` generates its `.inc` automatically (not listed in "list of compressed songs.txt").
      - It lives in the first music bank (`MusicPoint1`, which only had Continue); to make room in the second bank for the jumps, **Credits also moved to the first bank** with `marioMode` (its music ID is unchanged).
      - Its ID is `MusID_MarioDeath` = `MusID_SuperSonic` ($96): with `marioMode` the playlist entry points at it (Mario can't go super).
      - Played by `Mario_DeathSound`, a size-neutral hook on `KillCharacter`'s `jsr (PlaySound).l` (all deaths): as SMB1's `KillPlayer`/`LoadEventMusic`, no death sound, `MusID_StopSFX` (Music0) this frame and the death music (Music1) next frame. S2 still plays game over / time over music afterwards, and the level music on respawn.
  - **WFZ fixes (user report, 2026-10-10; verified in a live play session):**
    - **Fireball tiles moved again, to $79B–$79F**: the last 5 tiles of Mario's own 32-tile DPLC slot (his largest frame is `MarioFrame_MaxTiles` = 8; a `fatal` guards the overlap). $7B0 was corrupted in WFZ: the Tornado pilot's (Tails) DPLC reaches past $7AF.
    - **H20, the end-of-WFZ cutscene (ObjB2 routine 6)** scripts "the player" for Sonic. Three size-neutral hooks in `mario_polish.asm`:
      - `Mario_TornadoWait` replaces `move.l #(…Wait…),mapping_frame(a1)` in `ObjB2_Waiting_animation` and `ObjB2_Landed_on_plane`. Sonic's frame 1 was drawn with Mario's tiles (garbage); Mario gets his own standing anim, and the landing also ends his hop.
      - `Mario_TornadoHopArc` replaces `ObjB2_Jump_to_plane`'s first two instructions. The script's jump is a held A (Mario's run button), and an SMB1 standing jump couldn't cover the gap anyway (the Tornado starts ~90 px away and moves off at 1 px/frame).
      - So Mario hops: `obj_control` 1 (own movement off), jump frame and sound, x/y velocities computed so S2's `ObjectMoveAndFall` puts his feet on the Tornado's top `Mario_HopFrames` (40) later; ObjB2's own SolidObject lands him. If he ends up $80 below the Tornado, control comes back so he falls normally.
      - Later, the script's "jump to the ship" A press does nothing for Mario: he rides the Tornado into the docking and DEZ loads normally.
      - **Known cosmetic issue (user, 2026-10-10: leave for now):** at the end of the cutscene Mario makes no attempt to jump onto Eggman's jet. `ObjB2_Jump_to_ship` (state $E) holds A, which is Mario's run button. It looks fine because the Tornado pulls up to the Death Egg anyway. A fix would be another hop like `Mario_TornadoHopArc`, aimed at the jet; the docking may not expect the player to leave the Tornado, so check that first.
      - Live session (`watch_session.py` log): every state 0→$10, landed on the Tornado, DEZ loaded.
    - `tools/test_wfz_end.py` (spawns the cutscene at the last platform) has not been run against the final build: the first attempts used a wrong start position. The live session above is the verification.
    - **Test harness fixes:**
      - `blastem_gdb.read` used 1 KB chunks, but BlastEm's stub replies with at most 255 bytes; chunks are now $80.
      - `watch_session.py` logs the cutscene Tornado's routine/state/position, `Mario_TornadoHop`, `Control_Locked` and `Ctrl_1_Logical`. Env options for test runs: `MARIO_LIVES=99`, `MARIO_GOD=1` (keeps `invulnerable_time` topped up; pits still kill).
    - Playtest note for Phase 8: the user found the WFZ boss very hard as Mario.
  - **Fireball VRAM moved to $7B0** (superseded, see the WFZ fixes above) (Tails' tails slot). In SCZ/WFZ the Tornado's pilot (Tails, in Mario mode) DPLCs his frames into $7A0, which would have overwritten the fireball tiles.
  - **S2 hooks** (`mario/mario_polish.asm`, all size-neutral `jsr (X).l`):
    - H11 `Mario_StarpostRings`: Obj79's `cmpi.w #50,(Ring_count).w` → carry set in Mario's mode, so no stars.
    - H13 `Mario_LoadLifeIcon` (from `ObjMario_Init`): DMAs `MarioLife.bin` over the life counter, skipping the two tiles `Hud_Lives` draws the digits into ($113, $115).
    - H14 `Mario_TornadoRadius`: ObjB2's `move.b #$13,y_radius(a1)` → Mario's radius.
    - H15 `Mario_CameraBias`: ScrollVerti's rolling −5 → for Mario, feet − $13 (frames him as it frames Sonic; no jolt when his radius changes). The `fixBugs` Tails fix moved inside it.
    - H16 `Mario_SignpostFace`: when the signpost is passed, DMA `MarioSignpost.bin` over frame 0's tiles ($22–$39); it shows Robotnik and spins for 3 s first.
    - H16 `Mario_ResultsName`: the results name object uses `MapUnc_MarioEOLName` ("MARIO GOT", all letters already in the results art: M from MILES, R from THROUGH).
  - **Verified:**
    - `python -I tools/test_phase7.py`, 22/22: camera (H15); C jump = B jump frame by frame; hold C + B stroke mid-air; releasing C. In ARZ1 (water raised over Mario's start): water entry forces, water speed $10, floor stroke speed and its sound (PSG3 pitches against the generated file), 400 frames of strokes and mashing never leave the water while the $18 force applies, fireballs under water, hold C swims out 64+ px above the water, release falls back with the normal force, re-entry gives the swim force, underwater badnik hurts, drowning. In EHZ1: starpost with 50 rings makes no stars (H11), signpost frame 0, results mappings. Screenshots in `tools/out/phase7/` (signpost, results, HUD visible).
    - Phases 2, 4, 5, 6, breakables, star, power pause, power-up sound: all pass. Phase 3: only its pre-existing "land f5". Art verifies (66 frames).
    - **flag=0 bit-perfect with REV01** (also covers the Phase 5/6 sound changes, which hadn't been re-checked).
  - **Not verified at runtime:** H14 (needs the end of SCZ) and CPZ2's water (same code as ARZ). Both are on the Phase 8 playthrough.
  - Test harness note: `emu.frame()` returns stopped at `ReadJoypads`, before that frame's game logic, so RAM read right after shows the previous frame's result; a check that depends on this frame's input needs one more frame. Setting `Ring_count` ≥ 10 starts power tasks that pause the world (and Mario) for about a second each.
- [ ] Phase 7.5: SMB1-style WFZ boss (planned 2026-10-10, user design; **built and passing its test 2026-10-11, sounds still S2 stand-ins**)
  - **Status:**
    - **Code:** `mario/bowser.asm`.
      - `ObjBowser` ($4C): subtype $92 = the fight controller (ObjC5's laser case converted by `Mario_WFZBossInit`, a size-neutral hook in `ObjC5_Init`); subtype $10 = Bowser.
      - `ObjBowserMisc` ($4D): flame (0), hammer (2), axe (4). Both IDs were free `ObjNull` slots.
      - Fireball hits: `FireballEnemyCollision` sends harmful-class hits on Bowser to `Bowser_FireballHit`.
    - **Art:** `chr2md.py` `boss_art()` → `Bowser.bin` (35 tiles), `mappings/sprite/Bowser.asm`, frame IDs in `mario_frames.asm`. Palette line 1 (WFZ; "Mecha Bowser"). DMA'd over the laser case's tiles $379+$00..$58 once the boss PLC is done (the walls use $59–$60; a `fatal` guards it).
    - **Fight:** Mario enters from the left.
      - **Trigger** (user fix 2026-10-11: "as soon as you enter the arena"): Mario x ≥ case x − $78, just inside the left wall, and y ≥ case y (not passing above). Mario usually arrives running, down a step at x ≈ $2AA0 (old trigger: mid-arena).
      - **At the trigger:** walls, Robotnik, the music fade, and also Bowser (front x = case + $18, on the floor found by `ObjCheckFloorDist`) and the axe (case + $70, standing on the floor: user said 16 px up was too high). Only the boss music waits for the fade.
      - **Bug fixed (user report):** the fireball kill's 5000 points used `move.w` into `AddPoints`, which adds all 32 bits, so the score jumped to 999999 (displayed 9999990). Now `move.l`.
    - **Bowser = SMB1 code** (`BowserControl`, world-8 flames + hammers, `PRandomRange`/`FlameTimerData`, `MoveEnemySlowVert` gravity $0F max 2, the jump −2.0). SMB1's 8-bit screen constants became arena-relative: ground = the floor; "past $C8" = `Bowser_ChaseLimit`. On landing he's snapped to the floor (port).
    - **Flames:** fly left 1.25 px/frame towards a random height (FlameYPosData relative to his standing top).
    - **Hammers:** held over his head ~14 frames, thrown ±1 px/frame with −2.0, gravity $10 max 4; 9 misc slots (`Bowser_HammerSlots`).
    - **Collision:** Bowser, flame and hammer are harmful (sizes $0E/$1B/$0B); no stomping him.
    - **Axe:** a box test against Mario. Then `Control_Locked`, music fade, and Bowser's `RemoveBridge` timing (feet every 4 frames ×15, blast + shatter sounds), state $40 fall, `KillAllEnemies`. Then ObjC5's ending: the case's `p1_pushing` bit (walls flicker out, Robotnik sinks), 100 points, $EF frames of explosions anywhere on screen, WFZ music, camera floor $720, controls back.
    - **Fireballs:** 5 hits (`HurtBowser`): upside down, −2.0 hop, falls away, 5000 points; the fight only ends at the axe.
    - **Verified:** `python -I tools/test_bowser.py`, both runs pass: (A) the fight starts, 2 walls, Bowser paces/jumps/flames/hammers, his touch hurts, axe → collapse → fall → explosions → ending, walls gone; (B) 5 fireball hits, he falls away, not over until the axe. Screenshots in `tools/out/bowser/`. flag=0 still bit-perfect.
    - **Bug fixed while testing:** `ImposeGravityS2` lost its force/cap in d0/d1 to `ObjectMove` (Bowser rose forever).
    - **Still to do:** convert SMB1's `Sfx_BowserFlame` (noise channel: the converter has no noise model yet), `Sfx_BowserFall`, `Sfx_Blast`, `Sfx_BrickShatter`; the stand-ins are `SndID_Fire`, `SndID_Bonus`, `SndID_BossExplosion`, `SndID_Smash` (mario.constants.asm). A user playtest in normal and hard mode.
    - **Sounds (user, 2026-10-11): keep the S2 stand-ins** (flame, fall, collapse); no SMB1 conversion needed.
    - **Castle theme (done 2026-10-10, user request; the user is judging the sound):** SMB1's castle music plays for the fight, in music slot **$9F** (`MusID_BowserCastle` = `MusID_Countdown`, s2.constants.asm; free because drowning is disabled).
      - **Generated** by `castle_music()` in `tools/nes_sfx2smps.py` → `sound/music/Mario Castle.asm` (never hand-edit). It runs SMB1's engine on `CastleMusData` as area music, frame by frame, through the NES APU model:
        - The squares' control reg is rewritten every frame from `AreaMusicEnvData`. A note's first frame reads one byte past that table (offset 8 is read before the decrement), so it's silent: SMB1's staccato.
        - Triangle control $FF for lengths ≥ $12 (every castle note), else $1F.
        - No noise. `LoadHeader`'s $4015 write clears the triangle at the loop.
      - **Loop:** the converter simulates two passes and fails unless they're identical. It writes one 480-frame pass, and each PSG track ends in `smpsJump` to its own start (where SMB1's `EndOfMusicData` → `MusicLoopBack` restarts). `write_song`/`emit_psg(loop_label)` are shared with the death music, whose output is byte-identical to before.
      - **Tempo (decision): drift accepted.** With tempo $FF the S2 driver skips one tick every 256 frames, so the song runs 0.39% slower than SMB1: every channel holds one extra frame about every 4.3 s. Compensating would mean either dropping frames, which adds a second kind of 1-frame glitch because the skipped ticks wander relative to a 480-frame loop, or unrolling 8 passes (~20 KB).
      - **Wiring (all `if marioMode`):**
        - `zMusIDPtr_Countdown` → `Mus_MarioCastle`, without `MusFlag_SlowerOnPAL`, so on PAL it keeps NTSC speed like the death music.
        - The $9F `zSpedUpTempoTable` entry is $FF instead of $80; $80 would halve its speed with speed shoes.
        - The song is in the first music bank (`MusicPoint1`, after Mario Death; the bank is at $263C of $8000).
        - `Arena_WaitMusic` (bowser.asm) plays `MusID_BowserCastle`. The axe still fades it out and the ending plays WFZ music.
        - S2's only other $9F users are the drowning countdown (disabled) and the 2P loser countdown (2P only).
      - **Verified:**
        - `tools/test_bowser.py` passes both runs, with a new music check: `zCurSong` reads $9F in Z80 RAM, and the PSG1 track's data pointer stays inside `MarioCastle_PSG1` and jumps back to its start 481 frames after the song begins (expected ≈ 480 × 256/255 = 482).
        - flag=0 is still bit-perfect.
    - Note: 8-4's real hammer rate is high (49 hammers in 900 frames in the test); kept faithful unless the user finds it too much.
  - **Why:** the WFZ boss (ObjC5) is a laser case on the ceiling. Sonic jumps into it; Mario can barely reach it. Normal mode only works because bosses take airborne hits from any angle, and hard mode's falling-only rule (rule 8) would make it impossible.
  - **The design (user, revised 2026-10-11): SMB1's Bowser himself is the WFZ boss.** (An earlier idea, Eggman in the Eggmobile acting like Bowser, was dropped.)
    - Mario starts on the left of the caged-in laser arena. Bowser is between him and **SMB1's axe** on the right (deliberately out of place in high-tech WFZ: the user wants it funny).
    - Mario has to get past Bowser and touch the axe. Bowser then dies as in SMB1 (falls off the screen), then a run of explosion effects across the screen, then everything plays out as after S2's WFZ boss.
    - Eggman stays outside the arena with his usual escape animation (ObjC5's Robotnik on his platform, sinking away).
    - Both difficulties. Sonic and Tails will be phased out entirely (user, 2026-10-11), so the original ObjC5 fight does not need to keep working in the Mario build.
    - Bowser's behaviour: translate SMB1's own code (`BowserControl` etc.: pacing, jumping, the flame, fireball hits).
    - **Decided (user, 2026-10-11):**
      - **Projectile: Bowser's own flame** (not MTZ3's laser).
      - **Hammers too**, as 8-4's Bowser: it's the penultimate zone's boss.
      - **Fireballs can kill him**, as in SMB1, but the end-of-level sequence (explosions, S2's post-boss events) only starts when Mario touches the axe.
      - **Colours:** he's "Mecha Bowser" (the lore reason his colours are off), so mapping him onto the nearest colours of an existing S2 palette line is fine.
    - Art: Bowser is in `gfx/sprites.chr` (`chr2md.py`); his SMB1 colours (green/orange, sprite palette 1) don't fit palette line 0, so use the closest colours in a WFZ palette line, per the "closest existing S2 colours" rule.
  - **Scouting (from the code, 2026-10-10):**
    - **Placement:** ObjC5 is in WFZ_1's layout at ($2B80, $450), subtype $92. The level event (`LevEvents_WFZ_Routine5`, camera ≥ $2880/$400) loads `PLCID_WfzBoss` and sets `Camera_Min_X_pos` = $2880.
    - **The fight:** starts when the player is within ±$20 of the case. The two laser walls are at case x ± $88 (y + $60), giving an arena of about $2AF8–$2C08 (272 px). The case moves within x ± $60 and has 8 hit points. During the fight `Camera_Max_Y_pos` = $442.
    - **The end (`ObjC5_End`):** WFZ music, `Camera_Max_Y_pos(_target)` = $720 (opens the way down to the cutscene platform at y ≈ $5F0), the case deletes itself. Robotnik (ObjC5 $10, platform at $2C60/$4E6) sinks for $C0 frames and is deleted when the case's `p1_pushing` bit is set (`ObjC5_NoHitPointsLeft`).
    - The new boss must reproduce those effects (music, camera limits, walls, 100 points) and then let `LevEvents_WFZ_Routine6` / the Tornado cutscene (H20) run unchanged.
    - **MTZ laser (`Obj54_Laser`, s2.asm ~68331):** art `ArtNem_MTZBoss` at `ArtTile_ArtNem_MTZBoss` ($37C), mappings `Obj54_MapUnc_32DC6` frame $12, plays `SndID_LaserBurst`, and deletes itself outside the hardcoded MTZ x range $2AB0–$2BF0. So the new boss needs its own copy of the laser.
    - **VRAM:** `ArtNem_WFZBoss` loads at $379 (not needed in Mario mode). The MTZ boss PLC uses $37C (MTZBoss), $500 (Eggpod_4) and $560 (EggpodJets_2). $500 is the Tornado's, but `PLCID_Tornado` only loads after the fight (`LevEvents_WFZ_Routine6`). **Still to check:** that WFZ's level art doesn't use $500–$5FF while the boss is on screen.
    - **Axe:** in SMB1 it's a background metatile, not a sprite, so it comes from SMB1's BG pattern table. `chr2md.py` currently reads only `gfx/sprites.chr`.
  - **Plan:**
    1. VRAM: check what WFZ uses around the boss and pick slots for Bowser, his flame and the axe. Load them instead of `PLCID_WfzBoss` (hook in `LevEvents_WFZ_Routine5`). Uncompressed art + DMA, as Mario's.
    2. Art via `chr2md.py`: Bowser's frames and flame from `sprites.chr`, the axe from SMB1's BG CHR, colours mapped to the chosen palette line.
    3. A Bowser object translated from SMB1 (pacing, jumps, flame, fireball hits), on S2 terrain, inside the arena walls.
    4. Replace ObjC5's fight in the Mario build: keep its laser walls, Robotnik and the end effects (music, camera limits, 100 points), and drop the laser case.
    5. The axe: touching it starts Bowser's SMB1 death fall, then explosions across the screen (`Boss_LoadExplosion`-style), then ObjC5's end sequence. Robotnik sinks away as in the original.
    6. Sounds as SMB1 (Bowser's fall, the flame) through `nes_sfx2smps.py`, if they fit the sound bank.
    7. Tests: a scripted run (get past him, touch the axe, his touch and flame hurt, fireballs) plus a live session in normal and hard mode.
  - **Hard mode rule #1 (head bumps hit ceiling bosses):** the user likes it for hard mode. With the new boss this rule no longer applies to WFZ; keep it in mind for any other ceiling-mounted boss.
- [ ] Phase 7.6: Sonic and Tails disabled, Luigi added (user request, 2026-10-10; built, all tests pass, waiting for the user's playtest)
  - **Character select (H21):** with `marioMode` the options menu offers only **MARIO** and **LUIGI**: `Player_option` 0/1 (`PlayerOpt_Mario`/`PlayerOpt_Luigi`, `PlayerOpt_Count`), so power-on defaults to Mario.
    - `Mario_SetPlayerMode` (size-neutral, replaces `move.w (Player_option).w,(Player_mode).w` in `Level_SetPlayerMode` and the level select's start) always sets `Player_mode` = 3 (`PlayerMode_Mario`), so none of S2's `Player_mode` checks change.
    - `ObjMario_Init` sets `Mario_IsLuigi` from `Player_option` (the Mario RAM block is cleared every life; `Player_option` persists).
    - Sonic and Tails stay in the ROM. Demos and 2P mode still force Sonic and Tails (S2's own code, not changed).
    - Hard mode (Phase 9) now needs new option numbers (e.g. 2/3 = MARIO/LUIGI HARD), not `Player_option` = 4.
    - Test harness: `boot_to_level(emu, option)` now takes 0 = Mario (default), 1 = Luigi; `watch_session.py`'s option argument likewise.
  - **Luigi = SMB2J's Luigi** (Lost Levels; data from threecreepio/smb2j-disassembly `sm2main.asm` `JumpFrictionData`/`LoadPhysicsData`):
    - `LuigiJumpMForceData` $18,$18,$18,$22,$22,$0D,$04 and `LuigiFallMForceData` $42,$42,$3E,$5D,$5D,$0A,$09: less gravity with the same jump speed, so a higher, floatier jump.
    - `LuigiFrictionData` $B4,$68,$A0 (Mario $E4,$98,$D0): lower acceleration and deceleration.
    - SMB2J patches X_Physics' friction doubling (`PhyOpcode`) into an RTS for Luigi: no 2x friction when turning, so he skids further.
    - Everything else (speeds, swim data, Y speeds) is Mario's; the 1.5x/1.25x S2 scaling applies to both.
    - `Mario_InitFallForce` gives the starting/after-swimming falling force from the character's table ($70 Mario, $42 Luigi).
    - **Uphill tuning (user, 2026-10-10, being playtested):** with the lower acceleration, S2's slope resistance (max $20/frame) stopped Luigi on slopes Mario climbs (running from a standstill: ~32 degrees vs ~42; per-frame acceleration 16.9 vs 21.4 S2 units). `Luigi_Uphill` (`mario_physics.asm`): on the ground, pushing up a slope steeper than `Luigi_UphillAngle` ($08, about 11 degrees), Luigi uses Mario's `FrictionData` and turn doubling. Flat ground, downhill and the air keep SMB2J's values. Options not taken: weaker slope resistance for Luigi (changes downhill speed), or leaving it as Lost Levels.
  - **Luigi's colours:** SMB1 Luigi = white cap/shirt ($6), skin ($F), green ($19). Line 0 has no green, and every entry is used by some line-0 object, so:
    - `tools/luigi_palette.py` frees **entry $2** (Sonic's darkest blue, used by the fewest arts): the 17 level object arts drawn only with line 0 that use $2 (shield, monitors, signpost, game over text, Flicky, Crawl, Turtloid, lever spring, ARZ water top, WFZ scratch/turret, ARZ/MCZ/MTZ/OOZ/WFZ/DEZ bosses) get their $2 pixels moved to $3 (the next blue), re-encoded with a new Nemesis compressor (`tools/nemesis.py compress`, round-trips every S2 .nem file at about the original size) into `art/nemesis/luigi/`, labels in `mario/luigi_slot_arts.asm`. s2.asm keeps the originals as `<label>_S2` (unused) so nothing before the Mario code moves. Level tiles and Tails' art never use $2. The Special Stage background is excluded (its own palette).
    - Gotcha (fixed): Nemesis data must start on an even address (`NemDec` reads the header with `move.w`); the generated file has `even` before each art. Without it the game hung on the level load (address error).
    - **H22 `Mario_PalPointers`** (size-neutral, replaces `lea (PalPointers).l,a1` in all four `PalLoad_*`): while Luigi plays a level (`Game_Mode` level or title card), `Pal_BGND` and the HPZ/CPZ/ARZ underwater palettes load from Luigi's copies with entry $2 = `LuigiGreen` ($0080, nearest to NES $19). The underwater greens (`LuigiGreen_*_U`) are fitted to each underwater palette's tint of line 0. Mario keeps S2's colour in entry $2 (nothing uses it now).
    - `chr2md.py` generates `Luigi.bin` (Mario's tiles, Luigi remap 1→$6, 2→$F, 3→$2), `LuigiLife.bin` ("LUIGI": L from MILES, I from SONIC, U and G drawn as `GLYPH_U`/`GLYPH_G`), `LuigiSignpost.bin` (light-blue panel, as his white cap vanished on white). Fire Luigi uses `MarioFire.bin` (same as SMB1). Previews: `tools/out/luigi_sheet.png`, `luigi_life.png`, `luigi_signpost.png`. S2 art decoded for line-0 pieces (signpost border) gets the same $2→$3 move.
    - `LoadMarioDynPLC` uses `ArtUnc_Luigi` for bank 0; `Mario_LoadLifeIcon`, `Mario_SignpostFace`, `Mario_ResultsName` ("LUIGI GOT": L $5C2, U $5D8 from THROUGH) pick Luigi's versions.
    - Star flash for Luigi cycles entries $2/$A/$C/$F (`LuigiStarEntries`: Mario-like blue/red, fire-like red/white, enemy black/brown). His white cap/shirt ($6) doesn't flash: $6 is shared with explosions, monitors etc.
  - **Verify:** `python -I tools/test_luigi.py`, 27/27 (since the uphill tuning: running up EHZ1's first hill uses $E4, the flat $B4): menus, palettes, SMB2J physics vs Mario (friction steps $68/$B4, no turn doubling, forces $18/$42), held standing jump 109 px vs Mario's 79 px. Screenshots in `tools/out/luigi/` (HUD "LUIGI", shield with no green). Phases 2, 4, 5, 6, star, power pause, breakables and Bowser all still pass. flag=0 still bit-perfect.
  - User playtest (2026-10-10): "works perfect". The 1-up monitor shows Mario (not Sonic). Known: Luigi's star flash leaves his white parts white.
- [ ] Phase 7.7: softlock fixes from the user's playthrough (started 2026-10-10; the user reports softlocks one at a time)
  - **HTZ loop rock floors (H23, done 2026-10-10):** Obj2F breaks only when the player stands on it with the Roll anim AND (subtype bit 7 or `top_solid_bit` = $E); otherwise it sets the player to path $C. HTZ1's and most of HTZ2's (subtype 0) are in the loops: Sonic rolls onto them along the loop's path $E. Mario never rolls, and his stomp landings (Roll while falling, `Mario_StompAnimID`) weren't on path $E, so he couldn't break them.
    - `Mario_SmashGroundPath` (`mario_polish.asm`, size-neutral, replaces the two main-character `cmpi.b #$E,(MainCharacter+top_solid_bit).w` in Obj2F): for Mario the path test always passes, so **jumping and landing on the rock breaks it**, on any path. Walking onto it still doesn't (S2's anim test).
    - Placements: HTZ1 x $1630, $24B0; HTZ2 x $06B0, $0C30, $1D30 (subtype 0), $0E30, $0EB0, $0F30 (subtype $80, always breakable).
    - Verified: `tools/test_breakables.py` 8/8 (new case: subtype 0 with Mario on path $C). flag=0 bit-perfect. Not yet played in HTZ by the user.
  - **Hang bars (H37, done 2026-10-12, user report: Mario's jumps off them were too small for WFZ; air swim was the only way through).**
    - **Which objects:** Obj7F (MCZ vine switch), Obj80 (MCZ vine pulley, WFZ chain hooks) and ObjD9 (WFZ handles). They drop the player with `y_vel` −$300/−$380: about 20 px under S2 gravity, which Sonic turns into distance with his fast air acceleration. SMB1's standstill air control can't.
    - **Fix:** `Mario_HangRelease300/380` (`mario_polish.asm`) replace those `move.w #…,y_vel(a1)` instructions (size-neutral). Other characters get S2's value. For Mario, letting go is his own standing jump: `InitJS_Swim` with `SwimmingFlag` and `Player_XSpeedAbsolute` cleared (C held doesn't make it a stroke), `y_vel` from `Mario_JumpSpeed`, and `Mario_LastYVel` set so it isn't taken for an S2 launch. Holding B gives the held-jump height. Obj80's sideways ±$200 is kept.
    - **Buttons:** the release checks of these three and ObjC1 (WFZ plating, which just drops you) take only B under `marioMode`.
    - **Verified:** `tools/test_hangbar.py` (ObjD9 spawned in EHZ1): C and A don't release; B gives −1240 (SMB1's standing jump), 83 px held, 36 px tapped. flag=0 bit-perfect. Not yet played in WFZ by the user.
- [ ] Phase 7.8: removing Sonic's remaining traces (started 2026-10-11; small changes, the user names them one at a time)
  - **Opening text (H24, done):** the title screen's "SONIC AND MILES 'TAILS' PROWER IN" becomes "MARIO 'JUMPMAN' MARIO / AND / LUIGI 'GREEN' MARIO / IN". `Mario_IntroText` (`mario_polish.asm`) is a copy of S2's `off_B2B0` table and strings with the intro charset copied too; the `lea (off_B2B0).l,a1` in the title setup points at it (size-neutral). In this font I and ' are 1 cell wide, a space 1 cell, other letters 2; the apostrophe glyph draws as a double quote. Verified by a BlastEm screenshot (`tools/out/intro/`); flag=0 still bit-perfect.
  - **Ending cutscene player (H25, done):** ObjCA loads "the player" as Obj01 with obj_control $81 and only positions it (Float2 anim at $A0,$50 during the fall; ObjCC's loc_A53A stands it on the rescue plane with the Wait anim every frame). Now:
    - `Mario_EndingLoad` replaces loc_A2E0's `move.b #ObjID_Sonic,id(a1)`: ObjMario with routine **$C** (`ObjMario_Ending`, new `ObjMario_Index` entry).
    - `ObjMario_Ending` (`mario_polish.asm`) is a puppet: no physics/input/touches. Killed frame (`MF_Killed`) while falling, small standing (`MF_SmallStand`) when the anim is Wait; DPLC via `LoadMarioDynPLC` with the normal art bank. For Luigi it writes `LuigiGreen` into `Target_palette` entry $2 every frame (the ending's line 0 is Sonic's; the cutscene's ObjC9 fades bring it in).
    - `Mario_EndingStand` replaces loc_A53A's `move.l #(1<<24)|…|Wait,mapping_frame(a1)` (it runs after ObjMario, so the frame has to be set there) and lowers him by `$13 - Mario_SmallYRadius` so his feet are on the wing.
    - Not changed (the user is doing custom ending sprites next): the plane close-up and the ending pictures (`ArtNem_EndingSonic`, `MapEng_Ending*`, ObjCE/ObjCF frames), and the Super Sonic ending path (unreachable: no emeralds in Mario mode).
    - Verified in BlastEm for Mario and Luigi (`tools/out/ending/`; a test that jumps straight from EHZ shows a garbage fall background, so warp to DEZ first). flag=0 still bit-perfect.
  - **Ending art pipeline (H26, done 2026-10-12; the user is drawing the art):** `tools/ending_art.py export|import` (docstring; user how-to in `ending_art/README.txt`).
    - **Files** in `so-retro/ending_art/` (the user's working files):
      - `photo1-4.aseprite`: 96x72, each with its own 16-colour palette.
      - `closeup.aseprite`: 184x120, 23x15 tiles of plane A.
      - `sprite_07-0E.aseprite`: ObjCF frames $07-$0B (player on the small Tornado; the Tornado is on a locked "Reference" layer) and $0C-$0E (the jump at the camera).
      - Close-up and sprites use a 64-colour palette (index = line×16 + colour; fixed, shared lines); one line per 8x8 tile. Layers "Reference"/"Original" aren't imported.
      - **Colour snapping (user request, 2026-10-12):** the user can't tell the lines apart, so import (`snap_to_lines`) picks per 8x8 tile the line that best matches the colours as drawn (the file palette's RGB, weighted distance), moves each pixel to its nearest colour there, and lists every changed tile. The user's first art set had the right colours on the wrong lines in sprites 08/0D/0E; 42 tiles were snapped, with 1 pixel visibly different.
    - **The .aseprite reader/writer is in the tool.** Aseprite writes the old 0x0004 palette chunk, not 0x2019. Verified by re-saving every file through the Aseprite CLI (`Aseprite.exe -b in --save-as out`; it's a GUI exe, so use `Start-Process -Wait`) and by a Lua-scripted edit (`--script-param`, `--script`) carried through to the game.
    - **Import generates** `art/nemesis/mario_ending/`, `mappings/misc/mario_ending/` (an Enigma encoder: common-value runs + inline literals), `art/palettes/mario_ending/Photo1-4.bin`, `mappings/sprite/MarioEndingCF.asm` (objCF with frames $07-$0E re-cut into ≤4x4 pieces, the Tornado pieces kept) and `mario/mario_ending_art.asm`. It decodes everything again and compares it with the Aseprite art.
    - **Photos:** S2's four photos fill the whole $328-$492 gap (363 tiles), so each photo now loads its own art and palette as it comes up. `Mario_EndingPhoto` (`mario_polish.asm`) replaces loc_A256's `movea.l off_A29C(pc,d0.w),a0 / lea (Chunk_Table).l,a1` (10 bytes). It NemDecs with interrupts off and copies the palette to `Mario_EndingPal` (new, 32 bytes of Mario RAM); ObjC9 subtypes 4/6 (`off_133A4/off_133B0`) read that instead of `Pal_AD1E`.
    - **Label swaps (size-neutral):** `ArtNem_EndingFinalTornado`, `ArtNem_EndingPics` (now photo 1, reloaded per photo anyway), `MapEng_EndingTailsPlane`, `ArtNem_EndingSonic` (character art at $19, budget up to $155), and `ObjCF_MapUnc_ADA2` in ObjCC (loc_A4B6) and ObjCE_Init. ObjCF (helixes) keeps S2's mappings.
    - **Budgets:** close-up $156-$1FF (170 tiles; plane B's second table starts at $4000 = tile $200).
    - **Not covered:** Tails (pilot, the big Tornado `ArtNem_Tornado`), the "Sonic the Hedgehog 2" logo after the credits (`ArtNem_EndingTitle`/`MapEng_EndGameLogo`, palette-cycled), the credits text, Super Sonic's/Tails' ending art.
    - **Luigi's character frames (done 2026-10-12, user report: the Luigi ending showed Mario, with green bits):**
      - **The bug:** while Luigi plays, line 0 entry $2 is his green (ObjMario_Ending writes it into the ending palette). Mario's frames use dark blue on both line 0 (entry $2) and line 1 (entry $2, the same blue), so the line-0 tiles went green and the line-1 tiles stayed blue. The close-up doesn't use entry $2, and S2's small Tornado pieces have no entry-$2 pixels.
      - **The two sets:** `ending_art/luigi/sprite_07-0E.aseprite` is Luigi's set.
        - `python -I tools/ending_art.py luigi [--force]` makes it from Mario's current frames. `LUIGI_RECOLOUR` turns red → white, dark red → grey, and dark blue → `LuigiGreen` (read from `mario/luigi_palette.asm`), on `luigi_lines()`. That gives SMB1 Luigi, like the in-game sprite. Mario's art is kept as a hidden "Original" layer.
        - `export` also creates missing Luigi files. `import` requires them and imports both sets (`import_chars`): `Character.nem`/`LuigiCharacter.nem` and `MarioEndingCF.asm`/`LuigiEndingCF.asm` (`MapUnc_<who>EndingCF`). Both load to the same VRAM ($19–$155). Previews: `tools/out/ending_art/luigi_sprite_*.png`.
      - **Game side:** `Mario_EndingCharArt` and `Mario_EndingCFMap` (mario_polish.asm) pick the set by `Player_option`, because the ending can start from the level select without a level. They replace the H26 label swaps (`lea` 6 bytes; `move.l` 8 bytes → jsr + nop).
      - **Verified:** Mario's generated art is byte-identical to before (only the mappings' header comment changed). The Luigi ending in BlastEm shows white/green Luigi on the small Tornado and in the jump; Mario's is unchanged. flag=0 is bit-perfect.
    - **Verified:** the unchanged round trip plays the whole ending in BlastEm. Edits (photo rectangle + palette entry, close-up block, a new sprite piece) show up in game. flag=0 bit-perfect.
  - **Title screen art pipeline (H27, done 2026-10-12; the user is drawing):** `tools/title_art.py export|import` (docstring; how-to in `title_art/README.txt`). It reuses ending_art.py's helpers (Aseprite I/O, Enigma, snapping).
    - **Files** in `so-retro/title_art/`:
      - `banner.aseprite`, 320x224. Layers:
        - Art: plane A, the logo map.
        - Top: sprite in front of the characters (Obj0E frames $A/$B).
        - TM: overseas only, frame $B.
        - Cut: a hidden mask, imported anyway. Those cells become low-priority sprites copying the banner's own pixels, S2's trick that puts the emblem over Sonic.
        - Background/Characters/Copyright: references.
      - `sprite_00-07,09,12,13`: Obj0E's Sonic (05-07, 12, hand 09) and Tails (00-04, hand 13) frames. Frame 08 (S2's armless leftover, shown one frame with fixBugs=0) becomes a copy of 12.
    - **Palettes:** lines 0/1/3 are editable (a change in any file applies everywhere; unedited files keep their indices). Entries used by the menu (Obj0F: line 0 and line 3 highlight), the copyright text, the stars and colour 0 are locked; line 2 is fixed. Line 3 has only 2,3,9,11,14,15 free. They're written as same-size files in `art/palettes/mario_title/`; s2.asm's `Pal_Title`/`Pal_133EC`/`Pal_1342C` BINCLUDEs are swapped under `marioMode`.
    - **VRAM:**
      - Banner: free slots of the title art at 0-$14F (background tiles kept at their indices), then $40C-$4AB.
      - Sprites: $150-$3F1, then $4BE-$67F (Std1's Numbers sits at $4AC-$4BD; the font is at $680).
      - S2's sprite art fills $150-$3F1 exactly; Sonic's final arm piece and Tails' hand come from MenuJunk ($3F2+), which stays. The re-cut originals need 693 tiles.
    - **`Mario_TitleLoadArt`** (`mario_polish.asm`) replaces the two NemDec loads (40 bytes: jsr + 17 nops) and walks `Mario_TitleArtTable` (generated). Its pointer is in a3 because NemDec doesn't save a2.
    - **Other swaps:** `MapEng_TitleLogo` → `MapEng_MarioTitleLogo`, with the base `make_art_tile(Title,3,1)` → `(Title,0,1)`. EniDec ADDS inline palette bits to the base's, so line 3 as the base made lower lines impossible; `enigma_encode` now asserts this and stores the line relative to the base. Obj0E's mappings in Obj0E_Init and TitleScreen_InitSprite → `MapUnc_MarioTitle0E`.
    - **Spare palette entries (2026-10-12):** the user's first import mixed lines: Mario's skin from line 2, blue and red from line 3. Before snapping, import collects every tile's colours as drawn. If no line holds them all, it copies the missing ones into editable-line entries that are unlocked and not used by any tile or by any pixel drawn directly. The first art set filled line 0 colours 2 ($00C) and 8 ($6AE); all 102 snapped tiles then kept exact colours. Both tools now only list snapped tiles whose colours changed, and count exact line moves.
    - **Palette line timing (user report, 2026-10-12):** Mario's blocks snapped to line 2 stayed black until the background flash. On the title, line 1 is live from the start, line 3 fades in from frame 56, line 0 is set at frame 128, line 2 is black until frame 288. So:
      - Sprites may only use lines 0/1/3 (`SPRITE_LINES`).
      - Banner/Top/TM use `BANNER_LINES` (3, 1, 0), ranked; pass 1 accepts only line 3 for them, and spare entries go to line 3 first. Import warns for banner tiles off line 3.
      - `snap_to_lines` now takes `lines` and `ranked`.
      - Verified in BlastEm: no black blocks at frame 270.
    - **Subtitle (user request, 2026-10-12):** "FOR SUPER PLAYERS" (after SMB "for Super Players").
      - `title_art/subtitle.txt` (text/row/column/line) is read by `read_subtitle`. Import writes standard-font tiles ($680 + S2's font codes, the title loads them) into the banner map words, like S2's copyright. They're `plane.get(t) or v[t]` in the Cut builder.
      - Placed at row 23 (y 184-191; the user's banner ends at y 183), columns 11-27 (17 chars can't be centred on the 8 px grid: 4 px left of centre), line 3, so it fades in with the banner.
      - The menu's "1 PLAYER" was at y 192-199 (Obj0F at centred y 92, pieces -$C/+4), touching it.
      - **H28 (user request):** Obj0F_Init's y is now centred(100) under `marioMode`, so the menu sits 8 px lower. It's one object, so all three states move: 1P/2P at y 200/216, OPTIONS at y 204. "2 PLAYER VS" now ends on the screen's last line (y 223), next to the copyright (row 26, x 224+), no overlap.
      - Verified in BlastEm, all three menu states.
    - **Title menu MARIO GAME / LUIGI GAME (H29, user request, 2026-10-12):**
      - `MapUnc_MarioTitleMenu` (`mario_polish.asm`, set in Obj0F_Init) replaces "1 PLAYER"/"2 PLAYER VS".
        - The text uses the standard font (1x1 pieces via the `titleMenuText` macro under a temporary `charset`); the highlighted line is on palette line 3, the other on line 0, and the arrow is MenuJunk $3FA. OPTIONS is S2's frame copied.
        - Gotcha: write `('ch'|0)`. Inside `dc.w`, AS emits `'M'` as a string (an extra word per piece, so the frames came out as garbage).
      - `Mario_TitleChoice` replaces `move.b (Title_screen_option).w,d0 / bne.s TitleScreen_CheckIfChose2P` (6 bytes). Options 0/1 set `Player_option` (= `PlayerOpt_Mario`/`Luigi`) and fall into S2's 1-player start (the level select cheat with A held works too). Option 2 pops the return address and jumps to `TitleScreen_ChoseOptions`.
      - 2P VS is no longer reachable from the title (the user is updating the options menu next phase).
      - Verified in BlastEm: MARIO GAME → EHZ1 as Mario; LUIGI GAME → as Luigi (`Mario_IsLuigi` $FF, HUD "LUIGI"); OPTIONS → options menu ($24). flag=0 bit-perfect.
    - **First user import:** S2's banner leaves the area behind Sonic's quills empty; with the smaller Mario a notch of background shows above-right of his hat. The banner needs filling there (told the user). Tails' frames 00, 01 and 13 are still S2's.
    - **Intro masking sprite** (frame $11, until frame 464) hides the characters below screen line 112 (documented for the user).
    - **Verified:**
      - Unchanged round trip: the full intro plays in BlastEm.
      - Edits (banner block, Top block, a sprite block, recolours of an unlocked line-3 and line-0 entry, a locked line-0 entry refused) show up correctly after an Aseprite re-save.
      - Aseprite CLI re-save of every title file is identical.
      - flag=0 bit-perfect.
    - **Test harness note:** an Aseprite Lua script (`Image:drawImage` + `Sprite:newCel`) lost the existing pixels of the banner's layers, though not of the sprite files. For scripted test edits, edit in Python (`ase_read`/`ase_write`) and then re-save through `Aseprite.exe -b --save-as`.
- [ ] Phase 7.9: Post-credits scene (user design, 2026-10-12; built, `tools/test_postcredits.py` passes for Mario and Luigi; waiting for the user's playtest)
  - **What happens:** after the credits and the "Sonic 2" logo (or a button press on it), EHZ2 loads at x $28A0. Super Mario walks right, hops onto the prison capsule's button, and Peach hops out instead of the animals. He hops off and lands $1C left of her, facing her. The victory music starts as he jumps off the capsule (user's cue, 2026-10-12; SMB1 starts it with the second message line). Then SMB1's world 8 timing: "THANK YOU MARIO!" at once; at 192 frames the first Lost Levels line; a line every 64 frames; 8 s hold; fade to black; SEGA screen. Luigi's version says LUIGI.
  - **Code:** `mario/mario_postcredits.asm`.
    - H35 `Mario_PostCreditsStart` replaces EndgameCredits' `move.b #GameModeID_SegaScreen,(Game_Mode).w`. It sets up a fake starpost restart (Saved_* values: position, `Saved_Dynamic_Resize_Routine` 6 = past the boss events, `Saved_Camera_Max_Y_pos` $380), `RunPLC_ROM`s the capsule and explosion art, and starts Level with `Demo_mode_flag` = -1. That is S2's old credits-demo path: no music fade, no title card, no PLCs, no `Level_SetPlayerMode`. The title screen clears the flag; the scene clears it too when it ends.
    - H36 `Mario_CapsuleOpen` replaces Obj3E's `move.b #1,anim(a0)` when the capsule opens. In the scene it spawns Peach and skips the animals and `Load_EndOfAct`.
    - `ObjMario_Init`, when `Demo_mode_flag` < 0: big Mario (0 rings keep him big) and spawns the director.
    - `ObjPostCredits` (ID **$4E**, a free ObjNull): subtype 0 is the director, which is also the message sprite; subtype 2 is Peach. The director locks controls and writes `Ctrl_1_Logical`, hides the HUD (clears `Level_started_flag` every frame), stops EHZ's PLC 2, fades in, plays the EHZ music, and holds the camera at max X $2AB0, Y $380.
    - Both hops are computed arcs (as `Mario_TornadoHopArc`). The hop on ends on the button's top, landed by its SolidObject. The hop off ends on the floor under Peach, and Mario's own movement takes over a frame early with no x speed: a real SMB1 jump kept his walking speed and slid him past her.
  - **Art:** `python -I tools/postcredits_art.py` generates `PostCredits_Mario/Luigi.bin` (99 text tiles plus 6 Peach tiles), `PostCreditsText.asm`, `Peach.asm` and `mario_postcredits_art.asm`. The text is in its docstring constants.
    - **Text:** sprites, not plane tiles (the EHZ palm trunks are plane A up to the top of the screen). SMB1's font from `bg.chr` in white ($6) with a 1-px black ($1) drop shadow: white alone vanished over the clouds (user).
    - **Peach:** EnemyGraphicsTable $9C, castle sprite palette 2 → $C/$6/$F, bottom-right tile h-flipped as SMB1's ESRtnr does.
    - **VRAM:** $3D2 (EHZ badnik art; a `fatal` guards the starpost tiles at $47C).
  - **Music:** `victory_music()` in `nes_sfx2smps.py` (shares `looping_music` with the castle theme, whose output is unchanged) → `sound/music/Mario Victory.asm`. It's a 384-frame loop in slot **$9D** (`MusID_MarioVictory` = `MusID_Emerald`: Mario never enters the Special Stage), in the first music bank, tempo-table entry $FF.
    - **Fixes after the user's first listen ("balancing off, instruments wrong, melody not flowing"):**
      - **Envelope start:** `looping_music` had the castle's note envelope start (8) hard-coded. Event music gets **$28** from `LoadControlRegs` (`env_start`), so every note was an 8-frame blip instead of SMB1's swell to volume 6 and hold.
      - **Triangle on FM1:** it was on PSG3, a square at fixed attenuation 2: buzzy and louder than the volume-6 melody. Now algorithm 7 with all four operators as carriers at MUL 1/3/5/7, TL = 40·log10(n)/0.75: a triangle's 1/n² harmonics.
      - **Balance knob:** `VICTORY_TRI_FM_VOLUME` ($1C) sets the bass against the melody.
      - FM pitch is the driver's own table (`fm_note`) plus detune, so the 98 Hz note no longer folds up an octave.
    - Squares stay on PSG1/2: SMB1 plays them at 50% duty, the PSG's own wave.
    - `triangle_note`'s octave fold is still there for PSG songs; the death and castle songs never hit it.
    - Not yet heard by the user after the fixes.
  - **Ground fix (user report):** the credits-demo path has no title card, and the title card is what draws plane A (`DrawLevelTitleCard`), so the ground only appeared as the camera scrolled. `PC_DrawFG` (director init) draws plane A with `DrawInitialBG`'s loop on the foreground camera and layout.
  - **Verified:** `test_postcredits.py` (mario and luigi) passes. It goes through level select → CREDITS, skips the cutscene (`Credits_Trigger`) and the slides. Screenshots: `tools/out/postcredits/scene_*.png`. Phase 2, 5 and Bowser tests pass; flag=0 is bit-perfect.
- [x] Phase 8: Full playthrough (done by the user, 2026-10-12): the game can be finished. Some spots need the hold-C air swim, which is intended: the level design stays unchanged.
- [ ] Phase 9: Hard mode (see "Hard mode" below; started 2026-10-12)
  - **Difficulty select (H31, done):** the options menu's first box is now "DIFFICULTY" (the character is picked on the title, H29).
    - Choices: **HYBRID MODE** (the normal/easy rules) and **MARIO MODE** (hard mode). They're padded with spaces to centre them under the header's text: `" HYBRID MODE   "` (11 letters, so it can't be exactly centred) and `"  MARIO MODE   "`.
    - Variable: `Difficulty_option` (word, $FFFFFF76, in a previously unused block of s2.constants.asm, `if marioMode`). Values `Difficulty_Hybrid` = 0 and `Difficulty_Mario` = 1 (mario.constants.asm). It persists across lives, acts and returns to the title, and defaults to Hybrid at power-on. Nothing reads it yet.
    - Size-neutral: the header text is the same length ("*  DIFFICULTY   *"), and the two choice strings replace TextOptScr_MarioAlone/LuigiAlone.
    - Test harness: `boot_to_level(emu, option, difficulty=None)` now picks the character on the title menu. With `difficulty` it first sets the box in options, then presses START on the sound test to go back to the title.
    - `test_phase2.py` checks the box. Phase 2 and Luigi pass, and flag=0 is bit-perfect.
  - **Middle box: LEVEL SELECT (H33, done 2026-10-12, user request):** box 1 (was VS MODE ITEMS) reads "* LEVEL SELECT  *" and picks **MARIO GAME / LUIGI GAME** (written `"  MARIO GAME   "`, centred under the header's words) (`Player_option`, the same variable the title's MARIO GAME / LUIGI GAME sets).
    - **START on it** opens the level select (`GameModeID_LevelSelect`, with `Two_player_mode`/`_copy` cleared, as the title's level select cheat does). This replaces the 2P VS start, padded with nops to the same 34 bytes. The text strings are replaced in place at the same lengths. `Two_player_items` is no longer touched.
    - 2P VS is now unreachable from the menus.
    - **SPECIAL STAGE → CREDITS (H34, user request, 2026-10-12):** the level select's Special Stage entry reads CREDITS, shows the Death Egg icon (`LevSel_IconTable` $14: $C → $B), and starts the ending sequence. Mode 3 never enters the Special Stage.
      - **Text:** `tools/levsel_art.py` decodes S2's `Level Select.eni` and writes CREDITS over row 15, columns 22–35 (it asserts the old text is SPECIAL STAGE). It re-encodes with `ending_art.enigma_encode` to `mappings/misc/mario/Level Select.eni`, which is `MapEng_MarioLevSel` (mario_polish.asm), swapped into `MenuScreen_LevelSelect`'s `lea`.
      - **Starting the ending:** `Mario_LevSelCredits` replaces `move.b #GameModeID_SpecialStage,(Game_Mode).w`.
        - **Why DEZ must be loaded:** the ending's falling scene scrolls plane B with `LoadTilesAsYouMove`, using whatever DEZ left behind: tiles in VRAM, blocks/chunks/layout in RAM, and the background at $E000. From a menu, that was garbage.
        - **The load:** fade to black, then `ClearScreen` (needed: `DrawInitialBG` only draws around the camera, so the menu's "SONIC" background showed through as specks). Then Current_ZoneAndAct = DEZ1, and Level's own order: `LevelSizeLoad`, `DeformBgLayer`, `LoadZoneTiles`, `loadZoneBlockMaps`, `LoadAnimatedBlocks`, `DrawInitialBG`.
        - **Afterwards:** `ClearPLC` (DEZ's PLC 2) and a black `Normal_palette` (`loadZoneBlockMaps` loads DEZ's palette straight to the screen), then Game_Mode = EndingSequence.
        - **On return:** the S2 code after the hook sets lives, score and `Player_mode` (`Mario_SetPlayerMode`). EndingSequence sets DEZ again itself.
      - **Verified:**
        - Compared with an ending started from inside a loaded DEZ: photos and Tornado identical frame for frame, the fall shows DEZ's starfield over the clouds.
        - `tools/test_options.py` (14/14; `credits_NNNN.png` at 60/1500/2250/3000 frames) passes, and flag=0 is bit-perfect.
    - **Test harness note:** `emu.screenshot` captures the screen region of the BlastEm window, so another window on top of it ends up in the PNG.
  - **Hard-mode rules (built 2026-10-12; scripted test passes, the user's hard-mode playthrough is still to do):**
    - **Flag:** `Mario_HardMode` (Mario RAM, $FF in MARIO MODE), set by `ObjMario_Init` from `Difficulty_option`. Each rule branches on it around the normal-mode code. S2 hooks read `Difficulty_option` directly.
    - **Rules 1–4, hurt (`Mario_HurtHard`, mario_touch.asm):**
      - A shield absorbs the hit first: the shield is gone, S2's hurt sound plays, and Mario gets the injured invincibility, keeping his size and rings.
      - Otherwise, small Mario dies whatever his ring count.
      - Super or fiery Mario loses his rings: `Ring_count` = 0, HUD updated, `Extra_life_flags` cleared, no LostRings object. Then `ForceInjury` runs.
      - No knockback: Mario stays in routine 2. `PlayerInjuryBlink` now returns "halted" until TimerControl $F0 and while `PlayerChangeSizeFlag` is set, so `ObjMario_Frozen` holds him (even in mid-air) until the shrink ends. Then he has control while the world stays paused until $C8. In normal mode that return value isn't used (ObjMario_Hurt freezes on the task itself).
      - Invincibility: `invulnerable_time` = `Mario_InjuryFrames` (8×21 = 168). `Mario_Display` (replaces `Sonic_Display` in Control/Frozen) doesn't count it down while TimerControl runs, and skips drawing on odd frames (SMB1 `PlayerGfxHandler`). Normal mode → `Sonic_Display`.
    - **Rule 5:** `ChkInj` → hurt in hard mode; the "12 px above" stomp is skipped.
    - **Rule 6, death:** in `Mario_DeathSound` (the `KillCharacter` hook, all deaths), after the death music:
      - Player_X_Speed 0 and the shrink flag cleared.
      - The character's own falling force (`Mario_InitFallForce`; a swim force left in VerticalForce would float for ages).
      - `Mario_SetYSpeed($FC00)`, Player_State 1, task `MarioTask_Death` ($0B), TimerControl $FF.

      `ObjMario_DeadHard` ticks TimerControl, holds him until it drops below $F0 (15 frames), then runs `ObjectMove` + `MovePlayerVertically`. S2 already freezes the other objects while the player is dead.
    - **Rule 7 (H32):** `Mario_MonitorContents` replaces `Obj26_Init`'s `move.b subtype(a0),anim(a0)`. In hard mode, anim 5 (shoes) becomes 4 (super ring), so both the icon and the contents change.
    - **Rule 8:** `Mario_TouchBoss` in hard mode needs `y_vel` > 0 as well as airborne.
    - **Verified:** `python -I tools/test_phase9.py`, 25/25 (EHZ1, booted through DIFFICULTY = MARIO MODE):
      - Shoes monitor → ring icon and +10 rings.
      - A big hit: rings 0, no LostRings, routine 2 throughout, halted until the shrink ends, invincibility 167/168 left at the task's end, then 1 per frame, blinking 1,0,1,0 (tiles $780-$79A in `Sprite_Table`), drawn every frame afterwards.
      - A shield absorbs a hit while small.
      - A 12-px-above touch hurts.
      - Falling stomps.
      - Rising into a boss hurts; falling onto it hits it.
      - Small with 25 rings (in the post-injury window) dies: frozen 15 frames, y_vel −$500 then +$8C per frame, x_vel 0.
      - Hard mode survives the restart; small with 5 rings dies.
    - Normal mode unchanged: Phases 4, 5, 6, star, power pause and Bowser all pass, and flag=0 is bit-perfect.
    - **Still to do:** the user's hard-mode playthrough of every zone and boss.
    - **Test notes:** a shield makes a cheap "was he hurt?" detector. While the injury task runs the world is paused, so objects spawned then never initialise: spawn them first.

**Note:** The user handles version control with GitHub Desktop. Don't run git commands or bring up backups.

## Context
The workspace has a Sonic 2 disassembly (`s2disasm-master`, AS assembler, `build.bat` → `s2built.bin`) and an SMB1 disassembly (`smb1-disasm-master`, asm6f). The goal is to add Mario to Sonic 2's own zones as a playable character, the way Knuckles was added to Sonic 2. His movement code is translated from SMB1's 6502 into 68k and kept as close to the original as possible, with changes only where Sonic 2's terrain collision, objects and gimmicks require them.

User decisions:
- **Scope:** Mario is a playable character in Sonic 2's zones. This is not a port of the whole SMB1 game.
- **Physics: hybrid.** Acceleration, top speed, friction, jump arc and gravity all use SMB1's numbers. Those numbers drive Sonic 2's `inertia`/`angle` system, so Mario can walk slopes and run loops. After playtesting, the user chose to buff them where they are handed to S2. Current values: **1.5× horizontal speed** (run $3C0, walk $240) and **1.25× jump speed and gravity** (SMB1's arc, a bit higher). See Phase 3 status.
- **Assets:** SMB1 sprites are converted from the NES CHR data. Sound effects are Sonic 2's existing ones. Imported Mario sprites should use the closest available palette data from Sonic 2 as to avoid graphics issues with original assets.
- **Power-ups come from rings:**
  - ≥10 rings makes him Super (big) Mario.
  - ≥30 rings makes him Fire Mario, who can throw fireballs.
  - Getting hit loses all rings and turns him back into small Mario.
  - Getting hit with 0 rings kills him.

## Approach overview
- **Build flag.** Add `marioMode = 0/1` in `s2.asm` next to `fixBugs` (line ~27). Every hook goes inside `if marioMode`. With the flag at 0, `chkbitperfect.bat` must still pass after every phase.
- **Mario is a new object.** `ObjMario` takes free ID **$D0** and `ObjMarioFireball` takes **$D1`; both replace `ObjNull` entries in `Obj_Index` (s2.asm ~30131). The object is modelled on `Obj01` (Sonic, s2.asm 36156) and `Obj02` (Tails, 38876), which already shows how to build a second full player object.
- **New player mode.** `Player_mode = 3` ("MARIO ALONE"). Mario is spawned by `InitPlayers_Alone` (s2.asm:5201).
- **Mario's own state lives in RAM, not in his object slot.** The player's object slot has no free bytes, so the SMB1 variables go in the `ds.b $C0` block at s2.constants.asm:1209. The block stays the same size so no other RAM addresses shift.
- **Calls into Sonic 2 code.** Mario's code sits at the end of the ROM, too far from most S2 routines for short branches, so every call uses `jsr/jmp (X).l`.

## New files (`s2disasm-master/mario/`)
| File | Contents |
|---|---|
| `mario.constants.asm` | SMB1-named RAM: `Player_State`, `PlayerSize`, `PlayerStatus`, `VerticalForce(Down)`, `FrictionAdderLow/High`, `MaximumLeft/RightSpeed`, `RunningTimer`, `RunningSpeed`, `JumpSwimTimer`, `JumpOrigin_Y`, `DiffToHaltJump`, `Player_X_MoveForce`, `PlayerChangeSizeFlag`, `PlayerAnimCtrl/Timer`, `CrouchingFlag`, `SwimmingFlag`, `FireballCounter`, `A_B_Buttons`, `PreviousA_B_Buttons`, `Left_Right_Buttons`, `Up_Down_Buttons`, and so on |
| `mario.asm` | Master include, placed before the end of ROM (s2.asm ~91967). Holds the ObjMario routine table, laid out exactly like `Obj01_Index`: 0 Init, 2 Control, 4 Hurt, 6 Dead, 8 Gone, $A Respawn. External code writes these routine numbers directly, so the layout must match. |
| `mario_physics.asm` | Line-for-line translations of `smb1/engine/game-mode/player-movement.asm` (`PlayerMovementSubs`, `OnGroundStateSub`, `JumpSwimSub`, `FallingSub`, `PlayerPhysicsSub`, `CheckForJumping`, `ProcJumping`, `X_Physics`, `GetPlayerAnimSpeed`, `ImposeFriction`), plus `MovePlayerVertically` and `ImposeGravity` from main.asm:4580/4704. The data tables are copied unchanged. Labels keep their SMB1 names, and each block has a comment such as `; SMB1 player-movement.asm:NNN` naming its source. |
| `mario_glue.asm` | Code that connects the SMB1 routines to Sonic 2: `Mario_Move`, `Mario_Air`, `Mario_ResetOnFloor_Part2`, `Mario_Water`, `Mario_Display`, `Mario_UpdatePower`, `PlayerChangeSize`/`HandleChangeSize` (from main.asm:12066), and the launch-state handling |
| `mario_touch.asm` | `Mario_TouchEnemy` (translated from `HandlePECollisions`/`ChkForPlayerInjury`/`EnemyStomped`, main.asm 8545–8714), `Mario_TouchMonitor`, `Mario_SolidMonitor`, `Mario_HurtHook` |
| `mario_anim.asm` | `Mario_Animate` (translated from `ProcessPlayerAction`, main.asm:11955), `MarioAniData`, `LoadMarioDynPLC` (copied from `LoadSonicDynPLC`, s2.asm:38829) |
| `mario_fireball.asm` | Obj$D1, translated from `ProcFireball_Bubble`/`FireballObjCore`/`FireballBGCollision` (main.asm ~3182–3290, 10026) |
| `mario_polish.asm` | Phase 7 S2 hooks H11, H13–H16 and the "MARIO GOT" results mappings |
| `mario_art.asm` | Includes the art, mappings and DPLC files, and checks at assembly time that the art doesn't cross a 128 KB boundary (it is copied to VRAM by DMA) |

Generated assets:
- `art/uncompressed/Mario.bin`, `MarioFire.bin`, `MarioFireball.bin`, `MarioLife.bin`
- `mappings/sprite/Mario.asm`
- `mappings/spriteDPLC/Mario.asm`

These use `SonicMappingsVer=2`, see `mappings/MapMacros.asm`. The converter script, `so-retro/tools/chr2md.py`, is run by hand and is not part of the build.

## Unit conversion (exact)
- **Horizontal speed.** SMB1's `X_Speed` is signed 4.4 fixed point. S2 speed is `inertia`/`x_vel = X_Speed << 4`.
  - Walk top speed: $18 → $180.
  - Run top speed: $28 → $280.
  - Water top speed: $10 → $100.
- **Fractional speed.** Friction and acceleration operate on a 16-bit `X_Speed:Player_X_MoveForce` value, so speed gained from slopes or springs doesn't wrap. Each frame:
  1. Load from `inertia`.
  2. Run the SMB1 code.
  3. Write back to `inertia`.

  SMB1 shares `X_MoveForce` between the subpixel position and the friction value. Here they are separate, which is deliberate and will be documented.
- **Speed thresholds.** The original SMB1 constants are kept, and compared against `|inertia|>>4`.
- **Vertical speed.** SMB1's `Y_Speed:Y_MoveForce` is already 8.8 fixed point, the same format as `y_vel`.
  - Jump speed $FC:00 → −$400.
  - Gravity is `add.w VerticalForce,y_vel`.
  - Falls are capped at $400 if `y_vel` reaches $480 or more (ImposeGravity).
  - The stomp bounce is `move.b #$FD,y_vel`.
  - The order is move first, then apply gravity, which matches both games.
- **Frame rate.** Both consoles run at 60 Hz, so values map 1:1. On PAL, Mario behaves like Sonic (no compensation).

## ObjMario control flow
- **Init.** Copy `Obj01_Init` with these changes:
  - Mario mappings.
  - Collision size (radii) set from `PlayerSize`.
  - SMB1 variables initialised: `VerticalForceDown=$70`, small Mario.
  - Fireball art copied into Tails' tails VRAM slot at $7B0, which is free because Tails isn't present ($7A0 is used by the SCZ/WFZ Tornado's pilot).
- **Control.** Copy `Obj01_Control`.
  - **Buttons.** Genesis B = SMB1 A (jump; C stopped jumping 2026-10-12 and only holds the air swim); Genesis A = SMB1 B (run/fire). Holding down on the ground cancels left/right, as in SMB1's `PlayerCtrlRoutine`.
  - **MdNormal (on the ground):**
    1. Crouch flag (big Mario only).
    2. `PlayerPhysicsSub` (`CheckForJumping`/`ProcJumping`, then `X_Physics`).
    3. `jsr Sonic_SlopeResist`.
    4. `Mario_Move`: `ImposeFriction` with a **soft cap**. SMB1's top-speed clamp only applies if Mario was at or under max speed before this frame. Speed above max (from slopes or springs) is kept and only slowed while no direction, or the opposite direction, is held. This is what lets Mario get through loops.
    5. `jmp Obj01_Traction` (s2.asm:36805), which splits `inertia` into `x_vel`/`y_vel` along the ground angle.
    6. `Sonic_LevelBound`, `ObjectMove`, `AnglePos`, `Sonic_SlopeRepel`.
  - **Jumping.** The jump strength comes from SMB1's speed-indexed tables and is applied perpendicular to the ground, the way `Sonic_Jump` does it. It sets `Player_State=1` and `JumpOrigin_Y`. It does **not** set the rolling flag, because Mario's jump is not a spin attack.
  - **MdAir (in the air):**
    1. `JumpSwimSub`/`FallingSub` choose `VerticalForce` (variable jump height).
    2. Left/right input in the air adjusts speed SMB1-style.
    3. `Sonic_LevelBound`, `ObjectMove`, then the SMB1 gravity add and cap.
    4. `Sonic_JumpAngle`, `Sonic_DoLevelCollision`.
  - **Launch state.** When Mario is airborne but not from his own jump and is still rising (springs, launchers, hurt knockback), he uses S2 gravity ($38) until the top of the arc, then SMB1 gravity. This keeps springs reaching their intended ledges.
  - **MdRoll.** Used only for rolls forced by the level (CPZ tubes, CNZ pinball); reuses `Sonic_RollRepel` and `Sonic_RollSpeed`. Mario never starts a roll himself.
  - **After the mode routine, each frame:**
    - `Mario_Display` (speed shoes double the SMB1 top speeds and friction values).
    - `Sonic_RecordPos`.
    - `Mario_Water` (sets `SwimmingFlag`, which switches to SMB1 swim physics).
    - `Mario_UpdatePower`, `Mario_Animate`, `TouchResponse`, `LoadMarioDynPLC`.
- **Hurt/Dead/Gone/Respawn.** Copy `Obj01_Hurt` through `Obj01_Respawning` (s2.asm 38164–38378). Sonic 2's knockback is kept.

## Power state
`Mario_UpdatePower` picks a target state: 2 (fire) at ≥30 rings, 1 (big) at ≥10, otherwise 0.
- **Small → big.** Plays the SMB1 grow animation (`HandleChangeSize`). Only Mario freezes while it plays. His feet stay on the ground (`y_pos -= Δradius`).
- **Big → fire.** Switches to the fire-colour art bank (DPLC) and flickers.
- **Collision size:**
  - Small: y_radius **$0E**, x_radius 7. It was $08, but S2's flat-ground wall sensor sits at y_pos+8 (`CalcRoomInFront`), so $08 would read floor bumps as walls. $0E matches rolling Sonic.
  - Big: y_radius $10, x_radius 7.
  - Set by `Mario_BigYRadius` and `Mario_SmallYRadius` in `mario.constants.asm`. The mappings anchor the feet with these symbols, so retuning them needs no art regeneration.
  - Crouching uses the small values.
  - While growing or shrinking, keep the big radius and use the "tall" small frames (`MarioFrame_TallSmallBase`). Switch radius once the change finishes.
- **Hurt hook** in `HurtCharacter` (s2.asm ~85604):
  - Shield: Sonic 2 behaviour (the shield absorbs the hit).
  - 0 rings: `KillCharacter`.
  - Otherwise: the S2 ring scatter (sets rings to 0), then `PlayerStatus=0` and the shrink animation.
- Rings reset every act, so Mario starts each act small.

## Sonic 2 hooks (all inside `if marioMode`)
| # | Location (s2.asm) | Change |
|---|---|---|
| H1 | Obj_Index ~30131 | `ObjPtr_Mario` ($D0), `ObjPtr_MarioFireball` ($D1) |
| H2 | `InitPlayers_Alone` 5201 | Mode 3 → spawn ObjMario in the MainCharacter slot, plus the dust object (Obj08) |
| H3 | `OptionScreen_Choices` 12250 and the text tables ~12387 | Increase the option maximum to 4 and add `"MARIO ALONE"` |
| H4 | `Sonic_ResetOnFloor_Part2` 38131 (ObjID check) | If the object is ObjMario → `Mario_ResetOnFloor_Part2`. This one check covers landing, `HurtCharacter`, `KillCharacter` and `SolidObject` landings. |
| H5/H6 | Duck checks in `TouchResponse` 85191 and `Touch_Boss` 85334 | Not needed (Phase 5): they test mapping frame $4D, which Mario doesn't have, and his crouch already shrinks his collision height |
| H7 | `Touch_Monitor` 85439 | Mario breaks a monitor by hitting it from below or stomping it from above, not from the side |
| H8 | `Touch_Enemy` 85479 | Invincible → kill. Boss → any airborne hit counts (user decision 2026-10-09; in hard mode, Phase 9, only while falling). Badnik → stomp if falling or more than 12 px above it, otherwise Mario is hurt. A stomp gives points and an explosion, then bounces Mario with `y_vel.b=$FD`. |
| H9 | `HurtCharacter` ~85612 | The power-state logic above |
| H10 | `SolidObject_Monitor` ~25592 | Monitors are not solid while Mario is stomping or bumping them |
| H11 | Starpost Obj79 ~44665 | Done (Phase 7): never spawn the Special Stage stars in mode 3. The six Special-Stage `Player_mode` checks (6626, 6772, 9533, 28333, 71695, 72309) can then never be reached. |
| H12 | `Debug_ExitDebugMode` ~88796 | Restore Mario's mappings, art and collision size |
| H13 | `ObjMario_Init` (no S2 change) | Done (Phase 7): DMA `MarioLife.bin` over the life counter (the title screen's PLC loaded Sonic's; mode 3 loads no other) |
| H14 | ObjB2 Tornado ~79214 | Done (Phase 7): use Mario's y_radius instead of the hardcoded $13 |
| H15 | `ScrollVerti` rolling offset | Done (Phase 7): camera follows Mario's feet − $13 |
| H16 | Obj0D signpost; Obj3A results name | Done (Phase 7): Mario's face panel; "MARIO GOT THROUGH" |
| H17 | `Level_MainLoop` (`jsr RunObjects`, `bsr OscillateNumDo`/`ChangeRingFrame`), `Hud_ChkTime` | Done (Phase 5): world pause during Mario's power tasks; size-neutral hooks |
| H19 | Obj24 bubble player check (`loc_1FB0C`) | Done (Phase 7): Mario doesn't inhale bubbles; size-neutral |
| H20 | ObjB2 WFZ end cutscene: `ObjB2_Waiting_animation`, `ObjB2_Landed_on_plane`, `ObjB2_Jump_to_plane` | Done (Phase 7): Mario's own standing frame; a computed hop onto the Tornado; size-neutral |
| H18 | `PalCycle_SuperSonic` first 6 bytes | Done: star flash (`Mario_PalCycleStar`, `mario_anim.asm`); size-neutral; Super Sonic unchanged |
| H21 | `Level_SetPlayerMode`, level select start: `move.w (Player_option).w,(Player_mode).w` | Done (Phase 7.6): `Mario_SetPlayerMode`, always mode 3; options menu lists MARIO/LUIGI only; size-neutral |
| H22 | `PalLoad_Now/_ForFade/_Water_Now/_Water_ForFade` first `lea (PalPointers).l,a1` | Done (Phase 7.6): `Mario_PalPointers`, Luigi's green in line 0 entry $2; size-neutral |
| H23 | Obj2F (HTZ smashable ground) main-character path $E checks | Done (Phase 7.7): `Mario_SmashGroundPath`, Mario's stomp breaks it on any path; size-neutral |
| H24 | Title screen setup: `lea (off_B2B0).l,a1` (intro text) | Done (Phase 7.8): `Mario_IntroText`, "MARIO 'JUMPMAN' MARIO AND LUIGI 'GREEN' MARIO IN"; size-neutral |
| H26 | Ending art: loc_A256 photo load; `lea`s of `ArtNem_EndingFinalTornado`/`ArtNem_EndingPics`/`ArtNem_EndingSonic`/`MapEng_EndingTailsPlane`; `ObjCF_MapUnc_ADA2` in ObjCC/ObjCE; `off_133A4/off_133B0` palette pointer | Done (Phase 7.8): art from `ending_art/*.aseprite` via `tools/ending_art.py`; `Mario_EndingPhoto` loads each photo's own art and palette; size-neutral |
| H27 | Title setup: the two ArtNem_Title/TitleSprites NemDec loads, `MapEng_TitleLogo` + its base, Obj0E mappings (Obj0E_Init, TitleScreen_InitSprite), `Pal_Title`/`Pal_133EC`/`Pal_1342C` files | Done (Phase 7.8): title art from `title_art/*.aseprite` via `tools/title_art.py`; `Mario_TitleLoadArt`; size-neutral |
| H28 | Obj0F_Init `move.w #spriteScreenPositionYCentered(92),y_pixel(a0)` | Done (Phase 7.8): title menu 8 px lower (100) to make room for the subtitle; size-neutral |
| H29 | Title start: `move.b (Title_screen_option).w,d0 / bne.s TitleScreen_CheckIfChose2P`; Obj0F_Init mappings | Done (Phase 7.8): MARIO GAME / LUIGI GAME start a 1-player game as that character (`Mario_TitleChoice`, `MapUnc_MarioTitleMenu`); size-neutral |
| H30 | Title loop `tst.w (Demo_Time_left).w / beq.w TitleScreen_Demo` | Done (Phase 7.8, user request): 4 nops, no demos (they played Sonic and Tails); the title waits. Verified: still on the title 2400 frames in, Start works; size-neutral |
| H31 | Options box 0: `OptionScreen_Choices` entry, `off_92D2`/`off_92DE`, `TextOptScr_PlayerSelect` text | Done (Phase 9): DIFFICULTY box, HYBRID MODE / MARIO MODE → `Difficulty_option`; size-neutral |
| H33 | Options box 1: `OptionScreen_Choices` entry, `TextOptScr_VsModeItems/AllKindsItems/TeleportOnly` text, `OptionScreen_Select_Not1P` 2P start | Done (Phase 9): LEVEL SELECT box, MARIO/LUIGI → `Player_option`, START → level select; size-neutral |
| H34 | Level select: `move.b #GameModeID_SpecialStage,(Game_Mode).w`, `lea (MapEng_LevSel).l`, `LevSel_IconTable` entry $14 | Done (Phase 9): CREDITS entry (`tools/levsel_art.py`), Death Egg icon; `Mario_LevSelCredits` loads DEZ's level data, then the ending; size-neutral |
| H32 | `Obj26_Init` `move.b subtype(a0),anim(a0)` | Done (Phase 9): `Mario_MonitorContents`, hard mode: speed shoes monitors are 10-ring monitors; size-neutral |
| H35 | `EndgameCredits` `move.b #GameModeID_SegaScreen,(Game_Mode).w` | Done (Phase 7.9): `Mario_PostCreditsStart`, the post-credits scene in EHZ2; size-neutral |
| H36 | Obj3E `loc_3F2FC` `move.b #1,anim(a0)` | Done (Phase 7.9): `Mario_CapsuleOpen`, Peach instead of animals in the scene; size-neutral |
| H37 | Obj7F/Obj80/ObjD9 release `move.w #-$300/-$380,y_vel(a1)`; their button checks and ObjC1's | Done (Phase 7.7): `Mario_HangRelease300/380`, letting go of a hang bar is Mario's own jump; B only; size-neutral |
| H38 | `zPlaySegaSound` (s2.sounddriver.asm); the `Snd_Sega` block before `MusicPoint2` | Done (2026-10-12, user request; from Sonic Retro's S1 "Fix the SEGA Sound" guide, done the S2 way): no size limit. With `marioMode`, `Snd_Sega` is at the end of the ROM and the Z80 loop switches to the next bank when its pointer wraps (bank number self-modified at `.bank+1`); both half-loops 70+13n cycles (`pcmLoopCounterBase(rate,166/2)`). Replaces the original loop rather than adding one: the Z80 driver had 0 bytes to spare. `MusicPoint2` doesn't move (`startBank` aligns). Verified in BlastEm: bank $23→$24 ~1.7 s in, title follows. The user's new SEGA.wav is $7A28 bytes, so a flag=0 build fails `Size_of_SEGA_sound` until the original wav is restored for `chkbitperfect` |
| H25 | Ending: loc_A2E0 `move.b #ObjID_Sonic,id(a1)`; loc_A53A `move.l #…,mapping_frame(a1)` | Done (Phase 7.8): `Mario_EndingLoad`/`ObjMario_Ending`/`Mario_EndingStand`, Mario/Luigi puppet (killed frame falling, small standing on the plane); size-neutral |

Effect of the new mode on existing checks:
- `cmpi.w #2,Player_mode` checks ("Tails alone") treat mode 3 like Sonic. That is correct for the camera, monitors, platforms and the SCZ Tornado.
- `tst.w` checks ("one player only") are also correct for Mario.
- 2P mode and demos force mode 0, so Mario never appears there.

Remaining audit greps: `#$13,y_radius`, `AniIDSonAni_Roll`, `status.player.rolling` (breakables at 45449, 46891, 82536), `Sonic_top_speed`, `MapUnc_Sonic`.

`MarioAniData` must have an entry for every one of the 33 `AniIDSonAni_*` IDs, because other objects write them into `anim` directly:
- Spring → jump frame.
- Hang → climb frame.
- Death/Drown → killed frame.
- Forced roll → jump frame, rotated.

## Fireballs (Obj$D1)
- **Spawning.** Fire Mario throws one when Genesis A is newly pressed, he isn't crouching, and fewer than 2 fireballs exist. It starts at x_vel ±$400, y_vel +$400, with `FireballThrowingTimer` set and an S2 fire sound.
- **Each frame:**
  - `ObjectMove`, then gravity $50, capped at $300.
  - `ObjCheckFloorDist`: bounce at −$300. If it is already in a bounce, or is moving up, it explodes.
  - Hitting a wall or leaving the screen: explode or delete.
- **Hitting enemies.** It uses the `Touch_Sizes` box test against the dynamic objects.
  - Badnik class: kill it with the points and explosion.
  - Boss: decrement `boss_hitcount2`.
  - Hurtful class: the fireball explodes.

## Art pipeline (`tools/chr2md.py`, Python 3)
Run it with `python -I tools/chr2md.py` from `so-retro`. It regenerates every Mario asset; never hand-edit the outputs. Afterwards, build with `marioMode = 1` and run `tools/verify_mario_art.py` (usage is in its docstring). The verifier decodes every frame out of the ROM and compares it pixel-for-pixel with SMB1's own sprite composition.
- **Colours (the user's rule: use the closest existing S2 colours, no palette edits).**
  - Each NES colour comes from SMB1's `PlayerColors` (colors.asm) or `GroundPaletteData` sprite palette 2. It maps to the nearest colour in palette line 0 (`SonicAndTails.bin`), using RGB from the FCEUX NES palette.
  - Result:

    | Sprite palette | Colour 1 | Colour 2 | Colour 3 |
    |---|---|---|---|
    | Normal | $C | $F | **$3** (user override, see below) |
    | Fiery | $A | $F | $C |
    | Fireball | $C | $6 | $F |

  - **User override (`REMAP_OVERRIDES` in chr2md.py):** Mario's olive `$18` (overalls, hair, shoes) maps to **$3**, a neutral blue ($0C42) from Sonic's palette, instead of the nearest colour ($B brown). The user asked for this.
  - The script fails if two colours in one sprite palette collapse onto the same index. Underwater palettes work automatically.
- **Frames.** Built from `PlayerGraphicsTable` (parsed from main.asm), including the `ChkForPlayerAttrib` mirroring:
  - $50, $B8 and $C0 mirror the 4th row only.
  - **$C8 (big stand) falls through `cmp #$c8 / bne ExPlyrAt` into `KilledAtt`**, so its 3rd *and* 4th rows are mirrored, the same as the killed frame ($B0). The user caught this one visually; the original reading only mirrored the 4th row. `mario/mario_frames.asm` holds the frame IDs:

  | Frames | Contents |
  |---|---|
  | 0 | blank |
  | 1–26 | Table rows: `mapping_frame = PlayerGfxOffset/8 + MarioFrame_GfxBase`. Big rows are anchored to the big radius, small rows to the small radius. |
  | 27–38 | Small rows in the 32 px box, anchored to the big radius (`MarioFrame_TallSmallBase`), used while growing or shrinking |
  | 39–43 | Swim-kick variants (`SwimKickTileNum`) |
  | 44–51 | 90° rotations (feet toward +x) of walk 1–3 and stand, big and small. 180° and 270° come from H/V flips (`MAnim_Orient`). |
  | 52–56 | 90° rotations added in Phase 4: big skid, big jump, big crouch, small skid, small jump (`ROTATE_ROWS` is append-only so earlier IDs never move) |

- **Output files:**
  - `art/uncompressed/Mario.bin` and `MarioFire.bin`: 266 tiles each (since Phase 4), same order.
  - `MarioFireball.bin`: 5 tiles.
  - `MarioLife.bin`: 12 tiles in the layout of S2's "Sonic lives counter.nem": the 2×2 face (small standing Mario), then the 4×2 name piece. "MARIO" is in S2's own name font (M from MILES, A from TAILS, I and O from SONIC, R drawn in the same style: `GLYPH_R`); the "×" and digit slots are Sonic's.
  - `MarioSignpost.bin`: 24 tiles, the signpost's frame 0 layout (two 3×4 pieces): Tails' panel border, white interior, Mario's face (top 12 rows of the big standing frame, pixel-doubled).
  - Both decode S2's Nemesis art with `tools/nemesis.py` (a decompressor; S2's build has no Nemesis tools). Previews: `tools/out/mario_life.png`, `mario_signpost.png`.
  - `mappings/sprite/Mario.asm`, `mappings/spriteDPLC/Mario.asm`, `mappings/sprite/MarioFireball.asm`.
  - `tools/out/mario_sheet.png`, the contact sheet. Rows: frames 0–26, frames 27–51, fiery frames 0–26, fireball.
- **ROM placement.** `mario/mario_art.asm` keeps the art inside one 128 KB bank (it currently starts at $100000) and fails the build if the art straddles a boundary. The 2× scale option was dropped.
- **VRAM.** At most 8 tiles per frame (the slot is 32 tiles at $780). The fireball uses Tails' area at $7A0.

## Phases and verification
In every phase:
1. Run `build.bat` with `marioMode=1`.
2. Test in BlastEm or Exodus (Exodus has a VRAM viewer).
3. Run `build.bat` with `marioMode=0`, then `chkbitperfect.bat`.

| Phase | Work | Verify |
|---|---|---|
| 0 | Flag, empty includes, RAM block, Obj_Index slots | flag=0 is bit-perfect; flag=1 boots |
| 1 | chr2md.py and the generated assets | The contact sheet matches the SMB1 frames; the art passes the 128 KB check |
| 2 | Skeleton ObjMario using Sonic's physics; art, DPLC, animation table; H1–H4, H12 | In EHZ1, Mario renders and walks, VRAM has no corrupted tiles, death and respawn work, debug mode works, the options menu has 4 entries |
| 3 | SMB1 physics and hybrid glue, launch state | Log per-frame values for the same inputs in SMB1 1-1 (Mesen, $57/$0705/$9F/$0433) and on flat EHZ ground. They must match: `inertia = X_Speed×$10`, and `y_vel` identical. Then check EHZ slopes and loops, springs reaching their ledges, CPZ tubes, CNZ pinball, pits. |
| 4 | Animation | Walk cadence changes with speed, skid with dust, crouch only when big, rotated sprites on loops, hang bars and bubbles show sensible frames |
| 5 | H5–H10, power state | Stomping works on each badnik; touching from the side or below hurts; spiked badniks always hurt; monitors break from below and above; 10 rings → big, 30 → fire; a hit scatters rings and shrinks Mario; a hit at 0 rings kills him; shield, invincibility and speed shoes work |
| 6 | Fireballs | At most 2 on screen, they bounce on slopes and explode on walls, they kill badniks and damage bosses |
| 7 | Water, H11, H13–H16 | SMB1-style swimming in CPZ2 and ARZ, the drowning countdown, no Special Stage stars, life icon, SCZ/WFZ Tornado |
| 8 | Full playthrough | Every zone and every boss (beaten with stomps and with fireballs); smoke-test the existing character modes; flag=0 still bit-perfect |
| 9 | Hard mode (below) | Normal mode unchanged (its phase tests pass); a hard-mode test for each rule; a hard-mode playthrough of every zone and boss proves it is still beatable; flag=0 still bit-perfect |

## Hard mode (Phase 9)
A second Mario option that trades Sonic 2's safety nets for SMB1's rules. **Guiding principle (user):** hard mode is harder *because the Mario rules are stricter*, not through arbitrary difficulty. Physics, time limit, lives, checkpoints and continues all stay as in normal mode. Normal mode stays exactly as it is.

**Selecting it.** Superseded (2026-10-12): the options menu's DIFFICULTY box sets `Difficulty_option` (`Difficulty_Mario` = hard, "MARIO MODE"). It persists, unlike the Mario RAM block, which `ObjMario_Init` clears. `Player_mode` stays 3 for both difficulties.

**Planned rules** (each one, wherever possible, a branch on `Mario_HardMode` around normal-mode code):

| # | Rule | SMB1 source | Normal mode does instead |
|---|---|---|---|
| 1 | **Small Mario always dies in one hit** (`PlayerStatus` 0), however many rings he has. That includes his 1–9 rings, and the 10+ he can hold while small after a CNZ slot machine took rings from a big Mario or after a hit. A shield still absorbs the hit first. | `ForceInjury`: `PlayerStatus` 0 → `KillPlayer` | rings protect him; only 0 rings kills |
| 2 | A hit while super/fiery shrinks him to small, and his rings are simply **lost** (set to 0, no scatter to re-collect) | no rings in SMB1 | S2 ring scatter |
| 3 | **No knockback.** Getting hurt runs SMB1's `PlayerInjuryBlink`: Mario halts until `TimerControl` $F0, shrinks, then keeps control while blinking | `PlayerInjuryBlink`, `InjuryTimer` | S2 knockback (`ObjMario_Hurt`) |
| 4 | **SMB1 invulnerability time** after a hit: `InjuryTimer` = 8 interval ticks (8 × 21 frames = 168 frames), with SMB1's every-other-frame blink | `ForceInjury`, `PlayerGfxHandler` | S2's $78 (120) frames |
| 5 | **Stomps only while falling.** The "12 px above" rule is dropped: SMB1 skips it for Goombas/Koopas (enemy IDs < Bloober) | `ChkForPlayerInjury` (`ChkInj`) | falling, or 12 px above |
| 6 | **SMB1 death:** everything freezes briefly, then Mario hops up (Y speed $FC) and falls off screen under SMB1 gravity | `KillPlayer`, `PlayerDeath` | S2's death jump (−$700) |
| 7 | **Speed-shoes monitors become 10-ring monitors** (SMB1 has no such item). The shield stays (user decision). Invincibility stays as SMB1's star. | SMB1 item set | S2 monitors as-is |
| 8 | **Bosses are hit only while Mario is airborne and falling** (`y_vel` > 0); any other touch is a hurt check | stomps need downward speed (`ChkForPlayerInjury`) | any airborne hit counts |

**Decided (user, 2026-10-09):**
- **Physics:** the normal tuning stays (1.5× horizontal, 1.25× jump); 1:1 SMB1 physics make S2's levels impossible.
- **Time limit:** S2's 10:00.
- **Shield:** kept. It absorbs one hit, before rule 1.
- **Lives:** the same as normal mode.
- **Bosses:** rule 8 above. Normal mode now counts any airborne hit; this was changed in code from Phase 5's falling-only rule.
- **Checkpoints and continues:** both kept.

**Verify:**
- Run the normal-mode tests unchanged: phases 2–5, plus phases 6–7 once they exist.
- Add `tools/test_phase9.py`:
  - Small Mario dies in one hit with 5 rings and with 25 rings; with a shield he survives (and stays small).
  - Big Mario shrinks and his rings are gone (no `ObjID_LostRings`).
  - No knockback (routine stays 2); 168-frame invulnerability.
  - A rising touch on a badnik hurts even 12 px above it.
  - Rising into a boss hurts; falling onto one hits it.
  - The death arc; shoes monitors give 10 rings.
- Hard-mode playthrough of every zone and boss.
- flag=0 bit-perfect.

## Key risks
- **6502 idioms.**
  - `JumpEngine` tables become `offsetTable` plus `jmp (pc,d1.w)`.
  - The `.db $2c` byte-skip trick becomes an explicit `bra.s`.
  - Signed compare and carry semantics must be translated with care.
  - The frame-by-frame value log in Phase 3 is the check for all of this.
- **SMB1's lower top speed vs loops.** Handled by the soft cap and a tuning constant for slope resistance.
- **SMB1 gravity vs Sonic 2 gimmicks.** Handled by the launch state. Watch the CPZ/MTZ wind tunnels and the CNZ cannons.
- **Code that resets Sonic's collision size or animations.** Found with the audit greps; also covered by `MarioAniData` having every animation ID.
- **ROM size.** Code at the end of the ROM pushes the padded ROM to 2 MB, which is fine. `jsr .l` is used throughout.

## Reference: key locations found during exploration
Line numbers come from the original, unmodified files. They shift as code is added, so re-check them with Grep.

### Build
- **S2:** `s2disasm-master/build.bat` runs `build.lua` (Lua 5.3, AS assembler `asw.exe` + `p2bin`) and produces `s2built.bin`. `chkbitperfect.bat` compares the MD5 against REV00/01/02. Options are at s2.asm lines 20–51 (`gameRevision=1`, `fixBugs=0`, `padToPowerOfTwo=1`).
- **SMB1:** `make` (asm6f), output checked against `smb.sha1`. Only needed for reference and the Mesen comparison.
- **Building from a shell** (both `.bat` files can pause): run from `s2disasm-master`:
  - `build_tools/Lua/lua.exe build.lua`
  - `build_tools/Lua/lua.exe chkbitperfect.lua`

  Assembler errors go to `s2.log`; the listing is `s2.lst`, which is useful for checking label addresses.
- **Nemesis compressor:** none in build_tools, so new art must be uncompressed.

### Sonic 2 (`s2.asm` unless noted; `const` = `s2.constants.asm`)

**Object system**
- Object slot (SST) layout: const 15–76; `object_size=$40`. Every offset $00–$3F is used by the player.
- `MainCharacter=$FFFFB000`, `Sidekick=$B040`.
- Free RAM: the `ds.b $C0` at const 1209 ($FFFFE740). Do NOT use $F100–$F5FF; that becomes `Sprite_Table_Alternate` when `fixBugs=1`.
- `Ring_count` const 1694. `Player_mode`/`Player_option` const 1824–1825.
- `Obj_Index` 29908–30144. Free IDs: $4C–$4F, $62, $D0 (Mario), $D1 (fireball).
- Helpers:

  | Routine | Line |
  |---|---|
  | `RunObjects` | 29805 |
  | `ObjectMove` | 30191 |
  | `ObjectMoveAndFall` | 30164 |
  | `DisplaySprite` | 30358 |
  | `DeleteObject` | 30330 |
  | `AllocateObject` | 33681 |
  | `AnimateSprite` | 30422 |
  | `QueueDMATransfer` | 1713 |

**Main loop**
- `MainGameLoop` 424.
- `Level` 4757; `Level_MainLoop` 5088.
- `Level_SetPlayerMode` 5161.
- `InitPlayers` 5177; `InitPlayers_Alone` 5201.
- `OptionScreen_Choices` 12250; option text tables ~12387.

**Sonic (Obj01)** 36156
- Setup and dispatch: `Obj01_Init` 36179, `Obj01_Control` 36223, modes 36270.
- Mode routines: `MdNormal` 36469, `MdAir` 36494, `MdRoll` 36511, `MdJump` 36530.
- Movement and jumping:

  | Routine | Line |
  |---|---|
  | `Sonic_Move` | 36551 |
  | `Obj01_Traction` (splits inertia into x/y speed along the angle) | 36805 |
  | `Sonic_Jump` | 37345 |
  | `Sonic_JumpHeight` | 37416 |
  | `Sonic_ChgJumpDir` | 37158 |
  | `Sonic_LevelBound` | 37233 |
  | `Sonic_SlopeResist` | 37709 |
  | `Sonic_SlopeRepel` | 37781 |
  | `Sonic_JumpAngle` | 37814 |
  | `Sonic_DoLevelCollision` | 37889 |

- Landing: `Sonic_ResetOnFloor_Part2` 38128, with the `ObjID_Sonic` check at 38131.
- Hurt and death: `Obj01_Hurt` 38164 through `Obj01_Respawning` ~38378.
- Graphics: `Sonic_Animate` 38379, `LoadSonicDynPLC` 38829.
- `Sonic_top_speed`/acceleration/deceleration: const 1551–1553.
- **Tails (Obj02)** 38876 is a full duplicate of the player object; use it as the template.

**Terrain collision**

| Routine | Line |
|---|---|
| `AnglePos` | 43006 |
| `FindFloor` | 43414 (register contract at 43402) |
| `FindWall` | 43666 |
| `CalcRoomInFront` | 43945 |
| `CalcRoomOverHead` | 44009 |
| `Sonic_CheckFloor` | 44036 |
| `ObjCheckFloorDist` | 44210 |
| `CheckRightWallDist` | 44326 |
| `CheckLeftWallDist` | 44517 |
| `Sonic_CheckCeiling` | 44367 |
| Obj03 plane switcher | 45612 |

**Object collision**
- `TouchResponse` 85174. Its duck check (`mapping_frame==$4D`) is at 85191; `Touch_Loop` 85209.
- `Touch_Boss` 85325; `Touch_ChkValue` 85413.
- `Touch_Monitor` 85439 (needs the roll animation); `Touch_Enemy` 85479; `Touch_KillEnemy` 85514; `Touch_ChkHurt` 85579.
- `HurtCharacter` 85604; `KillCharacter` 85671.
- `SolidObject` 35014; its landing code is at ~36023.
- Springs: Obj41 with `loc_189CA` at 33925. Monitors: Obj26 25526 / Obj2E 25731.
- Rings: `Touch_Rings` 31932, `CollectRing` 25023.

**Art, palettes, sound, input**
- `ArtUnc_Sonic` 90473, `MapUnc_Sonic` 90477, `MapRUnc_Sonic` (DPLC) 90479.
- `ArtTile_ArtUnc_Sonic=$780` (const 2615); Tails' art tiles start at $7A0.
- Mappings use `SonicMappingsVer=2` (`mappings/MapMacros.asm`).
- Player palette: `Pal_BGND` 3910 (`art/palettes/SonicAndTails.bin`).
- Sound: `PlaySound` 1535, `PlayMusic` 1520. Sound IDs at const 832–953 (e.g. `SndID_Jump=$A0`).
- Input: `Ctrl_1_Logical`. Button bits: up0 down1 left2 right3 B4 C5 A6 start7.
- Debug: `DebugMode` 88580; `Debug_ExitDebugMode` ~88796.
- Animation IDs (`AniIDSonAni_*`): const 997–1030.

### SMB1 (`smb1-disasm-master`)
- `main.asm` (13k lines) holds most of the engine. RAM map: `constants/constants.asm`.

**Player movement:** `engine/game-mode/player-movement.asm`
- `PlayerMovementSubs` 2, `MoveSubs` 21.
- States: `OnGroundStateSub` 35, `FallingSub` 48, `JumpSwimSub` 55.
- Physics tables 156–182.
- `PlayerPhysicsSub` 184, `CheckForJumping` 208, `ProcJumping` 219, `X_Physics` 289, `GetPlayerAnimSpeed` 353, then `ImposeFriction`.

**Player control:** `engine/game-mode/routine/player-control.asm` (`PlayerCtrlRoutine`).

**main.asm routines**

| Routine | Line |
|---|---|
| `MoveObjectHorizontally` | 4532 |
| `MovePlayerVertically` | 4580 |
| `ImposeGravity` | 4704 |
| `PlayerBGCollision` | 9140 |
| `PlayerEnemyCollision` | 8508 |
| `HandlePECollisions` | 8545–8714 |
| `InjurePlayer` | 8623 |
| Fireballs | ~3182–3290 |
| `FireballBGCollision` | 10026 |
| `PlayerGfxTblOffsets` / `PlayerGraphicsTable` | 11755–11792 |
| `ProcessPlayerAction` | 11955 |
| `HandleChangeSize` | 12066 |
| `ChkForPlayerAttrib` | 12104 |

**Player RAM:**
- `Player_X_Speed $57`, `X_MoveForce $0705`.
- `Player_Y_Speed $9F`, `Y_MoveForce $0433`.
- `VerticalForce $0709`.
- Timers: `$0780+` count down every frame; `$0795+` count down every 21 frames.

**Graphics:** `gfx/sprites.chr` holds the sprite tiles (NES 2bpp).
