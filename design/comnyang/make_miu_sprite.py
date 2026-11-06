"""Feed the approved Miu pattern into design/miu-pixel.js (the animated sprite used by the app).

Runs make_miu_pattern.py to get the zone shapes and Miu's colours, then writes absolute pixels
for each zone (plus the pieces the extra poses need) between /*DATA*/ and /*END DATA*/.
"""
import json, pathlib, re, runpy

HERE = pathlib.Path(__file__).parent
P = runpy.run_path(str(HERE / 'make_miu_pattern.py'))
SHAPES, paint, GRAY, STRIPE = P['SHAPES'], P['paint'], P['GRAY'], P['STRIPE']
RING_DARK, RING_LIGHT = P['RING_DARK'], P['RING_LIGHT']

zones = {}
for z in ['tail', 'body', 'legFl', 'legFr', 'earL', 'earR', 'head']:
    zones[z] = [[x, y, paint[z].get((x, y), GRAY)] for (x, y) in sorted(SHAPES[z]['cells'], key=lambda c: (c[1], c[0]))]

# focus pose: a headband across the head (rows 6-7, wherever the head is)
band = [[x, y] for (x, y) in sorted(SHAPES['head']['cells']) if y in (6, 7)]

# break pose: a long loaf behind the head, with stripes along the back
flop_body = []
inset = {21: 5, 22: 3, 23: 2, 24: 1, 32: 1, 33: 2}
for y in range(21, 34):
    for x in range(9 + inset.get(y, 0), 34 - inset.get(y, 0)):
        flop_body.append([x, y, GRAY])
stripes = {(14, 22), (14, 23), (19, 21), (19, 22), (24, 21), (24, 22), (29, 22), (29, 23)}
flop_body = [[x, y, STRIPE if (x, y) in stripes else c] for x, y, c in flop_body]
# its ringed tail lies along the cushion in front and curls up at the end
flop_tail = []
for x in range(18, 35):
    ring = RING_DARK if x <= 19 or ((x - 20) // 2) % 2 else RING_LIGHT
    for y in (32, 33): flop_tail.append([x, y, ring])
flop_tail += [[34, 31, RING_LIGHT], [35, 31, RING_LIGHT], [35, 30, RING_DARK], [36, 30, RING_DARK], [36, 29, RING_DARK]]

data = {'zones': zones, 'band': band, 'flopBody': flop_body, 'flopTail': flop_tail}
js_path = HERE.parent / 'miu-pixel.js'
js = js_path.read_text(encoding='utf-8')
js, n = re.subn(r'/\*DATA\*/.*?/\*END DATA\*/', lambda m: '/*DATA*/' + json.dumps(data, separators=(',', ':')) + '/*END DATA*/', js, flags=re.S)
assert n == 1
js_path.write_text(js, encoding='utf-8')
print('wrote', js_path, {k: len(v) for k, v in zones.items()}, 'band', len(band), 'flop', len(flop_body))
