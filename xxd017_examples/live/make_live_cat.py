"""Generate the animated "live" cut-out of the XXD 017 gray cat.

Outputs (next to this script):
  miu-cat.svg  self-contained animated SVG, transparent background (works in <img>)
  miu-cat.js   <miu-cat> web component with the same SVG inlined; tap to yawn
Geometry is the same as the poster illustration; outlines are variable-width
filled strips so the hand-drawn line character survives, and an SVG
turbulence filter makes the lines gently "boil" like hand-drawn animation.
"""
import math, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
rng = np.random.default_rng(17)

BLACK = "#1E1E1B"
PAPER = "#FFFDF5"
CAT = "#8D9197"
CAT_DARK = "#5F6369"
PINK = "#F59AB6"
RED = "#EF5548"
TONGUE = "#F8B0B6"

YAWN = 3.2  # seconds per yawn
R = 66      # head radius

# ---------------------------------------------------------------- geometry helpers
def M(x, y):  # source photo coords -> illustration coords (same mapping as the poster)
    return (300 + 0.66 * x, 30 + 0.66 * y)

def catmull(pts, closed=True, n=14):
    P = [np.array(p, float) for p in pts]
    L = len(P)
    out = []
    for i in (range(L) if closed else range(L - 1)):
        p0 = P[(i - 1) % L] if closed or i > 0 else P[i]
        p1, p2 = P[i], P[(i + 1) % L]
        p3 = P[(i + 2) % L] if closed or i + 2 < L else P[(i + 1) % L]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
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

def normals(p):
    t = np.gradient(p, axis=0)
    n = np.c_[-t[:, 1], t[:, 0]]
    return n / np.maximum(np.hypot(*n.T), 1e-6)[:, None], t / np.maximum(np.hypot(*t.T), 1e-6)[:, None]

def ellipse_pts(cx, cy, rx, ry, rot=0.0, n=40):
    a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    th = math.radians(rot)
    x, y = rx * np.cos(a), ry * np.sin(a)
    return np.c_[cx + x * math.cos(th) - y * math.sin(th), cy + x * math.sin(th) + y * math.cos(th)]

def tube(center, w0, w1):
    c = catmull(center, closed=False, n=10)
    nrm, tan = normals(c)
    ws = np.linspace(w0, w1, len(c))[:, None] / 2
    cap = [c[-1] + (nrm[-1] * math.cos(a) + tan[-1] * math.sin(a)) * ws[-1, 0] for a in np.linspace(0, math.pi, 12)]
    return np.vstack([c + nrm * ws, cap, (c - nrm * ws)[::-1]])

def stroke(pts, width=4.6, closed=False, gaps=1, taper=True, jitter=1.2):
    """Rough hand-drawn line as filled polygons: wobble, uneven pressure, occasional breaks."""
    p = resample(pts, 2.5, closed)
    n = len(p)
    nrm, tan = normals(p)
    t = np.arange(n)
    ph = rng.uniform(0, 6.3, 3)
    p = p + nrm * (jitter * (0.6 * np.sin(t * 0.09 + ph[0]) + 0.4 * np.sin(t * 0.31 + ph[1])) + rng.normal(0, 0.3, n))[:, None]
    w = width * (1 + 0.25 * np.sin(t * 0.05 + ph[2])) + rng.normal(0, 0.1, n)
    if taper and not closed:
        w = w * np.clip(np.minimum(t, n - 1 - t) / 6, 0.35, 1)
    keep = np.ones(n, bool)
    if n > 70:
        for _ in range(gaps):
            st = rng.integers(10, n - 15)
            keep[st:st + rng.integers(3, 6)] = False
    polys, i = [], 0
    while i < n:
        if not keep[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and keep[j + 1]:
            j += 1
        if j > i:
            seg = slice(i, j + 1)
            L = p[seg] + nrm[seg] * w[seg, None] / 2
            Rr = p[seg] - nrm[seg] * w[seg, None] / 2
            cap_end = [p[j] + (nrm[j] * math.cos(a) + tan[j] * math.sin(a)) * w[j] / 2 for a in np.linspace(0, math.pi, 5)]
            cap_start = [p[i] - (nrm[i] * math.cos(a) + tan[i] * math.sin(a)) * w[i] / 2 for a in np.linspace(0, math.pi, 5)]
            polys.append(np.vstack([L, cap_end, Rr[::-1], cap_start]))
        i = j + 1
    return polys

# ---------------------------------------------------------------- SVG building
SHIFT = np.zeros(2)

def d_of(polys, shift=True):
    off = SHIFT if shift else np.zeros(2)
    out = []
    for poly in polys:
        q = np.asarray(poly) + off
        out.append("M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in q) + "Z")
    return "".join(out)

def fill(pts, color, offset=(1.6, 1.2), shift=True):
    return f'<path fill="{color}" d="{d_of([np.asarray(pts) + np.array(offset)], shift)}"/>'

def ink(polys, shift=True):
    return f'<path fill="{BLACK}" d="{d_of(polys, shift)}"/>'

def shape(pts, color, width=4.6, gaps=1, smooth=True, shift=True, offset=(1.6, 1.2)):
    q = catmull(pts) if smooth else np.asarray(pts, float)
    return fill(q, color, offset, shift) + ink(stroke(q, width, closed=True, gaps=gaps), shift)

def spline_anim(kind, values, key_times, begin, dur, extra=""):
    n = len(values) - 1
    splines = ";".join(["0.45 0 0.55 1"] * n)
    attr = 'attributeName="transform"' if kind != "opacity" else 'attributeName="opacity"'
    typ = f'type="{kind}" ' if kind != "opacity" else ""
    return (f'<anim{"ateTransform" if kind != "opacity" else ""} {attr} {typ}values="{";".join(values)}" '
            f'keyTimes="{";".join(map(str, key_times))}" calcMode="spline" keySplines="{splines}" '
            f'begin="{begin}" dur="{dur}" {extra}/>')

def build():
    global SHIFT
    hc = np.array(M(330, 725))
    HEAD_ROT = -63  # head's local "up" points to the upper-left, as in the photo

    # ---- global-space geometry
    tail_c = [M(400, 330), M(300, 318), M(200, 352), M(130, 425), M(118, 490), M(145, 548), M(178, 600)]
    tail = tube(tail_c, 50, 34)
    tail_tip = tube([M(155, 560), M(178, 600)], 34, 32)
    leg = [M(495, 215), M(522, 160), M(548, 128), M(578, 118), M(598, 140), M(590, 180), M(560, 205), M(540, 250)]
    body = [M(350, -20), M(372, -62), M(405, -75), M(440, -62), M(458, -20), M(468, 100), M(512, 192), M(578, 255),
            M(604, 340), M(604, 460), M(594, 590), M(586, 705), M(566, 795), M(540, 856), M(532, 960), M(522, 1018),
            M(490, 1034), M(455, 1018), M(446, 940), M(430, 852), M(398, 760), M(386, 620), M(378, 480), M(370, 360),
            M(360, 220), M(350, 90)]
    paw = ellipse_pts(*M(570, 800), 22, 27, rot=-15, n=24)

    # bounds (head included via its local->global transform)
    th = math.radians(HEAD_ROT)
    rot = np.array([[math.cos(th), -math.sin(th)], [math.sin(th), math.cos(th)]])
    head_extent = (ellipse_pts(0, 0, R * 1.75, R * 1.75, n=36) @ rot.T) + hc
    allpts = np.vstack([tail, catmull(body), np.asarray(leg), head_extent])
    pad = 14
    lo = allpts.min(0) - pad
    hi = allpts.max(0) + pad
    SHIFT = -lo
    vw, vh = hi - lo
    S = lambda p: np.asarray(p) + SHIFT  # shift a global point for pivots

    yb = "yawn.begin"
    yd = f"{YAWN}s"
    parts = []

    # ---- tail: slow lazy swish
    tp = S(M(392, 335))
    parts.append('<g>' + spline_anim("rotate", [f"0 {tp[0]:.1f} {tp[1]:.1f}", f"7 {tp[0]:.1f} {tp[1]:.1f}", f"0 {tp[0]:.1f} {tp[1]:.1f}"],
                                     [0, 0.5, 1], "0s", "3.6s", 'repeatCount="indefinite"'))
    parts.append(fill(tail, CAT) + fill(tail_tip, CAT_DARK) + ink(stroke(tail, 4.6, closed=True)))
    for a, b in ((M(240, 318), M(232, 362)), (M(165, 372), M(190, 410))):
        parts.append(ink(stroke([a, b], 3.4)))
    parts.append('</g>')

    # ---- raised hind leg: stretches during the yawn
    lp = S(M(520, 225))
    parts.append('<g>' + spline_anim("rotate", [f"{v} {lp[0]:.1f} {lp[1]:.1f}" for v in (0, -10, -10, 0, 0)],
                                     [0, 0.25, 0.6, 0.85, 1], yb, yd))
    parts.append(shape(leg, CAT) + fill(ellipse_pts(*M(574, 145), 9, 7, rot=-30), CAT_DARK, (0, 0)))
    parts.append('</g>')

    # ---- body: breathing
    bc = S(M(480, 480))
    parts.append(f'<g transform="translate({bc[0]:.1f} {bc[1]:.1f})"><g>'
                 + spline_anim("scale", ["1 1", "1.03 1", "1 1"], [0, 0.5, 1], "0s", "2.8s", 'repeatCount="indefinite"')
                 + f'<g transform="translate({-bc[0]:.1f} {-bc[1]:.1f})">')
    parts.append(shape(body, CAT, width=4.8, gaps=2))
    for x in (390, 418):  # toe lines on the top foot
        parts.append(ink(stroke([M(x, -64), M(x + 2, -44)], 2.8)))
    spine = catmull([M(530, 250), M(552, 340), M(548, 470), M(536, 600), M(526, 700)], closed=False, n=8)
    nr, _ = normals(spine)
    u = np.linspace(0, 1, len(spine))
    half = (8 + 13 * np.sin(u * math.pi)) * (1 + 0.16 * np.sin(u * 23 + 1) + 0.1 * np.sin(u * 61) + 0.08 * np.sin(u * 97 + 2))
    parts.append(fill(np.vstack([spine + nr * half[:, None], (spine - nr * half[:, None] * 0.8)[::-1]]), PAPER, (0, 0)))
    for a, b in ((M(395, 250), M(418, 262)), (M(390, 330), M(416, 342)), (M(392, 450), M(418, 462)), (M(398, 580), M(424, 590))):
        parts.append(ink(stroke([a, b], 3.4, gaps=0)))
    for x in (472, 498):
        parts.append(ink(stroke([M(x, 1004), M(x + 2, 1026)], 2.8)))
    parts.append(shape(paw, PAPER, width=4.2, gaps=0, smooth=False))
    parts.append(ink(stroke([M(555, 812), M(570, 822)], 2.6)))
    parts.append('</g></g></g>')

    # ---- head, drawn in its own upright frame (local up = -y)
    h = S(hc)
    piv = (0.35 * R, 0.75 * R)  # neck side, toward the body
    parts.append(f'<g transform="translate({h[0]:.1f} {h[1]:.1f}) rotate({HEAD_ROT})"><g>')
    parts.append(spline_anim("rotate", [f"{v} {piv[0]:.1f} {piv[1]:.1f}" for v in (0, -8, -9, 0, 0)],
                             [0, 0.22, 0.6, 0.84, 1], yb, yd))
    for k, ang in enumerate((-48, -132)):
        dv = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
        pv = np.array([-dv[1], dv[0]])
        base = dv * R * 0.7
        ear = [base + pv * R * 0.5, dv * R * 1.55 + pv * R * 0.04, base - pv * R * 0.5]
        inner = [dv * R * 0.86 + pv * R * 0.28, dv * R * 1.32 + pv * R * 0.04, dv * R * 0.86 - pv * R * 0.28]
        ear_svg = shape(ear, CAT, width=4.4, gaps=0, smooth=False, shift=False) + fill(inner, PINK, (0, 0), shift=False)
        bx, by = f"{base[0]:.1f}", f"{base[1]:.1f}"
        twitch = ''
        if k == 0:  # occasional ear twitch while idle
            twitch = ('<animateTransform attributeName="transform" type="rotate" '
                      f'values="0 {bx} {by};0 {bx} {by};-14 {bx} {by};4 {bx} {by};0 {bx} {by}" '
                      'keyTimes="0;0.86;0.89;0.92;0.95" dur="7.3s" repeatCount="indefinite"/>')
        flick = -18 if k == 0 else 18  # both ears flick when tapped
        twitch += ('<animateTransform attributeName="transform" type="rotate" '
                   f'values="0 {bx} {by};{flick} {bx} {by};{-flick / 3:.0f} {bx} {by};0 {bx} {by}" '
                   'keyTimes="0;0.3;0.65;1" begin="boop.begin" dur="0.5s"/>')
        parts.append('<g>' + twitch + ear_svg + '</g>')
    parts.append(shape(ellipse_pts(0, 0, R * 1.04, R * 0.96), CAT, width=4.8, gaps=1, shift=False))
    for k in (-0.2, 0.0, 0.2):
        parts.append(ink(stroke([(k * R, -0.8 * R), (k * R, -0.56 * R)], 3.0, gaps=0), shift=False))

    # eyes: relaxed closed arcs while idle, squeezed > < during the yawn
    relaxed, squeeze = [], []
    for sgn in (1, -1):
        ex, ey = sgn * 0.4 * R, -0.2 * R
        arc = [(ex + c * 0.16 * R, ey + 0.07 * R * (1 - c * c)) for c in np.linspace(-1, 1, 9)]
        relaxed.append(stroke(arc, 4.2, gaps=0))
        v = (ex - sgn * 0.12 * R, ey)
        squeeze.append(stroke([(ex + sgn * 0.1 * R, ey - 0.12 * R), v, (ex + sgn * 0.1 * R, ey + 0.12 * R)], 4.6, gaps=0, taper=False))
    parts.append('<g><animate attributeName="opacity" values="1;0;1" keyTimes="0;0.1;0.82" calcMode="discrete" begin="yawn.begin" dur="%s"/>' % yd
                 + "".join(ink(s, False) for s in relaxed) + '</g>')
    parts.append('<g opacity="0"><animate attributeName="opacity" values="0;1;0" keyTimes="0;0.1;0.82" calcMode="discrete" begin="yawn.begin" dur="%s"/>' % yd
                 + "".join(ink(s, False) for s in squeeze) + '</g>')

    # nose
    nose = [(-0.08 * R, -0.02 * R), (0.08 * R, -0.02 * R), (0, 0.07 * R)]
    parts.append(shape(nose, PINK, width=2.8, gaps=0, smooth=False, shift=False))

    # closed little "w" mouth while idle
    mt = 0.2 * R
    w_mouth = [(-0.2 * R, mt - 0.06 * R), (-0.1 * R, mt + 0.06 * R), (0, mt - 0.04 * R), (0.1 * R, mt + 0.06 * R), (0.2 * R, mt - 0.06 * R)]
    parts.append('<g><animate attributeName="opacity" values="1;0;0;1;1" keyTimes="0;0.05;0.84;0.9;1" begin="yawn.begin" dur="%s"/>' % yd
                 + ink(stroke(catmull(w_mouth, closed=False, n=6), 3.6, gaps=0), False) + '</g>')

    # big yawning mouth, scaled open from its top edge
    mw, mh = R * 0.36, R * 0.62
    mouth = np.array([(-mw, 0)] + [(mw * math.cos(a), mh * math.sin(a)) for a in np.linspace(math.pi, 0, 16)][1:])
    tongue = ellipse_pts(0, mh * 0.72, mw * 0.5, mh * 0.24)
    fangs = [[(sgn * mw * 0.62 - 0.06 * R, 0), (sgn * mw * 0.62 + 0.06 * R, 0), (sgn * mw * 0.62, 0.14 * R)] for sgn in (1, -1)]
    mouth_svg = (fill(mouth, RED, (0, 0), False) + fill(tongue, TONGUE, (0, 0), False)
                 + "".join(fill(f, PAPER, (0, 0), False) for f in fangs)
                 + ink(stroke(np.vstack([mouth, mouth[:1]]), 4.2, gaps=0, taper=False), False))
    parts.append(f'<g transform="translate(0 {mt:.1f})"><g opacity="0">'
                 f'<animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.06;0.8;0.86;1" begin="yawn.begin" dur="{yd}"/>'
                 '<g>' + spline_anim("scale", ["1 0.12", "1 1", "1 0.9", "1 1", "1 0.12", "1 0.12"],
                                     [0, 0.22, 0.4, 0.6, 0.84, 1], yb, yd)
                 + mouth_svg + '</g></g></g>')

    # whiskers fan out while yawning
    for sgn in (1, -1):
        base = np.array([sgn * 0.42 * R, 0.1 * R])
        g = [spline_anim("rotate", [f"{v} {base[0]:.1f} {base[1]:.1f}" for v in (0, sgn * -10, sgn * -10, 0, 0)],
                         [0, 0.22, 0.6, 0.84, 1], yb, yd)]
        for k, L in ((-0.35, 1.0), (0.0, 1.15), (0.35, 0.95)):
            dv = np.array([sgn * math.sin(k), math.cos(k)]) * 0.55 + np.array([sgn * 0.75, 0])
            dv /= np.hypot(*dv)
            g.append(ink(stroke([base, base + dv * R * 0.6 * L, base + dv * R * 1.1 * L + np.array([0, 6])], 2.4, gaps=0, jitter=0.6), False))
        parts.append('<g>' + "".join(g) + '</g>')
    parts.append('</g></g>')

    # hand-drawn burst lines beside the head (from the poster): pop on tap and during the yawn
    burst = "".join(ink(stroke([a, b], 3.4, gaps=0)) for a, b in (((420, 448), (408, 432)), ((404, 470), (386, 462)), ((398, 496), (378, 497))))
    parts.append('<g opacity="0">'
                 '<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.12;0.7;1" begin="boop.begin" dur="0.8s"/>'
                 '<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.15;0.75;1" begin="yawn.begin+0.6s" dur="1.6s"/>'
                 + burst + '</g>')

    # whole-cat squash & stretch when tapped
    sq = (vw / 2, vh * 0.55)
    parts.insert(0, f'<g transform="translate({sq[0]:.1f} {sq[1]:.1f})"><g>'
                    '<animateTransform attributeName="transform" type="scale" values="1 1;1.06 0.95;0.97 1.03;1 1" '
                    'keyTimes="0;0.3;0.65;1" begin="boop.begin" dur="0.5s"/>'
                    f'<g transform="translate({-sq[0]:.1f} {-sq[1]:.1f})">')
    parts.append('</g></g></g>')

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw:.0f} {vh:.0f}" width="{vw:.0f}" height="{vh:.0f}" role="img" aria-label="Gray cat stretching and yawning">
<defs>
<filter id="boil" x="-5%" y="-5%" width="110%" height="110%">
<feTurbulence type="fractalNoise" baseFrequency="0.045" numOctaves="2" seed="1"><animate attributeName="seed" values="1;6;11;3" dur="0.56s" calcMode="discrete" repeatCount="indefinite"/></feTurbulence>
<feDisplacementMap in="SourceGraphic" scale="2.6" xChannelSelector="R" yChannelSelector="G"/>
</filter>
</defs>
<rect width="0" height="0"><animate id="yawn" attributeName="x" from="0" to="0" dur="{yd}" begin="1.5s; yawn.end+5s" restart="whenNotActive"/></rect>
<rect width="0" height="0"><animate id="boop" attributeName="y" from="0" to="0" dur="0.5s" begin="indefinite"/></rect>
<g filter="url(#boil)">
{"".join(parts)}
</g>
</svg>
'''
    return svg

svg = build()
with open(os.path.join(HERE, "miu-cat.svg"), "w") as f:
    f.write(svg)

js = """// <miu-cat> — the XXD 017 gray cat, alive. Tap / click to make it yawn.
// Usage: <script src="miu-cat.js"></script>  <miu-cat style="width:240px"></miu-cat>
(() => {
  const SVG = __SVG__;
  class MiuCat extends HTMLElement {
    connectedCallback() {
      if (this.shadowRoot) return;
      const root = this.attachShadow({ mode: "open" });
      root.innerHTML = `<style>:host{display:inline-block;cursor:pointer;-webkit-tap-highlight-color:transparent}
        svg{display:block;width:100%;height:auto;overflow:visible}</style>` + SVG;
      this.svg = root.querySelector("svg");
      this.yawnAnim = root.getElementById("yawn");
      this.boopAnim = root.getElementById("boop");
      // a tap during a yawn is queued so the next yawn follows straight after
      this.yawning = false;
      this.queued = false;
      this.yawnAnim.addEventListener("beginEvent", () => { this.yawning = true; });
      this.yawnAnim.addEventListener("endEvent", () => {
        this.yawning = false;
        if (this.queued) { this.queued = false; setTimeout(() => this.yawn(false), 120); }
      });
      this.addEventListener("click", () => this.yawn());
      this.setAttribute("role", "img");
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
      const sync = () => (reduce.matches ? this.svg.pauseAnimations() : this.svg.unpauseAnimations());
      reduce.addEventListener?.("change", sync);
      sync();
      // pause while scrolled out of view to save battery
      this.io = new IntersectionObserver(([e]) => {
        if (reduce.matches) return;
        e.isIntersecting ? this.svg.unpauseAnimations() : this.svg.pauseAnimations();
      });
      this.io.observe(this);
    }
    disconnectedCallback() { this.io?.disconnect(); }
    yawn(boop = true) {
      try {
        if (boop) this.boopAnim.beginElement();  // instant squish + ear flick on every tap
        if (this.yawning) this.queued = true;
        else this.yawnAnim.beginElement();
      } catch (_) {}
    }
  }
  if (!customElements.get("miu-cat")) customElements.define("miu-cat", MiuCat);
})();
"""

import json
js = js.replace("__SVG__", json.dumps(svg.strip()))
with open(os.path.join(HERE, "miu-cat.js"), "w") as f:
    f.write(js)
print("svg bytes", len(svg), "viewBox", svg.split('viewBox="')[1].split('"')[0])
