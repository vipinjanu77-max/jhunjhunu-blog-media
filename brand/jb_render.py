#!/usr/bin/env python3
"""Jhunjhunu Blog fact-card renderer (v2).

Usage:  python3 jb_render.py spec.json      (spec may be one object or a list)

Spec fields:
  out        output path, .jpg
  size       "feed" (1080x1350) or "story" (1080x1920)
  theme      "maroon" (default) or "cream"
  eyebrow    category line, e.g. "Jhunjhunu Itihaas"
  big        optional big highlight, e.g. "1967" or "PVC"
  headline   Hindi or Hinglish headline (string)
  body       2-5 short lines of fact text (string, may contain \n)
  source     short source line, e.g. "Ramakrishna Math, Khetri (khetri.rkmm.org)"
  fonts_dir  default: folder of this script
  logo       default: jb-mark.png next to this script

Fonts needed in fonts_dir: DMSerifDisplay-Regular, Poppins-SemiBold, Poppins-Regular,
Mukta-ExtraBold, Mukta-SemiBold, Mukta-Regular (.ttf). If missing, they are fetched
from github.com/google/fonts with a sparse git clone.
Devanagari is shaped with raqm; the script refuses to render Hindi without it.
"""
import json, os, re, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont, features

HERE = os.path.dirname(os.path.abspath(__file__))
MAROON = (0x72, 0x04, 0x12)
MUSTARD = (0xD6, 0x8B, 0x1F)
CREAM = (0xFE, 0xFD, 0xF5)
INK = (0x1F, 0x1F, 0x1F)
DEVA = re.compile(r"[ऀ-ॿ]")
SIZES = {"feed": (1080, 1350), "story": (1080, 1920)}
FONTS = {
    "DMSerifDisplay-Regular.ttf": "ofl/dmserifdisplay",
    "Poppins-SemiBold.ttf": "ofl/poppins",
    "Poppins-Regular.ttf": "ofl/poppins",
    "Mukta-ExtraBold.ttf": "ofl/mukta",
    "Mukta-SemiBold.ttf": "ofl/mukta",
    "Mukta-Regular.ttf": "ofl/mukta",
}
THEMES = {
    "maroon": dict(bg=MAROON, head=CREAM, body=(0xF3, 0xE6, 0xD8), accent=MUSTARD, muted=(0xD9, 0xB8, 0xB0)),
    "cream": dict(bg=CREAM, head=MAROON, body=INK, accent=MUSTARD, muted=(0x6B, 0x5E, 0x58)),
}


def ensure_fonts(d):
    missing = [f for f in FONTS if not os.path.exists(os.path.join(d, f))]
    if not missing:
        return
    tmp = tempfile.mkdtemp()
    subprocess.run(["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--sparse",
                    "https://github.com/google/fonts", tmp], check=True)
    subprocess.run(["git", "-C", tmp, "sparse-checkout", "set"] + sorted(set(FONTS[f] for f in missing)), check=True)
    for f in missing:
        os.replace(os.path.join(tmp, FONTS[f], f), os.path.join(d, f))


def F(d, name, size, text=""):
    if DEVA.search(text or ""):
        if not features.check("raqm"):
            raise SystemExit("Hindi needs Pillow with raqm - refusing to render broken Hindi")
        name = {"Poppins-SemiBold.ttf": "Mukta-SemiBold.ttf", "Poppins-Regular.ttf": "Mukta-Regular.ttf",
                "DMSerifDisplay-Regular.ttf": "Mukta-ExtraBold.ttf"}.get(name, name)
    lay = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC
    return ImageFont.truetype(os.path.join(d, name), size, layout_engine=lay)


def wrap(draw, text, font, width):
    out = []
    for para in text.split("\n"):
        cur = ""
        for w in para.split():
            t = (cur + " " + w).strip()
            if draw.textlength(t, font=font) <= width or not cur:
                cur = t
            else:
                out.append(cur)
                cur = w
        out.append(cur)
    return out


def layout(spec, d, draw, W, H, scale):
    """Return list of draw ops and total height for a given scale."""
    m = 100
    width = W - 2 * m
    ops, y = [], 0
    if spec.get("eyebrow"):
        f = F(d, "Poppins-SemiBold.ttf", int(30 * scale), spec["eyebrow"])
        txt = spec["eyebrow"].upper() if not DEVA.search(spec["eyebrow"]) else spec["eyebrow"]
        ops.append(("text", (m, y), txt, f, "accent", 4))
        y += int(52 * scale)
        ops.append(("bar", (m, y, m + 90, y + 6)))
        y += int(52 * scale)
    if spec.get("big"):
        f = F(d, "DMSerifDisplay-Regular.ttf", int(190 * scale), spec["big"])
        ops.append(("text", (m - 6, y - int(30 * scale)), spec["big"], f, "accent", 0))
        y += int(200 * scale)
    if spec.get("headline"):
        f = F(d, "Mukta-ExtraBold.ttf" if DEVA.search(spec["headline"]) else "DMSerifDisplay-Regular.ttf",
              int(82 * scale), spec["headline"])
        lh = int(100 * scale)
        for ln in wrap(draw, spec["headline"], f, width):
            ops.append(("text", (m, y), ln, f, "head", 0))
            y += lh
        y += int(36 * scale)
    if spec.get("body"):
        f = F(d, "Poppins-Regular.ttf", int(40 * scale), spec["body"])
        lh = int(60 * scale)
        for ln in wrap(draw, spec["body"], f, width):
            if ln:
                ops.append(("text", (m, y), ln, f, "body", 0))
            y += lh if ln else lh // 2
    return ops, y


def render(spec):
    d = spec.get("fonts_dir", HERE)
    ensure_fonts(d)
    W, H = SIZES[spec.get("size", "feed")]
    th = THEMES[spec.get("theme", "maroon")]
    img = Image.new("RGB", (W, H), th["bg"])
    draw = ImageDraw.Draw(img)
    # thin inset frame
    draw.rectangle((36, 36, W - 37, H - 37), outline=th["accent"], width=2)
    top = 150 if H == 1350 else 300
    bottom_reserved = 230 if H == 1350 else 420
    avail = H - top - bottom_reserved
    scale = 1.0 if H == 1350 else 1.2
    while True:
        ops, h = layout(spec, d, draw, W, H, scale)
        if h <= avail or scale < 0.6:
            break
        scale -= 0.05
    if h > avail:
        raise SystemExit(f"{spec['out']}: text too long for card, shorten it")
    y0 = top if H == 1350 else top + (avail - h) // 3
    for op in ops:
        if op[0] == "bar":
            x1, y1, x2, y2 = op[1]
            draw.rectangle((x1, y1 + y0, x2, y2 + y0), fill=th["accent"])
        else:
            _, (x, y), txt, f, col, spacing = op
            if spacing:
                cx = x
                for ch in txt:
                    draw.text((cx, y + y0), ch, font=f, fill=th[col])
                    cx += draw.textlength(ch, font=f) + spacing
            else:
                draw.text((x, y + y0), txt, font=f, fill=th[col])
    # footer: source + handle + logo
    fy = H - (170 if H == 1350 else 330)
    draw.line((100, fy, W - 100, fy), fill=th["muted"], width=1)
    if spec.get("source"):
        label = "स्रोत: " if DEVA.search(spec["source"]) else "Source: "
        sf = F(d, "Poppins-Regular.ttf", 24, label + spec["source"])
        lines = wrap(draw, label + spec["source"], sf, W - 360)[:2]
        for i, ln in enumerate(lines):
            draw.text((100, fy + 24 + i * 34), ln, font=sf, fill=th["muted"])
    hf = F(d, "Poppins-SemiBold.ttf", 24)
    draw.text((100, fy + 24 + 2 * 34 + 6), "@jhunjhunu_blog", font=hf, fill=th["accent"])
    logo = spec.get("logo", os.path.join(HERE, "jb-mark.png"))
    if os.path.exists(logo):
        lg = Image.open(logo).convert("RGB")
        lg.thumbnail((104, 104))
        pad = 12
        chip = Image.new("RGB", (lg.width + 2 * pad, lg.height + 2 * pad), CREAM)
        chip.paste(lg, (pad, pad))
        mask = Image.new("L", chip.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, chip.width - 1, chip.height - 1), 18, fill=255)
        img.paste(chip, (W - 100 - chip.width, fy + 18), mask)
    img.save(spec["out"], "JPEG", quality=92)
    print("wrote", spec["out"])


if __name__ == "__main__":
    data = json.load(open(sys.argv[1]))
    for s in data if isinstance(data, list) else [data]:
        render(s)
