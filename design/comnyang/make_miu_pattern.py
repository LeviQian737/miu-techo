"""Build Miu's comnyang pattern (schemaVersion 2) and a preview PNG.

Zones and their shapes come from comnyang's own cat template (read from the showcase page).
Pattern cells are local to each zone's bounding box; we paint in absolute sprite pixels
and convert. The cat is mirrored around x = 13.5 (abs x <-> 27 - x).
"""
import json, re, sys, datetime, pathlib
from PIL import Image, ImageDraw

OUT = pathlib.Path(__file__).parent

# comnyang zone shapes: (svg path, translate)  — sitting pose
ZONES = {
    'tail':  ("M0 8V7H6V6H8V5H9V4H8V1H9V0H11V1H12V2H13V7H12V8H11V9H9V10H4V9H1V8H0Z", (20, 24)),
    'body':  ("M15 0V1H18V2H20V3H21V6H22V11H21V14H19V15H3V14H1V11H0V6H1V3H2V2H4V1H7V0H15Z", (3, 19)),
    'legFl': ("M6 29V26H7V25H10V26H11V28H12V31H13V32H14V35H13V36H9V35H8V31H7V29H6Z", (0, 0)),
    'legFr': ("M23 29V26H22V25H19V26H18V28H17V31H16V32H15V35H16V36H20V35H21V31H22V29H23Z", (0, 0)),
    'earL':  ("M0 7V4H1V2H2V1H3V0H4V2H5V3H6V7H5V8H1V7H0Z", (5, 2)),
    'earR':  ("M1 3H0V7H1V8H4V7H5V2H4V1H3V0H2V1H1V3Z", (17, 2)),
    'head':  ("M4 3H2V5H1V7H0V12H1V16H3V17H4V18H6V19H16V18H18V17H19V16H20V15H21V12H22V8H21V5H20V4H19V3H17V2H15V1H7V2H4V3Z", (3, 4)),
}
DRAW_ORDER = ['tail', 'body', 'legFl', 'legFr', 'earL', 'earR', 'head']
WHISKERS = [(0, 14, 5, 1), (23, 14, 5, 1), (0, 17, 6, 1), (23, 17, 6, 1)]
EYE_BG = [(7, 11, 1, 3), (11, 11, 1, 3), (8, 10, 3, 5), (16, 11, 1, 3), (20, 11, 1, 3), (17, 10, 3, 5)]
PUPILS = [(8, 11, 3, 3), (17, 11, 3, 3)]

def polygon(d, t):
    pts, x, y = [], 0, 0
    toks = re.findall(r'[MHVZ]|-?\d+(?:\.\d+)?', d)
    i = 0
    while i < len(toks):
        c = toks[i]; i += 1
        if c == 'M': x, y = float(toks[i]), float(toks[i+1]); i += 2
        elif c == 'H': x = float(toks[i]); i += 1
        elif c == 'V': y = float(toks[i]); i += 1
        elif c == 'Z': break
        pts.append((x + t[0], y + t[1]))
    return pts

def inside(poly, px, py):
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > py) != (y2 > py) and px < x1 + (py - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit

SHAPES = {}
for z, (d, t) in ZONES.items():
    poly = polygon(d, t)
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    origin = (int(min(xs)), int(min(ys)))
    cells = {(x, y) for x in range(int(min(xs)), int(max(xs))) for y in range(int(min(ys)), int(max(ys))) if inside(poly, x + .5, y + .5)}
    SHAPES[z] = {'origin': origin, 'cells': cells}

# ---------- Miu's colours ----------
GRAY, STRIPE, WHITE, PALE = '#8D9197', '#5F6369', '#FFFFFF', '#D3D5D9'
PINK_EAR, BLUSH, NOSE, MOUTH = '#F2B3BE', '#F4A7B5', '#D98E87', '#3A3A40'
RING_DARK, RING_LIGHT = '#4E5258', '#C9CCD1'

paint = {z: {} for z in list(ZONES) + ['legRl', 'legRr']}
def put(z, x, y, c, mirror=False):
    for xx in ([x, 27 - x] if mirror else [x]):
        if (xx, y) in SHAPES[z]['cells']: paint[z][(xx, y)] = c
def area(z, x0, x1, y0, y1, c, mirror=False):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1): put(z, x, y, c, mirror)

# ears: pink insides, in the part of the ear the head doesn't cover (abs rows 3-4)
for x, y in [(8, 3), (7, 4), (8, 4)]:
    put('earL', x, y, PINK_EAR); put('earR', 27 - x, y, PINK_EAR)
# head: three forehead stripes, cheek dashes, blush, a ring of white fur around the mouth
area('head', 13, 14, 5, 7, STRIPE)
area('head', 11, 11, 6, 8, STRIPE, mirror=True)
area('head', 4, 5, 12, 12, STRIPE, mirror=True)
area('head', 5, 6, 15, 15, BLUSH, mirror=True)
for y, (a, b) in {14: (11, 16), 15: (10, 17), 16: (10, 17), 17: (11, 16)}.items():
    area('head', a, b, y, y, WHITE)
# mouth copied from the reference, pixel for pixel: a centre line, then a little ω (5 wide, 3 rows)
for x, y in [(13, 14), (11, 15), (13, 15), (15, 15), (11, 16), (12, 16), (14, 16), (15, 16)]: put('head', x, y, MOUTH)
# body: a flatter white chest patch, lower down (the neck between stays gray), side stripes
for y, (a, b) in {23: (10, 17), 24: (9, 18), 25: (10, 17), 26: (12, 15)}.items():
    area('body', a, b, y, y, WHITE)
for y in (24, 27, 30): area('body', 3, 5, y, y, STRIPE, mirror=True)
# front legs: two tabby bands, pale paws
for leg, x0, x1 in (('legFl', 6, 14), ('legFr', 13, 23)):
    for y in (28, 31): area(leg, x0, x1, y, y, STRIPE)
    area(leg, x0, x1, 33, 35, PALE)
# rear legs (8x8, used in other poses): one band, pale paws — local coordinates
for leg in ('legRl', 'legRr'):
    for x in range(8):
        paint[leg][(x, 3)] = STRIPE
        for y in (6, 7): paint[leg][(x, y)] = PALE
# tail: rings along the curve, dark tip
ox, oy = SHAPES['tail']['origin']
for (x, y) in SHAPES['tail']['cells']:
    lx, ly = x - ox, y - oy
    if lx >= 8:   # the upright part: rings by row
        c = RING_DARK if ly <= 1 or ly in (3, 5) else RING_LIGHT if ly in (2, 4) else None
    else:         # the part lying along the floor: rings by column
        c = RING_DARK if lx in (4, 5) else RING_LIGHT if lx in (2, 3, 6, 7) else None
    if c: paint['tail'][(x, y)] = c

# ---------- export (local coordinates per zone) ----------
pattern = {}
for z in ['body', 'earL', 'earR', 'head', 'tail', 'legFl', 'legFr', 'legRl', 'legRr']:
    if z in SHAPES:
        ox, oy = SHAPES[z]['origin']
        cells = [{'x': x - ox, 'y': y - oy, 'color': c} for (x, y), c in paint[z].items()]
    else:
        cells = [{'x': x, 'y': y, 'color': c} for (x, y), c in paint[z].items()]
    pattern[z] = sorted(cells, key=lambda c: (c['y'], c['x']))
# eyes like the reference: the eye background matches the fur, so only the dark pupil shows
pattern.update({'oddEye': False, 'eyeColor': '#1E1E22', 'baseColor': GRAY, 'eyeBgColor': GRAY,
                'eyeColorLeft': '#1E1E22', 'eyeColorRight': '#1E1E22', 'eyePupilScale': 105})
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
desc = 'Miu: gray tabby with forehead stripes, white bib, pale paws and a ringed tail.'
doc = {'schemaVersion': 2, 'app': 'comnyang', 'exportedAt': now,
       'preset': {'name': 'Miu', 'createdAt': now, 'updatedAt': now, 'catName': 'Miu', 'userName': '', 'description': desc, 'pattern': pattern},
       'name': 'Miu', 'cat_name': 'Miu', 'user_name': '', 'description': desc, 'pattern_json': pattern}
(OUT / 'miu-comnyang-pattern.json').write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding='utf-8')

# ---------- preview (same layering as comnyang: zones, whiskers, eyes, white outline) ----------
S, PAD = 14, 3
img = {}
for z in DRAW_ORDER:
    for cell in SHAPES[z]['cells']:
        img[cell] = paint[z].get(cell, GRAY)
    if z == 'legFr':
        for (x, y, w, h) in WHISKERS:
            for xx in range(x, x + w): img[(xx, y)] = '#1A1A1A'
for (x, y, w, h) in EYE_BG:
    for xx in range(x, x + w):
        for yy in range(y, y + h): img[(xx, yy)] = pattern['eyeBgColor']
for (x, y, w, h) in PUPILS:
    for xx in range(x, x + w):
        for yy in range(y, y + h): img[(xx, yy)] = '#1E1E22'
edge = {(x + dx, y + dy) for (x, y) in img for dx in (-1, 0, 1) for dy in (-1, 0, 1)} - set(img)
W, H = 34 + 2 * PAD, 38 + 2 * PAD
im = Image.new('RGB', (W * S, H * S), (17, 17, 17)); dr = ImageDraw.Draw(im)
def box(x, y, col): dr.rectangle([(x + PAD) * S, (y + PAD) * S, (x + PAD + 1) * S - 1, (y + PAD + 1) * S - 1], fill=col)
for p in edge: box(*p, '#FFFFFF')
for (x, y), c in img.items(): box(x, y, c)
im.save(OUT / 'miu-comnyang-preview.png')
print('cells per zone', {z: len(v) for z, v in pattern.items() if isinstance(v, list)})
