"""verify_mario_art.py - decode Mario/fireball frames from a built ROM and compare them
pixel-for-pixel with SMB1's own sprite composition (PlayerGraphicsTable + flips).

Usage (from s2disasm-master, after building with marioMode = 1):
    python -I ../tools/verify_mario_art.py ../tools/chr2md.py s2built.bin s2.lst
"""
import importlib.util, sys, os, re

chr2md_path, rom_path, lst_path = sys.argv[1:4]
spec = importlib.util.spec_from_file_location("chr2md", chr2md_path)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

rom = open(rom_path, "rb").read()
lst = open(lst_path, errors="replace").read()[-3_000_000:]
def sym(n):
    mm = re.search(r"\b" + n + r" :\s+([0-9A-F]+)", lst)
    return int(mm.group(1), 16)
ART, MAP, DPLC = sym("ArtUnc_Mario"), sym("MapUnc_Mario"), sym("MapRUnc_Mario")
FB_ART, FB_MAP = sym("ArtUnc_MarioFireball"), sym("MapUnc_MarioFireball")
w16 = lambda a: (rom[a] << 8) | rom[a + 1]
s16 = lambda a: w16(a) - 0x10000 if w16(a) & 0x8000 else w16(a)
big_r, small_r = m.parse_radii()

def md_tile(addr):
    px = []
    for b in rom[addr:addr + 32]:
        px += [b >> 4, b & 15]
    return px

def decode(map_base, idx, vram):
    """vram: list of tile pixel lists. Returns {(x,y): colour}."""
    fa = map_base + s16(map_base + idx * 2)
    n = w16(fa)
    img = {}
    for p in range(n):
        a = fa + 2 + p * 8
        ypos = rom[a] - 256 if rom[a] & 0x80 else rom[a]
        size = rom[a + 1]
        w, h = ((size >> 2) & 3) + 1, (size & 3) + 1
        tw = w16(a + 2)
        tile, xf, yf = tw & 0x7FF, (tw >> 11) & 1, (tw >> 12) & 1
        xpos = s16(a + 6)
        for c in range(w):
            for r in range(h):
                t = vram[tile + c * h + r]
                cc = (w - 1 - c) if xf else c
                rr = (h - 1 - r) if yf else r
                for y in range(8):
                    for x in range(8):
                        v = t[y * 8 + x]
                        if v:
                            X = xpos + cc * 8 + (7 - x if xf else x)
                            Y = ypos + rr * 8 + (7 - y if yf else y)
                            img[(X, Y)] = v
    return img

def dplc_vram(idx):
    fa = DPLC + s16(DPLC + idx * 2)
    n = w16(fa)
    vram = []
    for e in range(n):
        ent = w16(fa + 2 + e * 2)
        cnt, off = (ent >> 12) + 1, ent & 0xFFF
        vram += [md_tile(ART + (off + k) * 32) for k in range(cnt)]
    if len(vram) > 32:
        raise SystemExit(f"frame {idx}: DPLC loads {len(vram)} tiles > 32")
    return vram

# Independent reference: compose each PlayerGraphicsTable row the way the NES does,
# as a 16x32 box whose bottom edge is at y = R+1, x from -8.
tiles = m.load_chr(os.path.join(m.SMB, "gfx", "sprites.chr"))
table = m.parse_db_block(open(os.path.join(m.SMB, "main.asm")).read().splitlines(), "PlayerGraphicsTable")
NES2MD = m.get_remaps()["normal"]
def nes_row(row, R, kick=None):
    ids = list(table[row * 8:row * 8 + 8])
    if kick is not None:
        ids[6] = kick
    off = row * 8
    img = {}
    for r in range(4):
        for c in range(2):
            tid = ids[r * 2 + c]
            if tid == 0xFC:
                continue
            # ChkForPlayerAttrib: $50/$B8/$C0 -> C_S_IGAtt (4th row); $C8 falls
            # through "cmp #$c8 / bne ExPlyrAt" into KilledAtt, like $B0 (3rd+4th).
            flip = c == 1 and ((r == 3 and off in (0x50, 0xB8, 0xC0, 0xC8, 0xB0)) or
                               (r == 2 and off in (0xB0, 0xC8)))
            t = tiles[tid]
            for y in range(8):
                for x in range(8):
                    v = t[y * 8 + (7 - x if flip else x)]
                    if v:
                        img[(-8 + c * 8 + x, R + 1 - 32 + r * 8 + y)] = NES2MD[v]
    return img

nframes = (s16(MAP) // 2)
errors = 0
def check(idx, ref, label):
    global errors
    got = decode(MAP, idx, dplc_vram(idx))
    if got != ref:
        errors += 1
        print(f"MISMATCH frame {idx} ({label}): {len(got)} px vs {len(ref)} px expected")

check(0, {}, "blank")
for row in range(26):
    R = small_r if 12 <= row <= 23 else big_r
    check(1 + row, nes_row(row, R), f"row {row}")
for i, row in enumerate(range(12, 24)):
    check(27 + i, nes_row(row, big_r), f"tall row {row}")
for i, (row, kick) in enumerate([(5, 0x31), (6, 0x31), (7, 0x31), (17, 0x46), (18, 0x46)]):
    R = small_r if row >= 12 else big_r
    check(39 + i, nes_row(row, R, kick), f"kick row {row}")
for i, row in enumerate(m.ROTATE_ROWS):
    R = small_r if 12 <= row <= 23 else big_r
    up = nes_row(row, R)
    rot = {(y, -x - 1): v for (x, y), v in up.items()}
    check(44 + i, rot, f"rot row {row}")
# throw composites: rows 1-3 (y < R+1-8) of the fire row, row 4 of the current row
base = 44 + len(m.ROTATE_ROWS)
for i, row in enumerate(m.THROW_ROWS):
    fire, legs = nes_row(m.FIRE_ROW, big_r), nes_row(row, big_r)
    cut = big_r + 1 - 8
    ref = {k: v for k, v in fire.items() if k[1] < cut}
    ref.update({k: v for k, v in legs.items() if k[1] >= cut})
    check(base + i, ref, f"throw over row {row}")

# Fireball: static art; frames 0-3 ball, 4-6 explosion
fbv = [md_tile(FB_ART + k * 32) for k in range(5)]
FB = m.get_remaps()["fireball"]
def fb_tile_img(tid, x0, y0, xf, yf):
    t = tiles[tid]; img = {}
    for y in range(8):
        for x in range(8):
            v = t[y * 8 + x]
            if v:
                img[(x0 + (7 - x if xf else x), y0 + (7 - y if yf else y))] = FB[v]
    return img
for i, (tid, fl) in enumerate([(0x64, 0), (0x65, 0), (0x64, 1), (0x65, 1)]):
    ref = fb_tile_img(tid, -4, -4, fl, fl)
    if decode(FB_MAP, i, fbv) != ref:
        errors += 1; print(f"MISMATCH fireball frame {i}")
for i, tid in enumerate([0x68, 0x67, 0x66]):
    ref = {}
    for (x, y, xf, yf) in [(-8, -8, 0, 0), (-8, 0, 0, 1), (0, -8, 1, 0), (0, 0, 1, 1)]:
        ref.update(fb_tile_img(tid, x, y, xf, yf))
    if decode(FB_MAP, 4 + i, fbv) != ref:
        errors += 1; print(f"MISMATCH explosion frame {i}")

print(f"mapping frames in ROM: {nframes}; errors: {errors}")
sys.exit(1 if errors else 0)
