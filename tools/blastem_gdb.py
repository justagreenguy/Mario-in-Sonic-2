#!/usr/bin/env python3
"""
blastem_gdb.py - drive BlastEm through its GDB remote stub for automated,
frame-accurate tests of the Sonic 2 build (no keyboard focus needed).

    from blastem_gdb import BlastEm
    emu = BlastEm("s2disasm-master/s2built.bin")       # launches blastem -D, connects
    emu.frames(600)                                     # run 600 frames, no input
    emu.frames(30, "right|c")                           # hold right + C for 30 frames
    print(hex(emu.r16(emu.sym("MainCharacter") + 8)))   # Mario's x_pos
    emu.screenshot("shot.png")                          # capture the BlastEm window
    emu.close()

How input works: a breakpoint sits on the `addq.w #2,a1` in ReadJoypads,
between reading pad 1 and pad 2, so it is hit exactly once per frame (in every
game mode). There the script overwrites Ctrl_1 held/press with its own
buttons, so the game sees exactly the scripted input for that frame.

Symbols come from s2disasm-master/s2.lst (build first).
Button names: up down left right b c a start (Genesis bit order 0..7).
"""

import ctypes
import os
import re
import socket
import struct
import subprocess
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BLASTEM = os.path.join(ROOT, "blastem-win64-1.0.0", "blastem.exe")
S2 = os.path.join(ROOT, "s2disasm-master")

BUTTONS = {"up": 0, "down": 1, "left": 2, "right": 3, "b": 4, "c": 5, "a": 6, "start": 7}


def buttons(spec):
    if not spec:
        return 0
    if isinstance(spec, int):
        return spec
    v = 0
    for name in spec.lower().replace("+", "|").split("|"):
        name = name.strip()
        if name:
            v |= 1 << BUTTONS[name]
    return v


class Listing:
    """Symbol and line-address lookup from the AS listing (s2.lst)."""

    def __init__(self, path):
        self.text = open(path, errors="replace").read()
        self.symbols = {}
        tail = self.text[self.text.rfind("Symbol Table"):] if "Symbol Table" in self.text else self.text[-4_000_000:]
        for m in re.finditer(r"\b([A-Za-z_][\w.]*) :\s+([0-9A-F]+) [A-Z-]", tail):
            self.symbols.setdefault(m.group(1), int(m.group(2), 16))

    def sym(self, name):
        if name not in self.symbols:
            raise KeyError(f"symbol {name} not in listing")
        return self.symbols[name]

    def addr_of(self, label, pattern):
        """Address of the first listing line after `label:` whose source matches regex `pattern`."""
        i = self.text.find(label + ":")
        for line in self.text[i:i + 20000].splitlines():
            m = re.match(r"\s*(?:\(\d+\))?\s*\d+/\s*([0-9A-F]+) :", line)
            if m and re.search(pattern, line):
                return int(m.group(1), 16)
        raise KeyError(f"no line matching {pattern} after {label}")

    def rts_after(self, label):
        """Address of the first rts after `label:` in the listing."""
        i = self.text.find(label + ":")
        for line in self.text[i:i + 20000].splitlines():
            m = re.match(r"\s*(?:\(\d+\))?\s*\d+/\s*([0-9A-F]+) :.*\brts\b", line)
            if m:
                return int(m.group(1), 16)
        raise KeyError(f"no rts after {label}")


class BlastEm:
    def __init__(self, rom, listing=None, port=1234, timeout=20):
        self.lst = Listing(listing or os.path.join(S2, "s2.lst"))
        self.proc = subprocess.Popen([BLASTEM, os.path.abspath(rom), "-D"],
                                     cwd=os.path.dirname(BLASTEM),
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + timeout
        while True:
            try:
                self.sock = socket.create_connection(("127.0.0.1", port), timeout=5)
                break
            except OSError:
                if time.time() > deadline:
                    self.proc.kill()
                    raise
                time.sleep(0.2)
        self.sock.settimeout(60)
        self.buf = b""
        self.frame_count = 0
        self.held = 0
        self.cmd("?")
        # ReadJoypads: lea (4 bytes), lea .l (6), bsr.s (2), then addq.w #2,a1
        self.joy_bp = (self.sym("ReadJoypads") + 12) & 0xFFFFFF
        if self.r16(self.joy_bp) != 0x5449:
            raise RuntimeError(f"expected addq.w #2,a1 at {self.joy_bp:x}")
        self.ctrl1 = self.sym("Ctrl_1") & 0xFFFFFF
        self.cmd(f"Z0,{self.joy_bp:x},2")

    # ---- symbols ----
    def sym(self, name):
        return self.lst.sym(name)

    # ---- GDB remote protocol ----
    def _send(self, data):
        pkt = b"$" + data.encode() + b"#" + f"{sum(data.encode()) & 0xFF:02x}".encode()
        self.sock.sendall(pkt)

    def _recv_packet(self):
        while True:
            m = re.search(rb"\$([^#]*)#([0-9a-fA-F]{2})", self.buf)
            if m:
                self.buf = self.buf[m.end():]
                self.sock.sendall(b"+")
                return m.group(1).decode()
            chunk = self.sock.recv(65536)
            if not chunk:
                raise ConnectionError("BlastEm closed the connection")
            self.buf += chunk

    def cmd(self, data):
        self._send(data)
        while True:
            r = self._recv_packet()
            # skip console output and stray stop replies unless we asked to run
            if r.startswith("O") and r != "OK":
                continue
            if data[0] not in "c?s" and (r.startswith("T") or r.startswith("S")) and len(r) >= 3:
                continue
            return r

    # ---- memory ----
    @staticmethod
    def _addr(a):
        return a & 0xFFFFFF

    def read(self, addr, n):
        out = b""
        addr = self._addr(addr)
        while n > 0:
            k = min(n, 0x80)                  # BlastEm's stub replies with at most 255 bytes
            r = self.cmd(f"m{addr:x},{k:x}")
            # An error reply is "Enn"; data is always 2*k hex digits (and may start
            # with "E", e.g. a byte of $EF).
            if len(r) != 2 * k:
                raise IOError(f"read {addr:x}: {r}")
            out += bytes.fromhex(r)
            addr += k
            n -= k
        return out

    def write(self, addr, data):
        r = self.cmd(f"M{self._addr(addr):x},{len(data):x}:{data.hex()}")
        if r != "OK":
            raise IOError(f"write {addr:x}: {r}")

    def r8(self, a):
        return self.read(a, 1)[0]

    def r16(self, a, signed=False):
        return struct.unpack(">h" if signed else ">H", self.read(a, 2))[0]

    def r32(self, a):
        return struct.unpack(">I", self.read(a, 4))[0]

    def w8(self, a, v):
        self.write(a, bytes([v & 0xFF]))

    def w16(self, a, v):
        self.write(a, struct.pack(">H", v & 0xFFFF))

    def regs(self):
        """d0-d7, a0-a7, sr, pc."""
        r = bytes.fromhex(self.cmd("g"))
        vals = struct.unpack(">18I", r[:72])
        names = [f"d{i}" for i in range(8)] + [f"a{i}" for i in range(8)] + ["sr", "pc"]
        return dict(zip(names, vals))

    # ---- execution ----
    def cont(self):
        """Continue until the next stop (breakpoint)."""
        return self.cmd("c")

    def frame(self, spec=None):
        """Run exactly one frame with the given buttons held for it."""
        held = buttons(spec)
        self.cont()
        press = held & ~self.held & 0xFF
        self.write(self.ctrl1, bytes([held, press]))
        self.held = held
        self.frame_count += 1

    # ---- free running (the user plays; we sample) ----
    def release_input(self):
        """Remove the per-frame input breakpoint and let the game run freely."""
        self.cmd(f"z0,{self.joy_bp:x},2")
        self._send("c")

    def pause(self):
        """Interrupt a free-running emulator (GDB Ctrl-C) and wait for it to stop."""
        self.sock.sendall(b"\x03")
        while True:
            r = self._recv_packet()
            if r[:1] in ("T", "S"):
                return r

    def resume(self):
        self._send("c")

    def frames(self, n, spec=None):
        for _ in range(n):
            self.frame(spec)

    def tap(self, spec, hold=4, after=8):
        """Press and release: hold for `hold` frames, then `after` idle frames."""
        self.frames(hold, spec)
        self.frames(after)

    # ---- screenshot of the BlastEm window ----
    def screenshot(self, path):
        user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
        user32.SetProcessDPIAware()
        hwnd = self._find_window()
        rect = (ctypes.c_long * 4)()
        user32.GetClientRect(hwnd, rect)
        pt = (ctypes.c_long * 2)(0, 0)
        user32.ClientToScreen(hwnd, pt)
        w, h = rect[2], rect[3]
        sdc = user32.GetDC(0)
        mdc = gdi32.CreateCompatibleDC(sdc)
        bmp = gdi32.CreateCompatibleBitmap(sdc, w, h)
        gdi32.SelectObject(mdc, bmp)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.15)
        gdi32.BitBlt(mdc, 0, 0, w, h, sdc, pt[0], pt[1], 0x00CC0020)
        bi = struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi32.GetDIBits(mdc, bmp, 0, h, buf, bi, 0)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(0, sdc)
        raw = bytearray()
        for y in range(h):
            raw.append(0)
            row = buf.raw[y * w * 4:(y + 1) * w * 4]
            for x in range(w):
                b, g, r = row[x * 4], row[x * 4 + 1], row[x * 4 + 2]
                raw += bytes((r, g, b))

        def chunk(tag, data):
            c = struct.pack(">I", len(data)) + tag + data
            return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

        png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        png += chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
        open(path, "wb").write(png)

    def _find_window(self):
        user32 = ctypes.windll.user32
        found = []
        pid = self.proc.pid
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def cb(hwnd, _):
            p = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
            if p.value == pid and user32.IsWindowVisible(hwnd):
                found.append(hwnd)
            return True

        user32.EnumWindows(WNDENUMPROC(cb), 0)
        if not found:
            raise RuntimeError("BlastEm window not found")
        return found[0]

    def close(self):
        try:
            self.sock.close()
        finally:
            self.proc.kill()


def boot_to_level(emu, player_option=0, settle=200, difficulty=None):
    """Title menu: MARIO GAME (player_option 0) or LUIGI GAME (1) -> Emerald Hill 1.
    With difficulty (0 = HYBRID MODE, 1 = MARIO MODE), first goes Title -> OPTIONS,
    sets the DIFFICULTY box, START on the sound test (back to the SEGA screen),
    then picks the character on the title. Returns once the level is running
    and the title card is gone."""
    gm = lambda: emu.r8(emu.sym("Game_Mode"))

    def wait_title():
        for _ in range(1500):
            if gm() == 4:
                break
            emu.frame()
        emu.frames(420)                  # title intro must finish before the menu takes input

    wait_title()
    if difficulty is not None:
        emu.tap("down"); emu.tap("down"); emu.tap("start")
        for _ in range(200):
            if gm() == 0x24:
                break
            emu.frame()
        emu.frames(60)                   # options screen fade-in
        for _ in range(8):
            if emu.r16(emu.sym("Difficulty_option")) == difficulty:
                break
            emu.tap("right")
        if emu.r16(emu.sym("Difficulty_option")) != difficulty:
            raise RuntimeError("could not select the difficulty")
        emu.tap("up")                    # box 0 -> box 2 (sound test): START there returns to SEGA
        emu.tap("start")
        for _ in range(200):
            if gm() != 0x24:
                break
            emu.frame()
        wait_title()
    for _ in range(player_option):
        emu.tap("down")
    emu.tap("start")
    for _ in range(400):
        if gm() == 0x0C:
            break
        emu.frame()
    emu.frames(settle)                   # title card


if __name__ == "__main__":
    rom = sys.argv[1] if len(sys.argv) > 1 else os.path.join(S2, "s2built.bin")
    emu = BlastEm(rom)
    emu.frames(120)
    print("frames:", emu.frame_count, "Game_Mode:", hex(emu.r8(emu.sym("Game_Mode"))))
    emu.close()
