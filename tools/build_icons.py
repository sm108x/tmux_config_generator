#!/usr/bin/env python3
"""Regenerate the application icon (SVG source, PNG sizes, .ico, .icns).

Needs Inkscape on PATH. Run from the repository root:
    python3 tools/build_icons.py
"""

import math
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

APP_ID = "io.github.sm108x.TmuxConfigGenerator"
DATA = Path(__file__).resolve().parent.parent / "tmux_config_generator" / "data" / "icons"
PNG_SIZES = [16, 24, 32, 48, 64, 128, 256, 512]


def gear_path(cx, cy, r_out, r_in, teeth, hole):
    pts = []
    for i in range(teeth * 4):
        a = 2 * math.pi * i / (teeth * 4) - math.pi / 2
        r = r_out if i % 4 in (1, 2) else r_in
        pts.append(f"{cx + r * math.cos(a):.2f},{cy + r * math.sin(a):.2f}")
    outer = "M" + " L".join(pts) + " Z"
    # Inner hole as a reversed circle so fill-rule evenodd cuts it out.
    circle = (f"M{cx + hole:.2f},{cy:.2f} A{hole},{hole} 0 1,0 {cx - hole:.2f},{cy:.2f} "
              f"A{hole},{hole} 0 1,0 {cx + hole:.2f},{cy:.2f} Z")
    return outer + " " + circle


SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#2b3245"/>
      <stop offset="1" stop-color="#171b26"/>
    </linearGradient>
    <linearGradient id="gear" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ffc24d"/>
      <stop offset="1" stop-color="#f08c1a"/>
    </linearGradient>
  </defs>
  <!-- terminal body -->
  <rect x="8" y="12" width="112" height="104" rx="20" fill="url(#bg)"/>
  <rect x="8.5" y="12.5" width="111" height="103" rx="19.5" fill="none" stroke="#000" stroke-opacity=".35"/>
  <!-- pane splits -->
  <path d="M66 22 V88 M66 55 H110" stroke="#3ecf6e" stroke-width="3" stroke-linecap="round"/>
  <!-- prompt in the main pane -->
  <path d="M22 34 L32 42 L22 50" fill="none" stroke="#e8ecf4" stroke-width="5"
        stroke-linecap="round" stroke-linejoin="round"/>
  <rect x="36" y="46" width="16" height="5" rx="2" fill="#e8ecf4"/>
  <rect x="22" y="62" width="30" height="4" rx="2" fill="#8792a8"/>
  <rect x="22" y="72" width="22" height="4" rx="2" fill="#8792a8"/>
  <rect x="76" y="32" width="24" height="4" rx="2" fill="#8792a8"/>
  <!-- status line -->
  <path d="M8 94 H120 V96 A20 20 0 0 1 100 116 H28 A20 20 0 0 1 8 96 Z" fill="#3ecf6e"/>
  <rect x="18" y="100" width="18" height="7" rx="2" fill="#15351f"/>
  <rect x="40" y="100" width="12" height="7" rx="2" fill="#15351f" fill-opacity=".45"/>
  <!-- settings gear -->
  <path d="{gear_path(92, 74, 23, 17.5, 8, 7)}" fill="url(#gear)" fill-rule="evenodd"
        stroke="#7a4200" stroke-width="2" stroke-linejoin="round"/>
</svg>
"""


def render_png(svg: Path, size: int, out: Path):
    subprocess.run(["inkscape", str(svg), "--export-type=png",
                    f"--export-filename={out}", f"--export-width={size}",
                    f"--export-height={size}"], check=True, capture_output=True)


def write_ico(pngs: dict, out: Path):
    sizes = [s for s in (16, 24, 32, 48, 64, 128, 256) if s in pngs]
    data = [pngs[s].read_bytes() for s in sizes]
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for s, d in zip(sizes, data):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32,
                               len(d), offset)
        offset += len(d)
    out.write_bytes(header + entries + b"".join(data))


def write_icns(pngs: dict, out: Path):
    types = [("icp4", 16), ("icp5", 32), ("icp6", 64), ("ic07", 128),
             ("ic08", 256), ("ic09", 512)]
    body = b""
    for ostype, s in types:
        d = pngs[s].read_bytes()
        body += ostype.encode() + struct.pack(">I", len(d) + 8) + d
    out.write_bytes(b"icns" + struct.pack(">I", len(body) + 8) + body)


def main():
    if not shutil.which("inkscape"):
        raise SystemExit("inkscape is required")
    DATA.mkdir(parents=True, exist_ok=True)
    svg = DATA / "hicolor" / "scalable" / "apps" / f"{APP_ID}.svg"
    svg.parent.mkdir(parents=True, exist_ok=True)
    svg.write_text(SVG)
    pngs = {}
    for s in PNG_SIZES:
        out = DATA / "hicolor" / f"{s}x{s}" / "apps" / f"{APP_ID}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        render_png(svg, s, out)
        pngs[s] = out
    write_ico(pngs, DATA / f"{APP_ID}.ico")
    write_icns(pngs, DATA / f"{APP_ID}.icns")
    print("icons written to", DATA)


if __name__ == "__main__":
    main()
