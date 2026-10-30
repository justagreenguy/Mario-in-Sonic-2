#!/usr/bin/env python3
"""
nemesis.py - Nemesis decompressor and compressor (Sonic 2's art/nemesis/*.nem format).

    from nemesis import decompress      # bytes -> uncompressed 4bpp tiles
    from nemesis import compress        # uncompressed 4bpp tiles -> bytes
    python -I tools/nemesis.py file.nem # prints the tile count

Format: a word header (bit 15 = XOR mode, low 15 bits = tile count), a code
table, then the bit stream. Code table entries: a byte with bit 7 set selects
the nibble value; other bytes are (run - 1) << 4 | code length, followed by
the code; $FF ends the table. In the stream, the 6-bit code %111111 is an
inline run: 3 bits run - 1, then 4 bits value. Rows are 8 nibbles; in XOR
mode each row is XORed with the previous one.
"""
import sys


def decompress(data):
    header = data[0] << 8 | data[1]
    xor_mode = bool(header & 0x8000)
    tiles = header & 0x7FFF
    pos = 2
    codes = {}
    value = 0
    b = data[pos]
    pos += 1
    while b != 0xFF:
        if b & 0x80:
            value = b & 0x0F
            b = data[pos]
            pos += 1
            continue
        run = ((b >> 4) & 7) + 1
        length = b & 0x0F
        code = data[pos]
        pos += 1
        codes[(length, code)] = (value, run)
        b = data[pos]
        pos += 1

    bitpos = pos * 8
    # the hardware decoder always peeks 8 bits ahead; the last code may end
    # closer than that to the end of the file
    data = bytes(data) + bytes(2)

    def bits(n):
        nonlocal bitpos
        v = 0
        for _ in range(n):
            byte = data[bitpos >> 3]
            v = v << 1 | (byte >> (7 - (bitpos & 7))) & 1
            bitpos += 1
        return v

    nibbles = []
    total = tiles * 64
    while len(nibbles) < total:
        # inline run?
        save = bitpos
        if bits(6) == 0x3F:
            run = bits(3) + 1
            nibbles += [bits(4)] * run
            continue
        bitpos = save
        code, length = 0, 0
        while True:
            code = code << 1 | bits(1)
            length += 1
            if (length, code) in codes:
                v, run = codes[(length, code)]
                nibbles += [v] * run
                break
            if length > 8:
                raise ValueError(f"bad Nemesis code at bit {save}")
    nibbles = nibbles[:total]

    out = bytearray()
    prev = 0
    for row in range(tiles * 8):
        r = 0
        for n in nibbles[row * 8:row * 8 + 8]:
            r = r << 4 | n
        if xor_mode:
            r ^= prev
            prev = r
        out += r.to_bytes(4, "big")
    return bytes(out)


def _code_lengths(freq, esc_weight):
    """Huffman code lengths for the symbols in freq plus an escape pseudo-symbol.
    Returns ({symbol: length}, escape length)."""
    import heapq
    heap = [(w, i, [s]) for i, (s, w) in enumerate(freq.items())]
    heap.append((esc_weight, len(heap), ["ESC"]))
    heapq.heapify(heap)
    depth = {s: 0 for s in freq}
    depth["ESC"] = 0
    n = len(heap)
    if n == 1:
        return {s: 1 for s in freq}, 1
    while len(heap) > 1:
        w1, _, a = heapq.heappop(heap)
        w2, _, b = heapq.heappop(heap)
        for s in a + b:
            depth[s] += 1
        heapq.heappush(heap, (w1 + w2, n, a + b))
        n += 1
    esc = depth.pop("ESC")
    return depth, esc


def _encode_stream(nibbles):
    """Runs (value, length 1..8) -> (code table bytes, bit string)."""
    runs = []
    i = 0
    while i < len(nibbles):
        v, n = nibbles[i], 1
        while n < 8 and i + n < len(nibbles) and nibbles[i + n] == v:
            n += 1
        runs.append((v, n))
        i += n
    freq = {}
    for r in runs:
        freq[r] = freq.get(r, 0) + 1
    # Codes may be at most 8 bits, and the 6-bit prefix %111111 is the inline
    # escape: the real codes, assigned canonically from 0, must leave the top
    # 1/64 of the code space free (escape length <= 6 guarantees that).
    coded = dict(freq)
    esc_weight = 1
    while True:
        lengths, esc = _code_lengths(coded, esc_weight)
        if lengths and max(lengths.values()) > 8:
            drop = min(coded, key=lambda s: (coded[s], s))   # rarest symbol goes inline
            esc_weight += coded.pop(drop)
            continue
        if esc > 6:
            esc_weight *= 2
            continue
        break
    order = sorted(lengths, key=lambda s: (lengths[s], s))
    codes, code, prev_len = {}, 0, 0
    for s in order:
        L = lengths[s]
        code <<= (L - prev_len)
        codes[s] = (code, L)
        code += 1
        prev_len = L
    assert code << (8 - prev_len) <= 252 if order else True
    table = bytearray()
    for v in range(16):
        entries = [(s, c) for s, c in codes.items() if s[0] == v]
        if not entries:
            continue
        table.append(0x80 | v)
        for (val, run), (c, L) in sorted(entries, key=lambda e: e[1][1]):
            table += bytes([((run - 1) << 4) | L, c])
    table.append(0xFF)
    bits = []
    for r in runs:
        if r in codes:
            c, L = codes[r]
            bits.append(format(c, f"0{L}b"))
        else:
            bits.append("111111" + format(r[1] - 1, "03b") + format(r[0], "04b"))
    return bytes(table), "".join(bits)


def compress(tiles):
    """Uncompressed 4bpp tiles -> Nemesis data (normal or XOR mode, whichever
    is smaller). Round-trips through decompress()."""
    assert len(tiles) % 32 == 0
    count = len(tiles) // 32
    best = None
    for xor_mode in (False, True):
        nibbles, prev = [], 0
        for row in range(count * 8):
            r = int.from_bytes(tiles[row * 4:row * 4 + 4], "big")
            if xor_mode:
                r, prev = r ^ prev, r
            nibbles += [(r >> (28 - 4 * k)) & 15 for k in range(8)]
        table, bits = _encode_stream(nibbles)
        bits += "0" * (-len(bits) % 8)
        stream = int(bits, 2).to_bytes(len(bits) // 8, "big") if bits else b""
        data = (count | (0x8000 if xor_mode else 0)).to_bytes(2, "big") + table + stream
        if best is None or len(data) < len(best):
            best = data
    assert decompress(best) == bytes(tiles), "Nemesis round trip failed"
    return best


if __name__ == "__main__":
    d = decompress(open(sys.argv[1], "rb").read())
    print(f"{len(d) // 32} tiles")
