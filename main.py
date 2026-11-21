#!/usr/bin/env python3
"""THE ANTI-GRAVITY TEAPOT — a catalogue photograph of an impossible gadget.

A white porcelain teapot, studio product shot, pouring tea UPWARD in a
golden arc into a small cup floating above it. Drawn entirely with code:
no network, no assets, no fonts — just an RGB buffer, a hand-rolled PNG
writer and a tiny 5x7 bitmap font for the brand label.

Usage: python3 main.py [output-path]   (default: /output/entry.png)
"""

import math
import os
import struct
import sys
import zlib

W = 1024
H = 1024

# ---------------------------------------------------------------- buffer

buf = bytearray(W * H * 3)


def _clamp(v):
    return 0 if v < 0 else (255 if v > 255 else v)


def _put(x, y, r, g, b, a=255):
    if x < 0 or x >= W or y < 0 or y >= H or a <= 0:
        return
    i = (y * W + x) * 3
    if a >= 255:
        buf[i] = r
        buf[i + 1] = g
        buf[i + 2] = b
    else:
        inv = 255 - a
        buf[i] = (r * a + buf[i] * inv) // 255
        buf[i + 1] = (g * a + buf[i + 1] * inv) // 255
        buf[i + 2] = (b * a + buf[i + 2] * inv) // 255


def _mix(c0, c1, t):
    return tuple(int(c0[k] + (c1[k] - c0[k]) * t) for k in range(3))


# ------------------------------------------------------------ primitives


def vgrad(x0, y0, x1, y1, top, bottom):
    """Vertical gradient rectangle."""
    for y in range(max(0, y0), min(H, y1)):
        t = (y - y0) / max(1, (y1 - y0 - 1))
        c = _mix(top, bottom, t)
        i = (y * W + max(0, x0)) * 3
        for x in range(max(0, x0), min(W, x1)):
            buf[i] = c[0]
            buf[i + 1] = c[1]
            buf[i + 2] = c[2]
            i += 3


def ellipse(cx, cy, rx, ry, color, a=255, clip=None):
    """Filled ellipse, optionally clipped to a second ellipse.

    clip is (ccx, ccy, crx, cry); only pixels inside it are painted.
    """
    if rx <= 0 or ry <= 0:
        return
    r, g, b = color
    for y in range(int(cy - ry), int(cy + ry) + 1):
        if y < 0 or y >= H:
            continue
        dy = (y - cy) / ry
        if abs(dy) > 1:
            continue
        dx = rx * math.sqrt(1 - dy * dy)
        xa, xb = int(cx - dx), int(cx + dx)
        if clip is not None:
            ccx, ccy, crx, cry = clip
            dyc = (y - ccy) / cry
            if abs(dyc) > 1:
                continue
            dxc = crx * math.sqrt(1 - dyc * dyc)
            xa = max(xa, int(ccx - dxc))
            xb = min(xb, int(ccx + dxc))
        for x in range(max(0, xa), min(W - 1, xb) + 1):
            _put(x, y, r, g, b, a)


def disc(cx, cy, r, color, a=255):
    ellipse(cx, cy, r, r, color, a)


def poly(points, color, a=255):
    """Scanline polygon fill (non-zero, works for convex and concave)."""
    if len(points) < 3:
        return
    r, g, b = color
    ys = [p[1] for p in points]
    ymin, ymax = int(max(0, min(ys))), int(min(H - 1, max(ys)))
    n = len(points)
    for y in range(ymin, ymax + 1):
        xs = []
        for k in range(n):
            x0, y0 = points[k]
            x1, y1 = points[(k + 1) % n]
            if (y0 <= y < y1) or (y1 <= y < y0):
                t = (y - y0) / (y1 - y0)
                xs.append(x0 + t * (x1 - x0))
        xs.sort()
        for k in range(0, len(xs) - 1, 2):
            xa, xb = int(xs[k]), int(xs[k + 1])
            for x in range(max(0, xa), min(W - 1, xb) + 1):
                _put(x, y, r, g, b, a)


def thick_line(x0, y0, x1, y1, w, color, a=255):
    steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    for s in range(steps + 1):
        t = s / steps
        disc(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, w / 2, color, a)


def bez(p0, p1, p2, t):
    u = 1 - t
    return (
        u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
        u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
    )


def taper_stroke(p0, p1, p2, w0, w1, color, a=255, steps=90):
    """A quadratic-bezier stroke whose width tapers from w0 to w1."""
    for s in range(steps + 1):
        t = s / steps
        x, y = bez(p0, p1, p2, t)
        disc(x, y, (w0 + (w1 - w0) * t) / 2, color, a)


def soft_shadow(cx, cy, rx, ry, peak=55):
    """Smooth radial falloff: a soft, diffuse contact shadow."""
    for y in range(int(cy - ry), int(cy + ry) + 1):
        if y < 0 or y >= H:
            continue
        for x in range(int(cx - rx), int(cx + rx) + 1):
            if x < 0 or x >= W:
                continue
            d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if d < 1:
                a = int(peak * (1 - d) ** 1.6)
                if a > 0:
                    _put(x, y, 60, 52, 44, a)


# ------------------------------------------------------------------ font
# Hand-built 5x7 bitmap glyphs, one row per string, '#' = ink.

GLYPHS = {
    "U": (
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        " ### ",
    ),
    "P": (
        "#### ",
        "#   #",
        "#   #",
        "#### ",
        "#    ",
        "#    ",
        "#    ",
    ),
    "O": (
        " ### ",
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        "#   #",
        " ### ",
    ),
    "R": (
        "#### ",
        "#   #",
        "#   #",
        "#### ",
        "# #  ",
        "#  # ",
        "#   #",
    ),
}


def draw_text(text, cx, top, scale, color):
    gw, gh = 5 * scale, 7 * scale
    gap = scale
    total = len(text) * gw + (len(text) - 1) * gap
    x = cx - total // 2
    for ch in text:
        glyph = GLYPHS.get(ch)
        if glyph is None:
            x += gw + gap
            continue
        for row_i, row in enumerate(glyph):
            for col_i, cell in enumerate(row):
                if cell == "#":
                    for dy in range(scale):
                        for dx in range(scale):
                            _put(x + col_i * scale + dx,
                                 top + row_i * scale + dy,
                                 color[0], color[1], color[2])
        x += gw + gap


# ------------------------------------------------------------------ scene

# Palette
PORCELAIN = (250, 249, 246)
PORCELAIN_DARK = (214, 208, 200)
PORCELAIN_LINE = (168, 160, 150)
TEA = (196, 138, 44)
TEA_LIGHT = (232, 181, 90)
INK = (58, 54, 50)


def draw():
    # 1. Studio backdrop: warm-grey vertical gradient + soft glow.
    vgrad(0, 0, W, H, (236, 232, 226), (198, 192, 184))
    for k in range(5, 0, -1):
        f = k / 5
        ellipse(512, 470, 460 * f, 380 * f, (255, 253, 248),
                int(26 * (1 - f * 0.7)))

    # 2. Floor shadow under the teapot.
    soft_shadow(512, 872, 265, 34, 66)

    # 3. Handle (behind the body so its roots tuck under it).
    taper_stroke((688, 596), (806, 620), (806, 730), 40, 40,
                 (226, 221, 214))
    taper_stroke((688, 742), (806, 742), (806, 730), 40, 40,
                 (226, 221, 214))
    taper_stroke((700, 612), (788, 626), (788, 720), 12, 12,
                 (180, 172, 162), 70)

    # 4. Spout, rising up-left from the body to its tip.
    taper_stroke((352, 648), (272, 560), (302, 436), 74, 26, PORCELAIN)
    taper_stroke((330, 620), (288, 552), (306, 452), 20, 10,
                 (255, 255, 255), 150)
    ellipse(302, 436, 15, 11, (228, 222, 214))          # spout tip rim
    ellipse(302, 436, 9, 6, (120, 110, 100))            # spout opening

    # 5. Body: porcelain ellipse with a vertical gradient.
    body = (512, 664, 212, 152)
    for y in range(body[1] - body[3], body[1] + body[3] + 1):
        if y < 0 or y >= H:
            continue
        dy = (y - body[1]) / body[3]
        if abs(dy) > 1:
            continue
        dx = body[2] * math.sqrt(1 - dy * dy)
        t = (y - (body[1] - body[3])) / (2 * body[3])
        c = _mix((255, 255, 255), (216, 210, 202), t)
        for x in range(max(0, int(body[0] - dx)), min(W - 1, int(body[0] + dx)) + 1):
            _put(x, y, c[0], c[1], c[2])
    # Body shading, clipped to the body ellipse: light left, shadow right.
    ellipse(398, 650, 98, 128, (255, 255, 255), 80, clip=body)
    ellipse(662, 676, 70, 120, (146, 136, 126), 38, clip=body)
    # Foot ring.
    ellipse(512, 806, 100, 20, (190, 182, 172))
    ellipse(512, 802, 100, 20, (226, 220, 212))

    # 6. Lid: flattened dome + knob.
    ellipse(512, 528, 132, 56, (252, 251, 248))
    ellipse(512, 534, 132, 50, (222, 216, 208), 50)
    ellipse(512, 520, 118, 44, (255, 255, 255), 110)
    disc(512, 470, 24, (244, 242, 238))
    disc(506, 463, 9, (255, 255, 255), 170)

    # 7. Tea arc: from the spout tip UP and over into the floating cup.
    arc0, arc1, arc2 = (306, 432), (430, 232), (600, 316)
    taper_stroke(arc0, arc1, arc2, 17, 10, TEA, steps=110)
    taper_stroke((312, 428), (430, 244), (592, 312), 6, 4, TEA_LIGHT,
                 steps=110)
    # Droplets escaping the arc.
    for t, off, r in ((0.30, 20, 7), (0.52, -16, 6), (0.72, 18, 5)):
        x, y = bez(arc0, arc1, arc2, t)
        disc(x + off, y - 6, r, TEA)
        disc(x + off - 2, y - 8, max(2, r // 3), TEA_LIGHT)

    # 8. The floating cup — the one accessory — above the teapot.
    # Cup shadow on nothing: it floats, so only a whisper of shade below.
    cup_top, cup_bot = 268, 384
    poly([(516, cup_top), (684, cup_top), (660, cup_bot), (540, cup_bot)],
         PORCELAIN)
    ellipse(600, cup_top, 84, 13, (255, 255, 255))
    ellipse(600, cup_top, 76, 10, TEA)                 # tea surface
    ellipse(600, cup_top, 76, 10, TEA_LIGHT, 90)
    ellipse(600, cup_bot, 60, 12, (222, 216, 208))
    # Cup shading: light left, shadow right, clipped to the cup body.
    poly([(516, cup_top), (560, cup_top), (552, cup_bot), (540, cup_bot)],
         (255, 255, 255), 130)
    poly([(652, cup_top), (684, cup_top), (660, cup_bot), (648, cup_bot)],
         (150, 140, 130), 70)
    # Cup handle (right side).
    taper_stroke((682, 300), (726, 306), (726, 348), 15, 15, PORCELAIN)
    taper_stroke((682, 352), (726, 352), (726, 348), 15, 15, PORCELAIN)
    # Cup rim line.
    thick_line(516, cup_top, 684, cup_top, 3, PORCELAIN_LINE, 120)

    # 9. Brand label on the teapot body.
    draw_text("UPPOUR", 512, 668, 3, INK)


# -------------------------------------------------------------------- png


def _chunk(tag, data):
    out = struct.pack(">I", len(data)) + tag + data
    out += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return out


def write_png(path):
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        raw += buf[y * W * 3:(y + 1) * W * 3]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n"
    png += _chunk(b"IHDR", ihdr)
    png += _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += _chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "/output/entry.png"
    draw()
    size = write_png(out)
    print(f"wrote {out}: {W}x{H}, {size} bytes")


if __name__ == "__main__":
    main()
