"""Generate the ambient background scenes in static/img/bg/.

Run:  python3 tools/make_backgrounds.py
The site shows these behind the content while you scroll. To use your own
4K photos instead, just drop JPG/WEBP files into static/img/bg/ and list
them in the BG_SCENES block in templates/base.html.
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, H = 2560, 1440
OUT = os.path.join(os.path.dirname(__file__), "..", "static", "img", "bg")
os.makedirs(OUT, exist_ok=True)
random.seed(7)
np.random.seed(7)


def base(tint=(10, 10, 14)):
    return Image.new("RGB", (W, H), tint)


def vignette(img, strength=0.75):
    y, x = np.mgrid[0:H, 0:W]
    d = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2)
    m = np.clip(1 - strength * (d ** 2), 0, 1)
    a = np.asarray(img).astype(np.float32) * m[..., None]
    return Image.fromarray(a.clip(0, 255).astype(np.uint8))


def glow(layer, radius):
    return layer.filter(ImageFilter.GaussianBlur(radius))


def add(img, layer, alpha=1.0):
    a = np.asarray(img).astype(np.float32)
    b = np.asarray(layer).astype(np.float32) * alpha
    return Image.fromarray((a + b).clip(0, 255).astype(np.uint8))


def grain(img, amount=6):
    a = np.asarray(img).astype(np.float32)
    n = np.random.normal(0, amount, (H, W, 1))
    return Image.fromarray((a + n).clip(0, 255).astype(np.uint8))


def save(img, name):
    # lift the highlights so the scene reads through the dark overlays
    a = np.asarray(img).astype(np.float32)
    a = (a * 1.75).clip(0, 255)
    img = grain(vignette(Image.fromarray(a.astype(np.uint8)), 0.6))
    img.save(os.path.join(OUT, name + ".jpg"), quality=82, optimize=True, progressive=True)
    print("wrote", name)


# ---------------------------------------------------------------- 1. neural
def neural():
    img = base((9, 9, 13))
    # soft aurora clouds
    cloud = Image.new("RGB", (W, H), 0)
    d = ImageDraw.Draw(cloud)
    for _ in range(6):
        cx, cy = random.randint(0, W), random.randint(0, H)
        r = random.randint(300, 700)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(38, 38, 48))
    img = add(img, glow(cloud, 260), 0.9)

    pts = [(random.uniform(0, W), random.uniform(0, H), random.uniform(0.3, 1.0)) for _ in range(160)]
    for depth_lo, depth_hi, blur, bright in [(0.3, 0.55, 14, 0.5), (0.55, 0.8, 5, 0.8), (0.8, 1.01, 0, 1.0)]:
        layer = Image.new("RGB", (W, H), 0)
        d = ImageDraw.Draw(layer)
        sel = [p for p in pts if depth_lo <= p[2] < depth_hi]
        for i, (x1, y1, z1) in enumerate(sel):
            for (x2, y2, z2) in sel[i + 1:]:
                dist = math.hypot(x1 - x2, y1 - y2)
                if dist < 320 * z1:
                    v = int(90 * (1 - dist / (320 * z1)) * bright)
                    d.line((x1, y1, x2, y2), fill=(v, v, v + 8), width=2)
        for (x, y, z) in sel:
            r = 3 + 6 * z
            v = int(230 * bright)
            d.ellipse((x - r, y - r, x + r, y + r), fill=(v, v, v))
        halo = glow(layer, 30)
        img = add(img, halo, 0.9)
        img = add(img, glow(layer, blur) if blur else layer, 0.8)
    save(img, "neural")


# ---------------------------------------------------------------- 2. circuit
def circuit():
    img = base((8, 8, 11))
    layer = Image.new("RGB", (W, H), 0)
    d = ImageDraw.Draw(layer)
    grid = 64
    for _ in range(140):
        x = random.randrange(0, W, grid)
        y = random.randrange(0, H, grid)
        length = random.randint(3, 14)
        pts = [(x, y)]
        for _ in range(length):
            dx, dy = random.choice([(grid, 0), (-grid, 0), (0, grid), (0, -grid), (grid, grid), (-grid, -grid)])
            x, y = x + dx, y + dy
            pts.append((x, y))
        v = random.randint(40, 110)
        d.line(pts, fill=(v, v, v + 6), width=3, joint="curve")
        for (px, py) in (pts[0], pts[-1]):
            d.ellipse((px - 9, py - 9, px + 9, py + 9), outline=(v + 60, v + 60, v + 66), width=4, fill=(0, 0, 0))
    # hot traces
    hot = Image.new("RGB", (W, H), 0)
    dh = ImageDraw.Draw(hot)
    for _ in range(14):
        x = random.randrange(0, W, grid)
        y = random.randrange(0, H, grid)
        pts = [(x, y)]
        for _ in range(random.randint(4, 10)):
            dx, dy = random.choice([(grid, 0), (0, grid), (grid, grid), (-grid, 0)])
            x, y = x + dx, y + dy
            pts.append((x, y))
        dh.line(pts, fill=(235, 235, 245), width=3)
        px, py = pts[-1]
        dh.ellipse((px - 10, py - 10, px + 10, py + 10), fill=(255, 255, 255))
    img = add(img, layer, 0.9)
    img = add(img, glow(hot, 24), 0.9)
    img = add(img, hot, 0.9)
    save(img, "circuit")


# ---------------------------------------------------------------- 3. mountains (Kurdistan ridges + sun)
def mountains():
    img = base((10, 10, 13))
    sun = Image.new("RGB", (W, H), 0)
    ds = ImageDraw.Draw(sun)
    cx, cy = W * 0.62, H * 0.42
    ds.ellipse((cx - 170, cy - 170, cx + 170, cy + 170), fill=(255, 250, 240))
    img = add(img, glow(sun, 260), 0.55)
    img = add(img, glow(sun, 40), 0.55)
    # 21 subtle rays (Kurdish sun)
    rays = Image.new("RGB", (W, H), 0)
    dr = ImageDraw.Draw(rays)
    for i in range(21):
        a = i * 2 * math.pi / 21
        dr.line((cx + math.cos(a) * 200, cy + math.sin(a) * 200, cx + math.cos(a) * 900, cy + math.sin(a) * 900), fill=(60, 58, 52), width=3)
    img = add(img, glow(rays, 8), 0.5)
    # ridges
    xs = np.arange(W)
    for k, (yb, amp, shade) in enumerate([(0.55, 140, 60), (0.66, 120, 42), (0.78, 100, 28), (0.9, 80, 16)]):
        y = H * yb + sum(amp / (j + 1) * np.sin(xs / (420 / (j + 1)) + random.uniform(0, 6) + k) for j in range(4))
        y += np.random.normal(0, 1.5, W).cumsum() * 0.15
        layer = Image.new("RGB", (W, H), 0)
        dl = ImageDraw.Draw(layer)
        poly = [(int(x), int(v)) for x, v in zip(xs[::4], y[::4])] + [(W, H), (0, H)]
        dl.polygon(poly, fill=(shade, shade, shade + 4))
        mist = glow(layer, 60)
        a = np.asarray(img).astype(np.float32)
        b = np.asarray(layer).astype(np.float32)
        m = (b.sum(axis=2) > 0)[..., None]
        a = np.where(m, b, a) + np.asarray(mist).astype(np.float32) * 0.25
        img = Image.fromarray(a.clip(0, 255).astype(np.uint8))
    save(img, "mountains")


# ---------------------------------------------------------------- 4. data streams
def streams():
    img = base((9, 9, 12))
    layer = Image.new("RGB", (W, H), 0)
    d = ImageDraw.Draw(layer)
    xs = np.arange(0, W + 20, 20)
    for i in range(70):
        phase = random.uniform(0, 10)
        amp = random.uniform(60, 220)
        yb = H * 0.15 + i * (H * 0.7 / 70)
        y = yb + amp * np.sin(xs / random.uniform(300, 700) + phase) + 40 * np.sin(xs / 90 + phase * 2)
        v = random.randint(30, 120)
        d.line(list(zip(xs.tolist(), y.tolist())), fill=(v, v, v + 8), width=2)
    bright = Image.new("RGB", (W, H), 0)
    db = ImageDraw.Draw(bright)
    for _ in range(8):
        phase = random.uniform(0, 10)
        amp = random.uniform(80, 200)
        yb = random.uniform(H * 0.2, H * 0.8)
        y = yb + amp * np.sin(xs / random.uniform(300, 700) + phase)
        db.line(list(zip(xs.tolist(), y.tolist())), fill=(235, 235, 245), width=3)
    img = add(img, glow(layer, 3), 0.9)
    img = add(img, glow(bright, 30), 0.8)
    img = add(img, bright, 0.7)
    save(img, "streams")


if __name__ == "__main__":
    neural()
    circuit()
    mountains()
    streams()
