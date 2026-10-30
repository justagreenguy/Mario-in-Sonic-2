#!/usr/bin/env python3
"""
chr2md.py - convert SMB1's Mario sprites (NES CHR) into Sonic 2 art/mappings/DPLCs.

Run from anywhere (paths are relative to this script):
    python tools/chr2md.py

Inputs (read-only):
    smb1-disasm-master/gfx/sprites.chr           NES 2bpp sprite pattern table
    smb1-disasm-master/main.asm                  PlayerGraphicsTable (parsed, not hardcoded)
    s2disasm-master/mario/mario.constants.asm    Mario_*YRadius (for the preview only)

Outputs (all regenerated every run; do not hand-edit):
    s2disasm-master/art/uncompressed/Mario.bin          player tiles, normal colours
    s2disasm-master/art/uncompressed/MarioFire.bin      same tiles/order, fiery colours
    s2disasm-master/art/uncompressed/MarioFireball.bin  fireball + explosion tiles
    s2disasm-master/art/uncompressed/MarioLife.bin      HUD life counter, 12 tiles in the layout of
                                                        "Sonic lives counter.nem": 2x2 face (small
                                                        Mario standing) + "MARIO" in S2's name font
    s2disasm-master/art/uncompressed/MarioSignpost.bin  signpost face panel (24 tiles, Obj0D frame 0)
    s2disasm-master/mappings/sprite/Mario.asm           SonicMappingsVer=2
    s2disasm-master/mappings/spriteDPLC/Mario.asm       SonicDplcVer=2
    s2disasm-master/mappings/sprite/MarioFireball.asm
    s2disasm-master/mario/mario_frames.asm              mapping-frame ID equates
    tools/out/mario_sheet.png                           contact sheet for review
    tools/out/mario_life.png, mario_signpost.png        previews of the two above
Also reads S2's Nemesis art (tools/nemesis.py) for the parts of the life counter
and signpost that are kept: the name font, the "x", the signpost border.

Mapping frame layout (see mario_frames.asm):
    0                      blank
    1 .. 26                PlayerGraphicsTable rows 0..25, i.e.
                           mapping_frame = PlayerGfxOffset/8 + MarioFrame_GfxBase.
                           Big rows are anchored to the big radius, small rows to the
                           small radius (feet at y_pos + y_radius).
    27 .. 38               small rows 12..23 anchored to the BIG radius (the original
                           NES 32px box); used while growing/shrinking.
    39 ..                  swim-kick variants (SwimKickTileNum), then 90-degree
                           rotations for loops/walls (feet pointing +x).

Colours: no palette edits. Each NES sprite colour (from SMB1's PlayerColors and
GroundPaletteData sprite palette 2) is mapped to the NEAREST colour already in
S2 palette line 0 (SonicAndTails.bin), using the FCEUX NES palette for RGB.
The script prints the chosen mapping and fails if two colours would merge.
"""

import os
import re
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SMB = os.path.join(ROOT, "smb1-disasm-master")
S2 = os.path.join(ROOT, "s2disasm-master")
OUT = os.path.join(HERE, "out")

BLANK_TILE = 0xFC  # SMB1 uses $FC as the empty sprite tile

# FCEUX default NES palette (RGB), used only to pick the nearest S2 colours.
NES_RGB = [
    0x747474, 0x24188C, 0x0000A8, 0x44009C, 0x8C0074, 0xA80010, 0xA40000, 0x7C0800,
    0x402C00, 0x004400, 0x005000, 0x003C14, 0x183C5C, 0x000000, 0x000000, 0x000000,
    0xBCBCBC, 0x0070EC, 0x2038EC, 0x8000F0, 0xBC00BC, 0xE40058, 0xD82800, 0xC84C0C,
    0x887000, 0x009400, 0x00A800, 0x009038, 0x008088, 0x000000, 0x000000, 0x000000,
    0xFCFCFC, 0x3CBCFC, 0x5C94FC, 0xCC88FC, 0xF478FC, 0xFC74B4, 0xFC7460, 0xFC9838,
    0xF0BC3C, 0x80D010, 0x4CDC48, 0x58F898, 0x00E8D8, 0x787878, 0x000000, 0x000000,
    0xFCFCFC, 0xA8E4FC, 0xC4D4FC, 0xD4C8FC, 0xFCC4FC, 0xFCC4D8, 0xFCBCB0, 0xFCD8A8,
    0xFCE4A0, 0xE0FCA0, 0xA8F0BC, 0xB0FCCC, 0x9CFCF0, 0xC4C4C4, 0x000000, 0x000000,
]


def md_rgb(word):
    """Genesis 0BGR palette word -> (r, g, b), 3 bits per channel scaled to 0..255."""
    return tuple(((word >> s) & 0xE) // 2 * 255 // 7 for s in (0, 4, 8))


def nearest_remap(nes_colours, md_words, label):
    """
    Map NES sprite colours 1..3 onto the nearest S2 palette line 0 entries
    (indices 1..15; 0 stays transparent). Distinct NES colours must stay distinct.
    """
    out = {0: 0}
    for i, nes in enumerate(nes_colours, start=1):
        rgb = ((NES_RGB[nes] >> 16) & 255, (NES_RGB[nes] >> 8) & 255, NES_RGB[nes] & 255)
        best = min(range(1, 16), key=lambda k: sum((a - b) ** 2 for a, b in zip(rgb, md_rgb(md_words[k]))))
        out[i] = best
    used = [out[i] for i in (1, 2, 3)]
    if len(set(used)) != len(set(nes_colours)):
        sys.exit(f"{label}: NES colours {nes_colours} collapse onto S2 indices {used}")
    return out


# Luigi's green ($19) has no near colour in line 0, so entry LUIGI_SLOT (Sonic's
# darkest blue) is made his green while Luigi plays; tools/luigi_palette.py moves
# every other line-0 object's pixels of that colour to LUIGI_SLOT_MERGE (the next
# blue). S2 art decoded here for line-0 pieces gets the same move.
LUIGI_SLOT = 0x2
LUIGI_SLOT_MERGE = 0x3

# User overrides applied on top of the nearest-colour rule: {palette: {NES colour index: S2 index}}.
# Mario's olive $18 (overalls/hair/shoes) -> $3, a neutral blue from Sonic's palette (user's choice).
# Luigi's green $19 -> LUIGI_SLOT (see above).
REMAP_OVERRIDES = {"normal": {3: 0x3}, "luigi": {3: LUIGI_SLOT}}


def get_remaps():
    """
    Colour remaps derived from SMB1's own palette data:
      PlayerColors (engine/screen/routine/colors.asm): Mario and fiery rows
      GroundPaletteData (main.asm): sprite palette 2, used by fireballs
    """
    md = open(os.path.join(S2, "art", "palettes", "SonicAndTails.bin"), "rb").read()[:32]
    md_words = [(md[i * 2] << 8) | md[i * 2 + 1] for i in range(16)]
    colors = open(os.path.join(SMB, "engine", "screen", "routine", "colors.asm")).read().splitlines()
    pc = parse_db_block(colors, "PlayerColors")  # 3 rows of [bg, c1, c2, c3]
    gp = parse_db_block(open(os.path.join(SMB, "main.asm")).read().splitlines(), "GroundPaletteData")
    sprite_pal2 = gp[3 + 4 * 6 + 1:3 + 4 * 6 + 4]  # skip 3-byte VRAM header; BG 0-3, sprite 0-3
    remaps = dict(
        normal=nearest_remap(pc[1:4], md_words, "PlayerColors Mario"),
        luigi=nearest_remap(pc[5:8], md_words, "PlayerColors Luigi"),   # green overridden below
        fiery=nearest_remap(pc[9:12], md_words, "PlayerColors fiery"),
        fireball=nearest_remap(sprite_pal2, md_words, "sprite palette 2"),
    )
    for pal, ov in REMAP_OVERRIDES.items():
        remaps[pal].update(ov)
        used = [remaps[pal][i] for i in (1, 2, 3)]
        if len(set(used)) != 3:
            sys.exit(f"override makes {pal} colours collapse: {used}")
    return remaps

# SMB1 PlayerGraphicsTable row names (row = offset / 8)
ROW_NAMES = [
    "Big_Walk1", "Big_Walk2", "Big_Walk3", "Big_Skid", "Big_Jump",
    "Big_Swim1", "Big_Swim2", "Big_Swim3", "Big_Climb1", "Big_Climb2",
    "Big_Crouch", "Big_Fire",
    "Small_Walk1", "Small_Walk2", "Small_Walk3", "Small_Skid", "Small_Jump",
    "Small_Swim1", "Small_Swim2", "Small_Swim3", "Small_Climb1", "Small_Climb2",
    "Small_Killed",
    "Small_Stand", "Grow_Mid", "Big_Stand",
]
FIRST_SMALL_ROW, LAST_SMALL_ROW = 12, 23
GROW_MID_ROW = 24

# ChkForPlayerAttrib (main.asm:12104) h-flips the right sprite of some rows:
#   $50 (crouch), $B8 (small stand), $C0 (grow mid) branch to C_S_IGAtt:
#       4th row only.
#   $C8 (big stand) is the last compare ("cmp #$c8 / bne ExPlyrAt"), so it does
#       NOT branch - it falls through into KilledAtt: 3rd AND 4th rows.
#   $B0 (killed, drawn by PlayerKilled during GameEngineSubroutine $0B) enters
#       KilledAtt directly: 3rd and 4th rows.
ATTRIB_ROW4 = {0x50, 0xB8, 0xC0}
ATTRIB_ROW3_AND_4 = {0xB0, 0xC8}

# SwimKickTileNum (main.asm:11794): big uses $31; small uses $46 unless the
# tile is already SwimTileRepOffset's value ($48, small swim frame 3).
SWIM_KICK = {5: 0x31, 6: 0x31, 7: 0x31, 17: 0x46, 18: 0x46}

# Rows that get a 90-degree rotated variant for loops/walls: walk cycle +
# standing (Phase 1), then skid, jump and crouch (Phase 4: skidding/crouching on
# walls, leaving a wall mid-air, and the spinning jump frame of forced rolls).
# Appended, so earlier frame IDs never move.
ROTATE_ROWS = [0, 1, 2, 25, 12, 13, 14, 23, 3, 4, 10, 15, 16]

# Phase 6: fireball-throw composites. SMB1's PlayerGfxProcessing draws the
# throw row ($58) over the player: all four rows when he stands still, but
# only the top three when he moves, so the legs (4th row, with its own
# ChkForPlayerAttrib flips) stay those of the current frame. One composite per
# big row Fire Mario can show while throwing (walk 1-3, skid, jump, swim 1-3,
# stand). Appended after the rotations.
FIRE_ROW = 11
THROW_ROWS = [0, 1, 2, 3, 4, 5, 6, 7, 25]


# ---------------------------------------------------------------------------
# Tile helpers. A tile is a tuple of 64 colour indices, row-major.
# ---------------------------------------------------------------------------
def load_chr(path):
    data = open(path, "rb").read()
    if len(data) != 4096:
        sys.exit(f"{path}: expected 4096 bytes, got {len(data)}")
    tiles = []
    for t in range(256):
        b = data[t * 16:(t + 1) * 16]
        px = []
        for y in range(8):
            p0, p1 = b[y], b[y + 8]
            for x in range(8):
                bit = 7 - x
                px.append(((p0 >> bit) & 1) | (((p1 >> bit) & 1) << 1))
        tiles.append(tuple(px))
    return tiles


def hflip(t):
    return tuple(t[y * 8 + (7 - x)] for y in range(8) for x in range(8))


def vflip(t):
    return tuple(t[(7 - y) * 8 + x] for y in range(8) for x in range(8))


def remap(t, m):
    return tuple(m[c] for c in t)


def to_md(t):
    """64 colour indices -> 32 bytes of Genesis 4bpp (high nibble = left pixel)."""
    out = bytearray()
    for i in range(0, 64, 2):
        out.append((t[i] << 4) | t[i + 1])
    return bytes(out)


EMPTY = tuple([0] * 64)


# ---------------------------------------------------------------------------
# Parse PlayerGraphicsTable / PlayerGfxTblOffsets from main.asm
# ---------------------------------------------------------------------------
def parse_db_block(lines, label):
    out = []
    try:
        i = next(n for n, l in enumerate(lines) if l.strip().startswith(label + ":"))
    except StopIteration:
        sys.exit(f"main.asm: label {label} not found")
    for l in lines[i + 1:]:
        s = l.split(";")[0].strip()
        if not s:
            if out:
                continue
            continue
        if not s.lower().startswith(".db"):
            break
        out += [int(v.strip().lstrip("$"), 16) for v in s[3:].split(",")]
    return out


def parse_radii():
    path = os.path.join(S2, "mario", "mario.constants.asm")
    txt = open(path).read()

    def get(name):
        m = re.search(rf"^{name}\s*=\s*\$?([0-9A-Fa-f]+)", txt, re.M)
        if not m:
            sys.exit(f"{path}: {name} not found")
        v = m.group(1)
        return int(v, 16) if "$" in m.group(0) else int(v)

    return get("Mario_BigYRadius"), get("Mario_SmallYRadius")


# ---------------------------------------------------------------------------
# Frame model
# ---------------------------------------------------------------------------
class Frame:
    """
    A frame is a list of pieces. Each piece: dict(x, y, w, h, tiles, xf, yf)
      x, y   : asm expression strings for the piece's top-left (relative to x_pos/y_pos)
      w, h   : size in tiles (1..4)
      tiles  : column-major list of tile pixel tuples (already flipped as needed)
      xf, yf : piece-level flip bits (used only for the fireball mappings)
    Also px/py: numeric positions for the preview.
    """

    def __init__(self, name, note=""):
        self.name = name
        self.note = note
        self.pieces = []


def grid_from_row(table, row, tiles, kick=None):
    """8 tile IDs -> 4x2 grid of pixel tiles, applying ChkForPlayerAttrib flips."""
    ids = table[row * 8:(row + 1) * 8]
    if kick is not None:
        ids = list(ids)
        ids[6] = kick  # first sprite of the 4th row (sprite 7)
    offset = row * 8
    grid = []
    for r in range(4):
        left_id, right_id = ids[r * 2], ids[r * 2 + 1]
        left = EMPTY if left_id == BLANK_TILE else tiles[left_id]
        right = EMPTY if right_id == BLANK_TILE else tiles[right_id]
        if (r == 3 and (offset in ATTRIB_ROW4 or offset in ATTRIB_ROW3_AND_4)) or \
           (r == 2 and offset in ATTRIB_ROW3_AND_4):
            right = hflip(right)
        grid.append([left, right])
    return grid


def trim_rows(grid):
    """Drop fully blank leading/trailing rows. Returns (rows, first_row_index)."""
    nonblank = [i for i, row in enumerate(grid) if any(t != EMPTY for t in row)]
    if not nonblank:
        return [], 0
    a, b = nonblank[0], nonblank[-1]
    return grid[a:b + 1], a


def upright_frame(name, grid, box_h, radius_sym, radius_val, note=""):
    """
    grid: 4 rows x 2 cols of tiles (NES 16x32 box, feet at the bottom).
    box_h: 32 for the big box, 16 for the small box (small frames use only rows 2-3).
    Feet are anchored at y_pos + radius + 1 (exclusive bottom edge).
    """
    f = Frame(name, note)
    rows, first = trim_rows(grid)
    if not rows:
        return f
    box_top_row = 4 - box_h // 8  # rows above this are outside the box
    if first < box_top_row:
        raise ValueError(f"{name}: tiles above the {box_h}px box")
    h = len(rows)
    # y of the first kept row relative to the feet line
    rel = (first - 4) * 8  # e.g. row 0 -> -32, row 2 -> -16
    tiles = [rows[r][c] for c in range(2) for r in range(h)]
    f.pieces.append(dict(
        x="-8", y=f"{radius_sym}+1{rel:+d}", w=2, h=h, tiles=tiles, xf=0, yf=0,
        px=-8, py=radius_val + 1 + rel))
    return f


def rotate_frame(src, name, radius_sym, radius_val):
    """
    Rotate an upright frame 90 degrees so the feet point +x (standing on a
    right-hand wall), about (x_pos, y_pos). Cell (x, y) -> (y, -x-1).
    Upright piece occupies x in [-8, 8), y in [R+1+rel, R+1+rel+H).
    """
    p = src.pieces[0]
    w_t, h_t = p["w"], p["h"]
    W, H = w_t * 8, h_t * 8
    # Assemble upright image
    img = [[0] * W for _ in range(H)]
    for c in range(w_t):
        for r in range(h_t):
            t = p["tiles"][c * h_t + r]
            for y in range(8):
                for x in range(8):
                    img[r * 8 + y][c * 8 + x] = t[y * 8 + x]
    # Rotated image: width H, height W; R(i', j') = I(row=i', col=W-1-j')
    rot = [[img[i2][W - 1 - j2] for i2 in range(H)] for j2 in range(W)]
    nw_t, nh_t = h_t, w_t
    tiles = []
    for c in range(nw_t):
        for r in range(nh_t):
            tiles.append(tuple(rot[r * 8 + y][c * 8 + x] for y in range(8) for x in range(8)))
    rel = p["py"] - (radius_val + 1)  # recover rel from the numeric preview position
    f = Frame(name, f"{src.name} rotated 90 (feet +x)")
    f.pieces.append(dict(
        x=f"{radius_sym}+1{rel:+d}", y="-8", w=nw_t, h=nh_t, tiles=tiles, xf=0, yf=0,
        px=radius_val + 1 + rel, py=-8))
    return f


# ---------------------------------------------------------------------------
# Art packing + DPLC
# ---------------------------------------------------------------------------
def pack_frames(frames):
    """
    Assign each frame's tiles to art. Each frame's VRAM layout is its pieces'
    tiles in order; mapping tile indices are positions in that layout.
    Reuse an existing contiguous art run if the whole frame matches, else append.
    Returns (art_tiles, dplc_entries_per_frame).
    """
    art = []
    dplcs = []
    for f in frames:
        seq = [t for p in f.pieces for t in p["tiles"]]
        if not seq:
            dplcs.append([])
            continue
        if len(seq) > 32:
            raise ValueError(f"{f.name}: {len(seq)} tiles exceeds the 32-tile VRAM slot")
        start = None
        n = len(seq)
        for i in range(len(art) - n + 1):
            if art[i:i + n] == seq:
                start = i
                break
        if start is None:
            start = len(art)
            art += seq
        entries = []
        off, left = start, n
        while left:
            k = min(16, left)
            entries.append((k, off))
            off += k
            left -= k
        dplcs.append(entries)
    if len(art) > 0xFFF:
        raise ValueError("art exceeds DPLC 12-bit offset range")
    return art, dplcs


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------
HEADER = "; Generated by tools/chr2md.py from smb1-disasm-master - do not edit by hand.\n"


def write_mappings(path, frames, comment):
    lines = [HEADER, f"; {comment}\n", ".offsets:\tmappingsTable\n"]
    for i in range(len(frames)):
        lines.append(f"\tmappingsTableEntry.w\t.frame{i}\n")
    lines.append("\n")
    for i, f in enumerate(frames):
        note = f"\t; {f.name}" + (f" - {f.note}" if f.note else "")
        lines.append(f".frame{i}:\tspriteHeader{note}\n")
        vram = 0
        for p in f.pieces:
            tile = p.get("tile", vram)
            lines.append(
                f"\tspritePiece\t{p['x']}, {p['y']}, {p['w']}, {p['h']}, "
                f"${tile:X}, {p['xf']}, {p['yf']}, 0, 0\n")
            vram += len(p["tiles"])
        lines.append(f".frame{i}_End\n\n")
    with open(path, "w", newline="\n") as fh:
        fh.writelines(lines)


def write_dplc(path, frames, dplcs):
    lines = [HEADER, ".offsets:\tmappingsTable\n"]
    for i in range(len(frames)):
        lines.append(f"\tmappingsTableEntry.w\t.frame{i}\n")
    lines.append("\n")
    for i, (f, ent) in enumerate(zip(frames, dplcs)):
        lines.append(f".frame{i}:\tdplcHeader\t; {f.name}\n")
        for k, off in ent:
            lines.append(f"\tdplcEntry\t${k:X}, ${off:X}\n")
        lines.append(f".frame{i}_End\n\n")
    with open(path, "w", newline="\n") as fh:
        fh.writelines(lines)


def write_bin(path, tiles, m):
    with open(path, "wb") as fh:
        for t in tiles:
            fh.write(to_md(remap(t, m)))


def write_png(path, rgb_rows):
    h = len(rgb_rows)
    w = len(rgb_rows[0]) // 3
    raw = b"".join(b"\x00" + bytes(r) for r in rgb_rows)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
    open(path, "wb").write(png)


def load_md_palette():
    data = open(os.path.join(S2, "art", "palettes", "SonicAndTails.bin"), "rb").read()[:32]
    pal = []
    for i in range(16):
        w = (data[i * 2] << 8) | data[i * 2 + 1]
        r, g, b = (w >> 1) & 7, (w >> 5) & 7, (w >> 9) & 7
        pal.append((r * 36, g * 36, b * 36))
    return pal


def render_sheet(path, frame_sets, pal):
    """frame_sets: list of (frames, colour remap). One row of cells per set."""
    CELL, SCALE, PAD = 48, 3, 2
    cols = max(len(fs) for fs, _ in frame_sets)
    W, H = cols * (CELL + PAD), len(frame_sets) * (CELL + PAD)
    canvas = [[(40, 40, 60)] * W for _ in range(H)]
    for row_i, (frames, m) in enumerate(frame_sets):
        for col_i, f in enumerate(frames):
            ox, oy = col_i * (CELL + PAD), row_i * (CELL + PAD)
            for y in range(CELL):
                for x in range(CELL):
                    checker = ((x // 4) + (y // 4)) & 1
                    canvas[oy + y][ox + x] = (90, 90, 110) if checker else (110, 110, 130)
            cx, cy = ox + CELL // 2, oy + CELL // 2
            canvas[cy][cx] = (0, 255, 0)  # origin = (x_pos, y_pos)
            for p in f.pieces:
                for c in range(p["w"]):
                    for r in range(p["h"]):
                        t = p["tiles"][c * p["h"] + r]
                        if p["xf"]:
                            t = hflip(t)
                        if p["yf"]:
                            t = vflip(t)
                        cc = (p["w"] - 1 - c) if p["xf"] else c
                        rr = (p["h"] - 1 - r) if p["yf"] else r
                        for y in range(8):
                            for x in range(8):
                                v = m[t[y * 8 + x]]
                                if v:
                                    X = cx + p["px"] + cc * 8 + x
                                    Y = cy + p["py"] + rr * 8 + y
                                    if ox <= X < ox + CELL and oy <= Y < oy + CELL:
                                        canvas[Y][X] = pal[v]
    rows = []
    for line in canvas:
        out = []
        for px in line:
            out += list(px) * SCALE
        for _ in range(SCALE):
            rows.append(out)
    write_png(path, rows)


# ---------------------------------------------------------------------------
# Phase 7: HUD life counter and end-of-act signpost (H13, H16).
# Both are drawn over S2's own art, so S2's Nemesis files are decoded for the
# parts that are kept (the name font, the "x", the signpost's border).
# ---------------------------------------------------------------------------
def md_tiles(data):
    """Genesis 4bpp bytes -> list of 64-index tiles."""
    return [tuple((data[t * 32 + y * 4 + x // 2] >> (4 if x % 2 == 0 else 0)) & 15
                  for y in range(8) for x in range(8)) for t in range(len(data) // 32)]


def nem_tiles(name):
    if HERE not in sys.path:                          # (python -I leaves the script's folder out)
        sys.path.insert(0, HERE)
    from nemesis import decompress
    return md_tiles(decompress(open(os.path.join(S2, "art", "nemesis", name), "rb").read()))


def tiles_to_image(tiles, w, h):
    """Column-major w x h tile piece -> image rows (lists of indices)."""
    img = [[0] * (w * 8) for _ in range(h * 8)]
    for c in range(w):
        for r in range(h):
            t = tiles[c * h + r]
            for y in range(8):
                for x in range(8):
                    img[r * 8 + y][c * 8 + x] = t[y * 8 + x]
    return img


def image_to_tiles(img, w, h, x0=0):
    """Image rows -> column-major w x h tiles, starting at column x0."""
    return [tuple(img[r * 8 + y][x0 + c * 8 + x] for y in range(8) for x in range(8))
            for c in range(w) for r in range(h)]


# The life counter's name is drawn in a 7 px font with a drop shadow (index $C
# letter, index 1 shadow), in the 32x8 top row of the 4x2 name piece. "MARIO":
# M from MILES, A from TAILS, I and O from SONIC; S2 has no R, so it is drawn
# here in the same style (square top-left, unlike the A).
GLYPH_R = ["......",
           "CCCC1.",
           "CC1CC1",
           "CC1CC1",
           "CCCC1.",
           "CC1CC1",
           "CC1CC1",
           "111111"]
# "LUIGI": L from MILES, I from SONIC; U and G drawn in the same style (U as
# SONIC's O without its top, G as its C with a bar).
GLYPH_U = ["......",
           "CC1CC1",
           "CC1CC1",
           "CC1CC1",
           "CC1CC1",
           "CC1CC1",
           ".CCC1.",
           ".111.."]
GLYPH_G = ["......",
           ".CCCC1",
           "CC1111",
           "CC1CCC",
           "CC11CC",
           "CC1.CC",
           ".CCCC1",
           ".1111."]


def life_counter(face_tiles, name="MARIO"):
    """S2 life counter layout (12 tiles, as 'Sonic lives counter.nem'): face 2x2
    (column-major), then the 4x2 name piece (column-major). The name piece's
    bottom row - the "x" and the two digit slots Hud_Lives writes - is Sonic's."""
    sonic = nem_tiles("Sonic lives counter.nem")
    miles = nem_tiles("Miles life counter.nem")
    tails = nem_tiles("Tails life counter.nem")

    def name_row(ts):
        return tiles_to_image(ts[4:12], 4, 2)[:8]

    s, m, t = name_row(sonic), name_row(miles), name_row(tails)
    glyph = lambda img, x0, x1: [row[x0:x1] for row in img]
    drawn = lambda rows: [[int(ch, 16) if ch != "." else 0 for ch in row] for row in rows]
    if name == "MARIO":
        letters = [
            (1, glyph(m, 1, 9)),                          # M
            (9, [[0] + r[1:] if y == 1 else r for y, r in enumerate(glyph(t, 10, 16))]),  # A (T's shadow removed)
            (15, drawn(GLYPH_R)),                         # R
            (22, glyph(s, 22, 25)),                       # I
            (26, glyph(s, 7, 13)),                        # O
        ]
    else:
        letters = [
            (3, glyph(m, 14, 19)),                        # L
            (9, drawn(GLYPH_U)),                          # U
            (16, glyph(s, 22, 25)),                       # I
            (20, drawn(GLYPH_G)),                         # G
            (27, glyph(s, 22, 25)),                       # I
        ]
    top = [[0] * 32 for _ in range(8)]
    for x0, g in letters:
        for y, row in enumerate(g):
            for x, v in enumerate(row):
                if v:
                    top[y][x0 + x] = v
    name = tiles_to_image(sonic[4:12], 4, 2)
    name[:8] = top
    return list(face_tiles) + image_to_tiles(name, 4, 2)


def signpost_panel(table, tiles, remap_normal, bg=6):
    """Signpost frame 0 replacement (Obj0D_MapUnc_195BE frame 0: two 3x4 pieces
    at tiles $22/$2E, palette line 0): Tails' panel border (frame 1: edge $3A,
    4x4 at $3E, edge mirrored) with a plain white interior, and Mario's face -
    the top 12 rows of SMB1's big standing frame, pixel-doubled - in it."""
    sp = nem_tiles("Signpost.nem")
    img = [[0] * 48 for _ in range(32)]

    def put(base, w, h, X, flip=False):
        part = tiles_to_image(sp[base:base + w * h], w, h)
        for y in range(h * 8):
            for x in range(w * 8):
                v = part[y][x]
                img[y][X + (w * 8 - 1 - x if flip else x)] = LUIGI_SLOT_MERGE if v == LUIGI_SLOT else v

    put(0x3A, 1, 4, 0)
    put(0x3E, 4, 4, 8)
    put(0x3A, 1, 4, 40, True)
    # bg: white (6) for Mario: his colours all read on it (on Tails' blue, his dark
    # blue hair vanished); Luigi's white cap needs light blue (5).
    for x in range(4, 44):
        img[4][x] = 1                                 # inner top shadow (without Tails' ears)
    for y in range(5, 29):
        for x in range(4, 44):
            img[y][x] = bg
    stand = grid_from_row(table, 25, tiles)          # big standing
    face = [[remap_normal[stand[r // 8][c // 8][(r % 8) * 8 + c % 8]] for c in range(16)] for r in range(12)]
    for y in range(24):
        for x in range(32):
            v = face[y // 2][x // 2]
            if v:
                img[5 + y][8 + x] = v
    return image_to_tiles(img, 3, 4, 0) + image_to_tiles(img, 3, 4, 24), img


# ---------------------------------------------------------------------------
# Phase 7.5: SMB1's Bowser as the WFZ boss ("Mecha Bowser": his colours are the
# nearest ones in WFZ's palette line 1, the line the boss arena's walls use).
# ---------------------------------------------------------------------------
BOSS_PAL_LINE = 1                                     # S2 palette line (WFZ.bin's first line)


def load_bg_chr():
    """SMB1's BG pattern table (gfx/bg.chr, tiles from $00; the file stops early)."""
    data = open(os.path.join(SMB, "gfx", "bg.chr"), "rb").read()
    tiles = []
    for t in range(len(data) // 16):
        b = data[t * 16:(t + 1) * 16]
        tiles.append(tuple(((b[y] >> (7 - x)) & 1) | (((b[y + 8] >> (7 - x)) & 1) << 1)
                           for y in range(8) for x in range(8)))
    return tiles


def wfz_line(n):
    pal = open(os.path.join(S2, "art", "palettes", "WFZ.bin"), "rb").read()
    o = (n - 1) * 32                                  # WFZ.bin holds lines 1-3
    return [(pal[o + i * 2] << 8) | pal[o + i * 2 + 1] for i in range(16)]


def boss_art(sprite_tiles, main_lines):
    """Bowser (4 frames: mouth closed/open x feet 1/2), his flame, the hammer's
    4 spin poses and the axe. Returns (tiles, frames, remaps) with each frame's
    pieces referring to tile indices in `tiles`."""
    gp = parse_db_block(main_lines, "CastlePaletteData")[3:]   # BG 0-3, sprite 0-3, 4 bytes each
    bowser_pal = parse_db_block(main_lines, "BowserPaletteData")[3:]
    line = wfz_line(BOSS_PAL_LINE)
    remaps = dict(
        bowser=nearest_remap(bowser_pal[1:4], line, "Bowser (BowserPaletteData)"),
        flame=nearest_remap(gp[4 * 6 + 1:4 * 6 + 4], line, "flame (castle sprite palette 2)"),
        hammer=nearest_remap(gp[4 * 7 + 1:4 * 7 + 4], line, "hammer (castle sprite palette 3)"),
        axe=nearest_remap(gp[4 * 3 + 1:4 * 3 + 4], line, "axe (castle BG palette 3)"),
    )
    bg = load_bg_chr()
    egt = parse_db_block(main_lines, "EnemyGraphicsTable")

    def enemy_rows(offset):
        """EnemyGraphicsTable entry -> 3 rows x 2 tiles, facing right as stored
        (DrawSpriteObject swaps and h-flips them for facing left)."""
        ids = egt[offset:offset + 6]
        return [[EMPTY if i == BLANK_TILE else sprite_tiles[i] for i in ids[r * 2:r * 2 + 2]] for r in range(3)]

    def half_image(rows, mirror):
        img = [[0] * 16 for _ in range(24)]
        for r in range(3):
            for c in range(2):
                t = rows[r][c]
                for y in range(8):
                    for x in range(8):
                        img[r * 8 + y][c * 8 + x] = t[y * 8 + x]
        if mirror:
            img = [row[::-1] for row in img]
        return img

    tiles, frames = [], []

    def add_tiles(img, w, h, remap):
        """Cut an image into column-major tiles (remapped), dedupe; return the first index."""
        cut = []
        for c in range(w):
            for r in range(h):
                cut.append(tuple(remap[img[r * 8 + y][c * 8 + x]] for y in range(8) for x in range(8)))
        n = len(cut)
        for i in range(len(tiles) - n + 1):
            if tiles[i:i + n] == cut:
                return i
        tiles.extend(cut)
        return len(tiles) - n

    # Bowser facing left (as he starts, towards Mario): the front (head) on the
    # left, mirrored; the rear 16 px to the right and 8 px lower (BowserGfxHandler).
    # Origin = the centre of the 32x32 box; feet at y+16.
    front = {1: enemy_rows(0xD2), 2: enemy_rows(0xDE)}      # mouth closed / open
    rear = {1: enemy_rows(0xD8), 2: enemy_rows(0xE4)}       # feet 1 / 2
    for mouth in (1, 2):
        for feet in (1, 2):
            f = Frame(f"Bowser_Mouth{mouth}_Feet{feet}", "facing left; x_flip faces right, y_flip = defeated")
            for rows, px, py in ((front[mouth], -16, -16), (rear[feet], 0, -8)):
                img = half_image(rows, mirror=True)
                t = add_tiles(img, 2, 3, remaps["bowser"])
                f.pieces.append(dict(x=str(px), y=str(py), w=2, h=3, tile=t, xf=0, yf=0,
                                     tiles=tiles[t:t + 6], px=px, py=py))
            frames.append(f)
    # flame: tiles $51-$53 left to right (ProcBowserFlame / DrawFlameLoop), 24x8
    img = [[sprite_tiles[0x51 + c][y * 8 + x] for c in range(3) for x in range(8)] for y in range(8)]
    t = add_tiles(img, 3, 1, remaps["flame"])
    f = Frame("Flame", "tiles $51-$53; ProcBowserFlame flips it vertically every 2 frames")
    f.pieces.append(dict(x="-12", y="-4", w=3, h=1, tile=t, xf=0, yf=0, tiles=tiles[t:t + 3], px=-12, py=-4))
    frames.append(f)
    # hammer: DrawHammer's 4 poses, two 8x8 sprites each (origin = the 16x16 box centre)
    fx, fy = parse_db_block(main_lines, "FirstSprXPos"), parse_db_block(main_lines, "FirstSprYPos")
    sx, sy = parse_db_block(main_lines, "SecondSprXPos"), parse_db_block(main_lines, "SecondSprYPos")
    t1, t2 = parse_db_block(main_lines, "FirstSprTilenum"), parse_db_block(main_lines, "SecondSprTilenum")
    attr = parse_db_block(main_lines, "HammerSprAttrib")
    for p in range(4):
        f = Frame(f"Hammer{p}", "DrawHammer pose")
        x1, y1 = fx[p], fy[p]
        x2, y2 = x1 + sx[p], y1 + sy[p]
        for tid, x, y in ((t1[p], x1, y1), (t2[p], x2, y2)):
            t = add_tiles([[sprite_tiles[tid][yy * 8 + xx] for xx in range(8)] for yy in range(8)], 1, 1,
                          remaps["hammer"])
            hf, vf = (attr[p] >> 6) & 1, (attr[p] >> 7) & 1
            f.pieces.append(dict(x=str(x - 8), y=str(y - 8), w=1, h=1, tile=t, xf=hf, yf=vf,
                                 tiles=[tiles[t]], px=x - 8, py=y - 8))
        frames.append(f)
    # axe: metatile $7B,$7D,$7C,$7E (TL, BL, TR, BR), 16x16
    ids = parse_db_block(main_lines, "Palette3_MTiles")[5 * 4:5 * 4 + 4]
    img = [[0] * 16 for _ in range(16)]
    for i, tid in enumerate(ids):
        c, r = i // 2, i % 2
        for y in range(8):
            for x in range(8):
                img[r * 8 + y][c * 8 + x] = bg[tid][y * 8 + x]
    t = add_tiles(img, 2, 2, remaps["axe"])
    f = Frame("Axe", "SMB1 metatile $7B/$7D/$7C/$7E")
    f.pieces.append(dict(x="-8", y="-8", w=2, h=2, tile=t, xf=0, yf=0, tiles=tiles[t:t + 4], px=-8, py=-8))
    frames.append(f)
    return tiles, frames, remaps, line


def render_indexed(path, img, pal, scale=4):
    rows = []
    for line in img:
        out = []
        for v in line:
            out += list(pal[v] if v else (255, 0, 255)) * scale
        rows += [out] * scale
    write_png(path, rows)


# ---------------------------------------------------------------------------
def main():
    tiles = load_chr(os.path.join(SMB, "gfx", "sprites.chr"))
    lines = open(os.path.join(SMB, "main.asm")).read().splitlines()
    table = parse_db_block(lines, "PlayerGraphicsTable")
    if len(table) != 26 * 8:
        sys.exit(f"PlayerGraphicsTable: expected {26*8} bytes, got {len(table)}")
    big_r, small_r = parse_radii()
    remaps = get_remaps()
    REMAP_NORMAL, REMAP_FIERY, REMAP_FIREBALL = remaps["normal"], remaps["fiery"], remaps["fireball"]
    REMAP_LUIGI = remaps["luigi"]
    BIG, SMALL = "Mario_BigYRadius", "Mario_SmallYRadius"

    frames = [Frame("Blank")]
    equates = [("MarioFrame_Blank", 0, "empty frame")]

    # 1..26: PlayerGraphicsTable rows, natural anchoring
    equates.append(("MarioFrame_GfxBase", len(frames),
                    "mapping_frame = PlayerGfxOffset/8 + MarioFrame_GfxBase"))
    row_frame = {}
    for row in range(26):
        grid = grid_from_row(table, row, tiles)
        small = FIRST_SMALL_ROW <= row <= LAST_SMALL_ROW
        name = f"Row{row:02X}_{ROW_NAMES[row]}"
        note = f"PlayerGfxOffset ${row*8:02X}"
        if small:
            f = upright_frame(name, grid, 16, SMALL, small_r, note + ", small radius")
        else:
            f = upright_frame(name, grid, 32, BIG, big_r, note + ", big radius")
        row_frame[row] = len(frames)
        frames.append(f)

    # 27..38: small rows in the big (NES 32px) box, for grow/shrink
    equates.append(("MarioFrame_TallSmallBase", len(frames) - FIRST_SMALL_ROW,
                    "small row in big box: PlayerGfxOffset/8 + MarioFrame_TallSmallBase"))
    for row in range(FIRST_SMALL_ROW, LAST_SMALL_ROW + 1):
        grid = grid_from_row(table, row, tiles)
        frames.append(upright_frame(f"Row{row:02X}_{ROW_NAMES[row]}_Tall", grid, 32, BIG, big_r,
                                    f"PlayerGfxOffset ${row*8:02X}, big radius"))

    # swim kick variants
    for row, kick in SWIM_KICK.items():
        grid = grid_from_row(table, row, tiles, kick=kick)
        small = row >= FIRST_SMALL_ROW
        name = f"Row{row:02X}_{ROW_NAMES[row]}_Kick"
        equates.append((f"MarioFrame_{ROW_NAMES[row]}_Kick", len(frames),
                        f"SwimKickTileNum ${kick:02X} on PlayerGfxOffset ${row*8:02X}"))
        frames.append(upright_frame(name, grid, 16 if small else 32,
                                    SMALL if small else BIG, small_r if small else big_r,
                                    "swim kick"))

    # 90-degree rotations
    for row in ROTATE_ROWS:
        small = FIRST_SMALL_ROW <= row <= LAST_SMALL_ROW
        src = frames[row_frame[row]]
        equates.append((f"MarioFrame_{ROW_NAMES[row]}_Rot90", len(frames),
                        f"PlayerGfxOffset ${row*8:02X} rotated, feet toward +x"))
        frames.append(rotate_frame(src, f"Row{row:02X}_{ROW_NAMES[row]}_Rot90",
                                   SMALL if small else BIG, small_r if small else big_r))

    # fireball-throw composites (fire row's top 3 rows + this row's 4th row)
    fire_grid = grid_from_row(table, FIRE_ROW, tiles)
    for row in THROW_ROWS:
        legs = grid_from_row(table, row, tiles)
        grid = fire_grid[:3] + legs[3:]
        name = ROW_NAMES[row].replace("Big_", "")
        equates.append((f"MarioFrame_Throw_{name}", len(frames),
                        f"throw ($58) rows 1-3 over PlayerGfxOffset ${row*8:02X} row 4"))
        frames.append(upright_frame(f"Throw_{name}", grid, 32, BIG, big_r, "fireball throw while moving"))
    equates.append(("MarioFrame_Count", len(frames), "number of mapping frames"))

    art, dplcs = pack_frames(frames)
    max_tiles = max(sum(len(p["tiles"]) for p in f.pieces) for f in frames)

    # --- fireball: tiles $64,$65 (fireball), $66,$67,$68 (explosion) ---
    fb_ids = [0x64, 0x65, 0x66, 0x67, 0x68]
    fb_tiles = [tiles[i] for i in fb_ids]
    fb_frames = []
    for i, (t, flip) in enumerate([(0, 0), (1, 0), (0, 1), (1, 1)]):
        f = Frame(f"Fireball{i}", f"tile ${fb_ids[t]:02X}" + (", flipped both ways" if flip else ""))
        f.pieces.append(dict(x="-4", y="-4", w=1, h=1, tiles=[fb_tiles[t]], xf=flip, yf=flip,
                             tile=t, px=-4, py=-4))
        fb_frames.append(f)
    for i, tid in enumerate([0x68, 0x67, 0x66]):  # ExplosionTiles order
        t = fb_ids.index(tid)
        f = Frame(f"Explosion{i}", f"tile ${tid:02X} x4 (DrawExplosion_Fireball)")
        for (x, y, xf, yf) in [(-8, -8, 0, 0), (-8, 0, 0, 1), (0, -8, 1, 0), (0, 0, 1, 1)]:
            f.pieces.append(dict(x=str(x), y=str(y), w=1, h=1, tiles=[fb_tiles[t]],
                                 xf=xf, yf=yf, tile=t, px=x, py=y))
        fb_frames.append(f)

    # --- life counter: small standing face 2x2 (column-major) + "MARIO" / "LUIGI" ---
    stand = grid_from_row(table, 23, tiles)
    face_ts = (stand[2][0], stand[3][0], stand[2][1], stand[3][1])
    life = life_counter([remap(t, REMAP_NORMAL) for t in face_ts])
    luigi_life = life_counter([remap(t, REMAP_LUIGI) for t in face_ts], "LUIGI")
    # --- signpost face panel ---
    signpost, signpost_img = signpost_panel(table, tiles, REMAP_NORMAL)
    luigi_signpost, luigi_signpost_img = signpost_panel(table, tiles, REMAP_LUIGI, bg=5)
    # --- WFZ boss: Bowser, flame, hammer, axe ---
    boss_tiles, boss_frames, boss_remaps, boss_line = boss_art(tiles, lines)

    # --- write everything ---
    art_dir = os.path.join(S2, "art", "uncompressed")
    write_bin(os.path.join(art_dir, "Mario.bin"), art, REMAP_NORMAL)
    write_bin(os.path.join(art_dir, "MarioFire.bin"), art, REMAP_FIERY)
    write_bin(os.path.join(art_dir, "Luigi.bin"), art, REMAP_LUIGI)     # fire Luigi = MarioFire.bin (as SMB1)
    write_bin(os.path.join(art_dir, "MarioFireball.bin"), fb_tiles, REMAP_FIREBALL)
    identity = {i: i for i in range(16)}             # already S2 colour indices
    write_bin(os.path.join(art_dir, "MarioLife.bin"), life, identity)
    write_bin(os.path.join(art_dir, "MarioSignpost.bin"), signpost, identity)
    write_bin(os.path.join(art_dir, "LuigiLife.bin"), luigi_life, identity)
    write_bin(os.path.join(art_dir, "LuigiSignpost.bin"), luigi_signpost, identity)
    write_bin(os.path.join(art_dir, "Bowser.bin"), boss_tiles, identity)
    write_mappings(os.path.join(S2, "mappings", "sprite", "Bowser.asm"), boss_frames,
                   f"WFZ boss (Bowser, flame, hammer, axe). Art: Bowser.bin, palette line {BOSS_PAL_LINE}.")
    write_mappings(os.path.join(S2, "mappings", "sprite", "Mario.asm"), frames,
                   "Mario mappings. Origin = (x_pos, y_pos); feet at y_pos + Mario_*YRadius.")
    write_dplc(os.path.join(S2, "mappings", "spriteDPLC", "Mario.asm"), frames, dplcs)
    write_mappings(os.path.join(S2, "mappings", "sprite", "MarioFireball.asm"), fb_frames,
                   "Mario fireball mappings (art: MarioFireball.bin, loaded statically).")

    with open(os.path.join(S2, "mario", "mario_frames.asm"), "w", newline="\n") as fh:
        fh.write(HEADER)
        fh.write("; Mapping frame IDs for MapUnc_Mario (mappings/sprite/Mario.asm).\n\n")
        for name, val, note in equates:
            fh.write(f"{name:<32}= ${val:02X}\t; {note}\n")
        fh.write(f"\nMarioFrame_MaxTiles{'':<13}= ${max_tiles:02X}\t; largest frame, in tiles (VRAM slot is $20)\n")
        fh.write(f"MarioArt_Tiles{'':<18}= ${len(art):02X}\t; tiles in Mario.bin / MarioFire.bin\n")
        fh.write("\n; Fireball mapping frames (mappings/sprite/MarioFireball.asm)\n")
        fh.write("MarioFireballFrame_Ball       = 0\t; +0..3: SMB1 DrawFirebar cycle\n")
        fh.write("MarioFireballFrame_Explosion  = 4\t; +0..2: ExplosionTiles $68,$67,$66\n")
        fh.write("\n; WFZ boss mapping frames (mappings/sprite/Bowser.asm)\n")
        fh.write("BowserFrame_Bowser            = 0\t; +(mouth open)*2 + (feet 2): 32x32, facing left\n")
        fh.write("BowserFrame_Flame             = 4\t; 24x8\n")
        fh.write("BowserFrame_Hammer            = 5\t; +0..3: DrawHammer poses\n")
        fh.write("BowserFrame_Axe               = 9\t; 16x16\n")
        fh.write(f"BowserArt_Tiles               = ${len(boss_tiles):02X}\t; tiles in Bowser.bin\n")
        fh.write(f"BowserPalLine                 = {BOSS_PAL_LINE}\t; S2 palette line (WFZ)\n")

    os.makedirs(OUT, exist_ok=True)
    pal = load_md_palette()
    upright = frames[:39]
    extra = frames[39:]
    render_sheet(os.path.join(OUT, "mario_sheet.png"),
                 [(upright[:27], REMAP_NORMAL), (upright[27:] + extra, REMAP_NORMAL),
                  (upright[:27], REMAP_FIERY), (fb_frames, REMAP_FIREBALL)], pal)
    # life counter preview: face in line 0 colours, name in greys (it uses line 1)
    grey = [(i * 16, i * 16, i * 16) for i in range(16)]
    lc = [[0] * 48 for _ in range(16)]
    face_img = tiles_to_image(life[:4], 2, 2)
    name_img = tiles_to_image(life[4:], 4, 2)
    for y in range(16):
        for x in range(16):
            lc[y][x] = face_img[y][x]
        for x in range(32):
            lc[y][16 + x] = 16 + name_img[y][x] if name_img[y][x] else 0
    render_indexed(os.path.join(OUT, "mario_life.png"), lc, pal + grey)
    render_indexed(os.path.join(OUT, "mario_signpost.png"), signpost_img, pal)
    # Luigi previews: line 0 with LUIGI_SLOT green (as Mario_PalPointers loads it)
    luigi_pal = list(pal)
    luigi_pal[LUIGI_SLOT] = tuple(round(((NES_RGB[0x19] >> s) & 255) / 36.43) * 36 for s in (16, 8, 0))
    render_sheet(os.path.join(OUT, "luigi_sheet.png"),
                 [(upright[:27], REMAP_LUIGI), (upright[27:] + extra, REMAP_LUIGI)], luigi_pal)
    face_img = tiles_to_image(luigi_life[:4], 2, 2)
    name_img = tiles_to_image(luigi_life[4:], 4, 2)
    for y in range(16):
        for x in range(16):
            lc[y][x] = face_img[y][x]
        for x in range(32):
            lc[y][16 + x] = 16 + name_img[y][x] if name_img[y][x] else 0
    render_indexed(os.path.join(OUT, "luigi_life.png"), lc, luigi_pal + grey)
    render_indexed(os.path.join(OUT, "luigi_signpost.png"), luigi_signpost_img, luigi_pal)
    boss_rgb = [md_rgb(w) for w in boss_line]
    render_sheet(os.path.join(OUT, "bowser_sheet.png"), [(boss_frames, {i: i for i in range(16)})], boss_rgb)
    for k, v in boss_remaps.items():
        print(f"boss colours {k:<6}: " + ", ".join(f"{i}->${v[i]:X}" for i in (1, 2, 3)))
    print(f"boss tiles: {len(boss_tiles)}")

    print(f"frames: {len(frames)}  art tiles: {len(art)} ({len(art)*32} bytes)  "
          f"max tiles/frame: {max_tiles}  fireball tiles: {len(fb_tiles)}")
    print(f"radii used for preview: big ${big_r:X}, small ${small_r:X}")
    for k, v in remaps.items():
        print(f"colours {k:<8}: " + ", ".join(f"{i}->${v[i]:X}" for i in (1, 2, 3)))


if __name__ == "__main__":
    main()
