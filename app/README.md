# Miu 手帳 (desktop web)

A plain-JavaScript web app — no install, no build tools needed. Data is saved in the browser (localStorage).

## Open it

- **Double-click** `dist/Miu手帳.html` (single file, everything inlined). Rebuild it after code changes:
  `python3 app/build.py`
- **While developing**, serve the folder so the ES modules load:
  `python3 -m http.server 8420 --directory app` → http://localhost:8420

Note: each way of opening (file vs. localhost) is a different browser origin, so they keep separate data.

## Files

- `js/store.js` — state (tape templates, sticky notes, per-day plans + time logs, running timer) and saving
- `js/schedule.js` — flexible plan layout: flowing vs pinned blocks, cushions, overrun, overflow tray, squeeze
- `js/app.js` — rendering and all interactions (drag & drop, timer / pomodoro, manual logging)
- `js/miu-pixel.js` — animated pixel Miu, generated from `design/comnyang/` (see `make_miu_sprite.py`)
- `css/app.css` — the 方眼手帐 look

## How recording works

Everything starts as a block in the plan (left lane). Time only counts when it is recorded in the
actual lane (right): start/stop the timer (free or pomodoro), drag a range on the actual lane and pick
the block, or use the pen on a block to type start/end times. Unrecorded = not done.
