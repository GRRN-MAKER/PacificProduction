#!/usr/bin/env python3
"""Generate placeholder PNG assets for MSIX packaging.

Used by the GitHub Actions workflow when no real assets/ directory
exists. Creates minimal valid PNGs at the sizes required by
AppxManifest.xml.

Usage:
    python build/generate_store_assets.py <output_dir>

Creates:
    StoreLogo.png           (50x50)
    Square44x44Logo.png     (44x44)
    Square150x150Logo.png   (150x150)
    Wide310x150Logo.png     (310x150)
    Square310x310Logo.png   (310x310)
    SplashScreen.png        (620x300)
"""

import struct
import sys
import os
import zlib


def make_png(width: int, height: int, r: int = 27, g: int = 79, b: int = 114) -> bytes:
    """Create a minimal solid-color PNG file in memory.

    Default color: #1B4F72 (Pacific navy blue).
    """
    # IHDR
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)

    # IDAT — raw pixel rows
    raw = b""
    for _ in range(height):
        raw += b"\x00"  # filter byte (None)
        raw += bytes([r, g, b]) * width
    compressed = zlib.compress(raw)
    idat = _chunk(b"IDAT", compressed)

    # IEND
    iend = _chunk(b"IEND", b"")

    # PNG signature + chunks
    return b"\x89PNG\r\n\x1a\n" + ihdr + idat + iend


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a PNG chunk with CRC."""
    raw = chunk_type + data
    return struct.pack(">I", len(data)) + raw + struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)


ASSETS = {
    "StoreLogo.png":          (50, 50),
    "Square44x44Logo.png":    (44, 44),
    "Square150x150Logo.png":  (150, 150),
    "Wide310x150Logo.png":    (310, 150),
    "Square310x310Logo.png":  (310, 310),
    "SplashScreen.png":       (620, 300),
}


def main():
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "assets"
    os.makedirs(output_dir, exist_ok=True)

    for name, (w, h) in ASSETS.items():
        path = os.path.join(output_dir, name)
        png = make_png(w, h)
        with open(path, "wb") as f:
            f.write(png)
        print(f"  ✅ {name} ({w}x{h}) — {len(png)} bytes")

    print(f"\nAll assets generated in {output_dir}/")
    print("⚠️  These are solid-color placeholders — replace with real branding before Store submission!")


if __name__ == "__main__":
    main()
