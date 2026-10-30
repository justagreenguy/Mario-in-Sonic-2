#!/usr/bin/env python3
"""analyze_session.py - summarise tools/out/session.csv from watch_session.py.

Reports: route, top speeds, loop attempts (ground angle sweeping past $40/$80/$C0),
detachments from walls/ceilings (S2 SlopeRepel), hurts/deaths, and stalls.
    python -I tools/analyze_session.py [csv] [--dump START END]
"""
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
path = os.path.join(HERE, "out", "session.csv")
args = sys.argv[1:]
if args and not args[0].startswith("--"):
    path = args.pop(0)
rows = [{k: (v if k == "zoneact" else float(v)) for k, v in r.items()} for r in csv.DictReader(open(path))]
for r in rows:
    for k in r:
        if k not in ("zoneact", "t"):
            r[k] = int(r[k])

if args and args[0] == "--dump":
    a, b = int(args[1]), int(args[2])
    for i, r in enumerate(rows[a:b], a):
        print(f"{i:4d} t={r['t']:6.2f} x={r['x']:04X} y={r['y']:04X} in={r['inertia']:5d} xv={r['x_vel']:5d} "
              f"yv={r['y_vel']:5d} ang={r['angle']:02X} st={r['status']:02X} rt={r['routine']} "
              f"ml={r['move_lock']} PS={r['Player_State']} XS={r['Player_X_Speed']} ctrl={r['ctrl']:02X} anim={r['anim']:02X}")
    sys.exit()

on_ground = lambda r: not (r["status"] & 2)
print(f"{len(rows)} samples over {rows[-1]['t']:.1f}s, zones {sorted(set(r['zoneact'] for r in rows))}")
print(f"x range {min(r['x'] for r in rows):04X}-{max(r['x'] for r in rows):04X}")
print(f"max |inertia| {max(abs(r['inertia']) for r in rows)}, max x_vel {max(r['x_vel'] for r in rows)}, "
      f"min y_vel {min(r['y_vel'] for r in rows)}")

# Loop / wall-run segments: consecutive on-ground samples with steep angles
segs, cur = [], []
for i, r in enumerate(rows):
    steep = on_ground(r) and 0x30 <= r["angle"] <= 0xD0
    if steep:
        cur.append(i)
    elif cur:
        segs.append(cur); cur = []
if cur:
    segs.append(cur)
print("\nsteep on-ground segments (walls/ceilings/loops):")
for s in segs:
    angs = [rows[i]["angle"] for i in s]
    upside = any(0x60 <= a <= 0xA0 for a in angs)
    r0, r1 = rows[s[0]], rows[s[-1]]
    nxt = rows[s[-1] + 1] if s[-1] + 1 < len(rows) else r1
    how = "detached (in air)" if nxt["status"] & 2 else "back on floor"
    print(f"  samples {s[0]}-{s[-1]} x {r0['x']:04X}->{r1['x']:04X} angles {[f'{a:02X}' for a in angs]}"
          f" inertia {r0['inertia']}->{r1['inertia']} {'UPSIDE-DOWN' if upside else ''} then {how}")

print("\nevents:")
prev = rows[0]
for i, r in enumerate(rows[1:], 1):
    if r["routine"] == 4 and prev["routine"] != 4:
        print(f"  {i}: hurt at x={r['x']:04X}")
    if r["routine"] == 6 and prev["routine"] != 6:
        print(f"  {i}: died at x={r['x']:04X}")
    if r["move_lock"] and not prev["move_lock"]:
        print(f"  {i}: S2 slope slide-back/detach (move_lock) at x={r['x']:04X} ang={r['angle']:02X} inertia={r['inertia']}")
    if r["Mario_LaunchFlag"] and not prev["Mario_LaunchFlag"]:
        print(f"  {i}: launched by S2 (spring/ramp) at x={r['x']:04X} y_vel={r['y_vel']}")
    if r["zoneact"] != prev["zoneact"]:
        print(f"  {i}: zone/act -> {r['zoneact']}")
    prev = r
