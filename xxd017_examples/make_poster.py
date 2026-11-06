"""XXD Panel 017 style poster: photo above, Korean naive flat illustration below.
Canvas 1086x1448 (3:4), exact 50/50 split at y=724."""
import math, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

SRC, OUT = sys.argv[1], sys.argv[2]
W, H = 1086, 1448
HALF = H // 2
SS = 3  # supersampling for the illustration
rng = np.random.default_rng(17)

PAPER = (255, 253, 245)
BLACK = (30, 30, 27)
CARAMEL = (241, 166, 62)
CAT = (141, 145, 151)
CAT_DARK = (95, 99, 105)
PINK = (245, 154, 182)
RED = (239, 85, 72)
TONGUE = (248, 176, 182)

# ---------------------------------------------------------------- upper half
def upper_half(path):
    src = Image.open(path).convert("RGB")
    sw, sh = src.size
    ph = HALF
    pw = round(sw * ph / sh)
    photo = src.resize((pw, ph), Image.LANCZOS)
    a = np.asarray(photo).astype(np.float32)
    s = ph / sh
    side = (W - pw) // 2
    F = 64  # feather width into the photo

    def region(x0, y0, x1, y1):
        return a[int(y0 * s):int(y1 * s), int(x0 * s):int(x1 * s)]

    def synth(srcs, w, h, P=40, step=20):
        # overlap-add of random zero-mean fabric patches: weave texture without large repeats
        win = np.outer(np.hanning(P), np.hanning(P))[..., None] + 1e-3
        out = np.zeros((h + 2 * P, w + 2 * P, 3), np.float32)
        ws = np.full((h + 2 * P, w + 2 * P, 1), 1e-6, np.float32)
        for y in range(0, h + P, step):
            for x in range(0, w + P, step):
                r = srcs[rng.integers(len(srcs))]
                yy = rng.integers(0, r.shape[0] - P); xx = rng.integers(0, r.shape[1] - P)
                pt = r[yy:yy + P, xx:xx + P]
                pt = pt - pt.mean(axis=(0, 1))
                out[y:y + P, x:x + P] += pt * win
                ws[y:y + P, x:x + P] += win
        out = (out / ws)[P:P + h, P:P + w]
        ref = np.concatenate([r.reshape(-1, 3) - r.reshape(-1, 3).mean(0) for r in srcs])
        return out * (0.9 * ref.std() / max(out.std(), 1e-3))

    fabric = [region(10, 660, 100, 960), region(625, 300, 760, 820), region(20, 470, 95, 640)]
    couch = np.concatenate([f.reshape(-1, 3) for f in fabric]).mean(0)
    canvas = a.copy()
    canvas = np.zeros((ph, W, 3), np.float32)
    canvas[:, side:side + pw] = a
    for is_left in (True, False):
        wd = side + F
        tex = synth(fabric, wd, ph)
        edge = a[:, F:F + 16] if is_left else a[:, -F - 16:-F]
        rowcol = edge.mean(axis=1)
        k = 121
        rowcol = np.stack([np.convolve(np.pad(rowcol[:, c], k // 2, mode="edge"), np.ones(k) / k, "valid") for c in range(3)], 1)
        xs = np.linspace(0, 1, wd)  # 0 = innermost (inside photo) -> 1 = canvas edge
        if is_left:
            xs = xs[::-1]
        t = np.clip((xs * wd - F) / (0.45 * side), 0, 1)[None, :, None]
        base = rowcol[:, None, :] * (1 - t) + couch[None, None, :] * t
        shade = (1 - 0.18 * np.clip((xs * wd - F) / side, 0, 1) ** 1.4)[None, :, None]
        ext = (base + tex) * shade
        alpha = np.clip((xs * wd) / F, 0, 1)[None, :, None]
        alpha = alpha * alpha * (3 - 2 * alpha)
        sl = slice(0, wd) if is_left else slice(W - wd, W)
        canvas[:, sl] = ext * alpha + canvas[:, sl] * (1 - alpha)

    img = Image.fromarray(np.clip(canvas, 0, 255).astype(np.uint8))
    # restrained exhibition-grade refinement
    img = ImageEnhance.Contrast(img).enhance(1.06)
    img = ImageEnhance.Color(img).enhance(0.95)
    arr = np.asarray(img).astype(np.float32)
    arr[..., 2] *= 1.015
    arr += rng.normal(0, 2.2, arr.shape[:2])[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

# ---------------------------------------------------------------- drawing helpers
def M(x, y):  # source photo coords -> lower-field coords
    return (300 + 0.66 * x, 30 + 0.66 * y)

def catmull(pts, closed=True, n=14):
    P = [np.array(p, float) for p in pts]
    out = []
    L = len(P)
    rngi = range(L) if closed else range(L - 1)
    for i in rngi:
        p0 = P[(i - 1) % L] if closed or i > 0 else P[i]
        p1 = P[i]; p2 = P[(i + 1) % L]
        p3 = P[(i + 2) % L] if closed or i + 2 < L else P[(i + 1) % L]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    if not closed:
        out.append(P[-1])
    return np.array(out)

def resample(pts, step=2.5, closed=False):
    pts = np.asarray(pts, float)
    if closed:
        pts = np.vstack([pts, pts[:1]])
    d = np.r_[0, np.cumsum(np.hypot(*np.diff(pts, axis=0).T))]
    n = max(int(d[-1] / step), 2)
    s = np.linspace(0, d[-1], n)
    return np.c_[np.interp(s, d, pts[:, 0]), np.interp(s, d, pts[:, 1])]

def S(pts):
    return [(float(x) * SS, float(y) * SS) for x, y in pts]

def fill(draw, pts, color, offset=(1.6, 1.2)):
    pts = np.asarray(pts) + np.array(offset)
    draw.polygon(S(pts), fill=color)

def rough(draw, pts, width=4.6, color=BLACK, closed=False, jitter=1.3, gaps=1, taper=True):
    p = resample(pts, 2.5, closed)
    n = len(p)
    tang = np.gradient(p, axis=0)
    nrm = np.c_[-tang[:, 1], tang[:, 0]]
    nrm /= np.maximum(np.hypot(*nrm.T), 1e-6)[:, None]
    t = np.arange(n)
    ph = rng.uniform(0, 6.3, 3)
    off = jitter * (0.6 * np.sin(t * 0.09 + ph[0]) + 0.4 * np.sin(t * 0.31 + ph[1])) + rng.normal(0, 0.32, n)
    p = p + nrm * off[:, None]
    w = width * (1 + 0.25 * np.sin(t * 0.05 + ph[2])) + rng.normal(0, 0.12, n)
    if taper and not closed:
        ramp = np.clip(np.minimum(t, n - 1 - t) / 6, 0.35, 1)
        w = w * ramp
    keep = np.ones(n, bool)
    if n > 70:
        for _ in range(gaps):
            st = rng.integers(10, n - 15)
            keep[st:st + rng.integers(3, 6)] = False
    for i in range(n - 1):
        if keep[i] and keep[i + 1]:
            r = w[i] * SS / 2
            x0, y0 = p[i] * SS; x1, y1 = p[i + 1] * SS
            draw.line([(x0, y0), (x1, y1)], fill=color, width=max(1, int(round(w[i] * SS))))
            draw.ellipse([x0 - r, y0 - r, x0 + r, y0 + r], fill=color)
    if keep[-1]:
        r = w[-1] * SS / 2; x, y = p[-1] * SS
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color)

def shape(draw, pts, color, width=4.6, gaps=1, smooth=True, outline=True):
    q = catmull(pts) if smooth else np.asarray(pts, float)
    fill(draw, q, color)
    if outline:
        rough(draw, q, width, closed=True, gaps=gaps)
    return q

def rounded_rect(x0, y0, x1, y1, r, rot=0.0):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for a in np.linspace(a0, a0 + 90, 10):
            pts.append((cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))))
    pts = np.array(pts)
    c = pts.mean(0)
    th = math.radians(rot)
    R = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    return (pts - c) @ R.T + c

def ellipse_pts(cx, cy, rx, ry, rot=0.0, n=40):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    th = math.radians(rot)
    x = rx * np.cos(a); y = ry * np.sin(a)
    return np.c_[cx + x * math.cos(th) - y * math.sin(th), cy + x * math.sin(th) + y * math.cos(th)]

def tube(center, w0, w1):
    c = catmull(center, closed=False, n=10)
    tang = np.gradient(c, axis=0)
    nrm = np.c_[-tang[:, 1], tang[:, 0]]
    nrm /= np.hypot(*nrm.T)[:, None]
    ws = np.linspace(w0, w1, len(c))[:, None] / 2
    left = c + nrm * ws; right = c - nrm * ws
    tip_dir = tang[-1] / np.hypot(*tang[-1])
    cap = [c[-1] + (nrm[-1] * math.cos(a) + tip_dir * math.sin(a)) * ws[-1, 0] for a in np.linspace(0, math.pi, 12)]
    return np.vstack([left, cap, right[::-1]])

def text_run(img, s, x, y, font, color=BLACK, rot=0.0, jit_rot=6, jit_y=4, spacing=0.94):
    for ch in s:
        if ch == " ":
            x += font.getlength(" ") / SS * spacing
            continue
        size = int(font.size * 1.6)
        layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((size / 2, size / 2), ch, font=font, fill=color, anchor="mm")
        layer = layer.rotate(rot + rng.uniform(-jit_rot, jit_rot), resample=Image.BICUBIC)
        dy = rng.uniform(-jit_y, jit_y)
        adv = font.getlength(ch) / SS
        img.paste(layer, (int((x + adv / 2) * SS - size / 2), int((y + dy) * SS - size / 2)), layer)
        th = math.radians(-rot)
        x += adv * spacing * math.cos(th)
        y += adv * spacing * math.sin(th)

# ---------------------------------------------------------------- lower half
def lower_half():
    img = Image.new("RGB", (W * SS, HALF * SS), PAPER)
    d = ImageDraw.Draw(img)

    # sofa: one broad caramel field, cropped at the top
    sofa = rounded_rect(430, -80, 880, 650, 70, rot=-1.5)
    fill(d, sofa, CARAMEL, (0, 0))
    rough(d, sofa, 4.8, closed=True, gaps=2)
    rough(d, [(832, 10), (838, 180), (834, 380), (826, 540)], 3.6)  # cushion seam

    # pink fleece blanket, cropped at the bottom edge
    blanket = [(420, 770), (432, 655), (480, 618), (545, 634), (600, 604), (690, 622), (760, 600),
               (850, 624), (912, 660), (928, 770)]
    shape(d, blanket, PINK, gaps=1)
    rough(d, [(560, 668), (590, 650), (625, 664)], 3.2)
    rough(d, [(780, 650), (812, 642), (836, 662)], 3.2)

    # charging cable
    cable = catmull([M(430, -40), M(470, 15), M(540, 35), M(620, 45), M(655, 75), M(642, 140), M(606, 196), M(572, 232)], closed=False)
    rough(d, cable, 9.5, jitter=0.6, gaps=0)
    rough(d, cable, 4.0, color=PAPER, jitter=0.4, gaps=0)

    # tail sweeping left off the sofa
    tail = tube([M(400, 330), M(300, 318), M(200, 352), M(130, 425), M(118, 490), M(145, 548), M(178, 600)], 50, 34)
    fill(d, tail, CAT)
    tip = tube([M(155, 560), M(178, 600)], 34, 32)
    fill(d, tip, CAT_DARK)
    rough(d, tail, 4.6, closed=True, gaps=1)
    for a, b in ((M(240, 318), M(232, 362)), (M(165, 372), M(190, 410))):
        rough(d, [a, b], 3.4)

    # raised hind leg + paw
    leg = [M(495, 215), M(522, 160), M(548, 128), M(578, 118), M(598, 140), M(590, 180), M(560, 205), M(540, 250)]
    shape(d, leg, CAT)
    pad = ellipse_pts(*M(574, 145), 9, 7, rot=-30)
    fill(d, pad, CAT_DARK, (0, 0))

    # long body (cropped at the top edge)
    body = [M(352, -70), M(455, -70), M(468, 100), M(512, 192), M(578, 255), M(604, 340), M(604, 460),
            M(594, 590), M(586, 705), M(566, 795), M(540, 856), M(532, 960), M(522, 1018), M(490, 1034),
            M(455, 1018), M(446, 940), M(430, 852), M(398, 760), M(386, 620), M(378, 480), M(370, 360),
            M(360, 220), M(350, 90)]
    shape(d, body, CAT, width=4.8, gaps=2)
    # fluffy white belly streak with tufted edges
    spine = catmull([M(530, 250), M(552, 340), M(548, 470), M(536, 600), M(526, 700)], closed=False, n=8)
    tang = np.gradient(spine, axis=0); nr = np.c_[-tang[:, 1], tang[:, 0]]; nr /= np.hypot(*nr.T)[:, None]
    u = np.linspace(0, 1, len(spine))
    half = (8 + 13 * np.sin(u * math.pi)) * (1 + 0.16 * np.sin(u * 23 + 1) + 0.1 * np.sin(u * 61) + 0.08 * np.sin(u * 97 + 2))
    belly = np.vstack([spine + nr * half[:, None], (spine - nr * half[:, None] * 0.8)[::-1]])
    fill(d, belly, PAPER, (0, 0))
    for a, b in ((M(395, 250), M(418, 262)), (M(390, 330), M(416, 342)), (M(392, 450), M(418, 462)),
                 (M(398, 580), M(424, 590))):
        rough(d, [a, b], 3.4, gaps=0)
    # front paw resting on the blanket, toe lines
    for x in (472, 498):
        rough(d, [M(x, 1004), M(x + 2, 1026)], 2.8)
    # curled white front paw
    paw = ellipse_pts(*M(570, 800), 22, 27, rot=-15, n=24)
    shape(d, paw, PAPER, width=4.2, gaps=0, smooth=False)
    rough(d, [M(555, 812), M(570, 822)], 2.6)

    # head (exaggerated, tilted toward the upper-left)
    hc = np.array(M(330, 725)); r = 66
    up = np.array([math.cos(math.radians(-153)), math.sin(math.radians(-153))])
    dn = -up
    pp = np.array([up[1] * -1, up[0]])  # perpendicular
    for ang in (-111, 165):
        dv = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
        pv = np.array([-dv[1], dv[0]])
        ear = [hc + dv * r * 0.7 + pv * r * 0.5, hc + dv * r * 1.55 + pv * r * 0.04, hc + dv * r * 0.7 - pv * r * 0.5]
        shape(d, ear, CAT, width=4.4, gaps=0, smooth=False)
        inner = [hc + dv * r * 0.86 + pv * r * 0.28, hc + dv * r * 1.32 + pv * r * 0.04, hc + dv * r * 0.86 - pv * r * 0.28]
        fill(d, inner, PINK, (0, 0))
    head = ellipse_pts(*hc, r * 1.04, r * 0.96, rot=-153 + 90)
    shape(d, head, CAT, width=4.8, gaps=1)
    # forehead tabby marks
    for k in (-0.2, 0.0, 0.2):
        a = hc + up * r * 0.8 + pp * r * k
        rough(d, [a, a - up * r * 0.24], 3.0, gaps=0)
    # squeezed-shut yawning eyes: > <
    for sgn in (1, -1):
        e = hc + up * r * 0.2 + pp * r * 0.4 * sgn
        v = e - pp * sgn * r * 0.12
        rough(d, [e + pp * sgn * r * 0.1 + up * r * 0.12, v, e + pp * sgn * r * 0.1 - up * r * 0.12], 4.6, gaps=0, taper=False)
    # nose
    n0 = hc - up * r * 0.02 + dn * r * 0.0
    nose = [n0 - pp * r * 0.08, n0 + pp * r * 0.08, n0 + dn * r * 0.09]
    shape(d, nose, PINK, width=2.8, gaps=0, smooth=False)
    # big yawning mouth: flat top, deep rounded bottom
    mc = hc + dn * r * 0.2
    mw, mh = r * 0.36, r * 0.62
    mouth = [mc - pp * mw] + [mc + pp * mw * math.cos(a) + dn * mh * math.sin(a) for a in np.linspace(math.pi, 0, 16)][1:]
    mouth = np.array(mouth)
    fill(d, mouth, RED, (0, 0))
    tongue = ellipse_pts(*(mc + dn * mh * 0.72), mw * 0.5, mh * 0.24, rot=math.degrees(math.atan2(pp[1], pp[0])))
    fill(d, tongue, TONGUE, (0, 0))
    for sgn in (1, -1):
        b = mc + pp * mw * 0.62 * sgn
        fang = [b - pp * r * 0.06, b + pp * r * 0.06, b + dn * r * 0.14]
        fill(d, fang, PAPER, (0, 0))
    rough(d, np.vstack([mouth, mouth[:1]]), 4.2, gaps=0, taper=False)
    # whiskers fanning out
    for sgn in (1, -1):
        base = hc + dn * r * 0.1 + pp * r * 0.42 * sgn
        for k, L in ((-0.35, 1.0), (0.0, 1.15), (0.35, 0.95)):
            dv = dn * math.cos(k) + pp * sgn * math.sin(k) * 1.0
            dv = dv * 0.55 + pp * sgn * 0.75
            dv /= np.hypot(*dv)
            rough(d, [base, base + dv * r * 0.6 * L, base + dv * r * 1.1 * L + dn * 6], 2.4, jitter=0.6, gaps=0)

    # accents: yawn burst + star near the head
    star_c = np.array((222, 410))
    star = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = 16 if i % 2 == 0 else 7
        star.append(star_c + rr * np.array((math.cos(a), math.sin(a))))
    rough(d, star, 3.2, closed=True, gaps=0)
    for a, b in (((420, 448), (408, 432)), ((404, 470), (386, 462)), ((398, 496), (378, 497))):
        rough(d, [a, b], 3.4)

    # measuring arrow: one very long cat
    ax = 952
    rough(d, [(ax, 40), (ax + 3, 300), (ax - 2, 560)], 3.8, gaps=1)
    rough(d, [(ax - 14, 60), (ax, 38), (ax + 14, 58)], 3.8, gaps=0)
    rough(d, [(ax - 14, 540), (ax - 1, 562), (ax + 12, 542)], 3.8, gaps=0)

    # typography
    title_f = ImageFont.truetype("/System/Library/Fonts/Supplemental/ChalkboardSE.ttc", 112 * SS, index=2)
    big_f = ImageFont.truetype("/System/Library/Fonts/Supplemental/ChalkboardSE.ttc", 74 * SS, index=2)
    small_f = ImageFont.truetype("/System/Library/Fonts/Supplemental/ChalkboardSE.ttc", 26 * SS, index=2)
    side_f = ImageFont.truetype("/System/Library/Fonts/Supplemental/ChalkboardSE.ttc", 34 * SS, index=2)
    text_run(img, "BIG", 62, 438, big_f, rot=-5)
    text_run(img, "YAWN!", 34, 540, title_f, rot=-3, jit_rot=7, jit_y=6)
    text_run(img, "SOFA / CAT / NO. 017", 40, 688, small_f, rot=0, jit_rot=3, jit_y=1.5)
    # vertical side note along the arrow
    note = Image.new("RGBA", (420 * SS, 70 * SS), (0, 0, 0, 0))
    text_run(note, "SO  L O N G", 10, 35, side_f, jit_rot=5, jit_y=3)
    note = note.rotate(90, expand=True, resample=Image.BICUBIC)
    img.paste(note, (int(978 * SS), int(110 * SS)), note)
    # dot pair accent
    for cx, cy in ((346, 682), (360, 686)):
        d.ellipse([(cx - 4) * SS, (cy - 4) * SS, (cx + 4) * SS, (cy + 4) * SS], fill=RED)

    return img.resize((W, HALF), Image.LANCZOS)

poster = Image.new("RGB", (W, H), PAPER)
poster.paste(upper_half(SRC), (0, 0))
poster.paste(lower_half(), (0, HALF))
poster.save(OUT, quality=95)
print("saved", OUT, poster.size)
