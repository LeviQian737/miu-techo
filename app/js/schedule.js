// Flexible scheduling for one day's plan.
// - Flowing blocks keep only their order and length; they are laid out back to back from day.flowStart.
// - Pinned blocks keep their clock time; flowing blocks jump over them.
// - The first unfinished block that should already have started is "current": it stretches to now.
// - Cushions (buffers) absorb that overrun first: a cushion ends where it ended in the plan, or at once.
// - Anything pushed past midnight lands in the overflow tray.

export const DAY_END = 24 * 60;

function skip(t, d, pins){
  let moved = true;
  while (moved){
    moved = false;
    for (const p of pins) if (t < p.e && t + d > p.s){ t = p.e; moved = true; }
  }
  return t;
}

// now: minutes since midnight for today, Infinity for past days, -Infinity for future days
function place(day, now, baseline){
  const pins = day.items.filter(x => x.pinned).map(x => ({ x, s: x.start, e: x.start + x.dur }));
  const res = new Map();
  let t = day.flowStart, cur = null;
  for (const p of pins) res.set(p.x.id, { s: p.s, e: p.e });
  for (const it of day.items){
    if (it.pinned) continue;
    if (it.kind === 'cushion'){
      t = skip(t, Math.max(1, it.dur), pins);
      if (baseline){
        const b = baseline.get(it.id);
        const e = Math.max(t, b ? b.e : t + it.dur);
        res.set(it.id, { s: t, e }); t = e;
      } else { res.set(it.id, { s: t, e: t + it.dur }); t += it.dur; }
      continue;
    }
    t = skip(t, it.dur, pins);
    const s = t; let e = s + (it.done ? (it.actual ?? it.dur) : it.dur);
    if (baseline && !it.done && !cur && s <= now && Number.isFinite(now)){ cur = it; e = Math.max(e, now); }
    res.set(it.id, { s, e }); t = e;
  }
  return { res, cur };
}

export function layout(day, now){
  const base = place(day, now, null).res;
  const { res, cur } = place(day, now, base);
  const overflow = day.items.filter(it => !it.pinned && it.kind !== 'cushion' && res.get(it.id).e > DAY_END + 0.01);
  const clashes = new Set();
  for (const p of day.items.filter(x => x.pinned)){
    for (const it of day.items){
      if (it.pinned || it.kind === 'cushion') continue;
      const r = res.get(it.id);
      if (r.s < p.start + p.dur && r.e > p.start + 0.01) clashes.add(p.id);
    }
  }
  return { res, cur, overflow, clashes };
}

export const minOf = it => it.min || Math.max(10, Math.round(it.dur * 0.5 / 5) * 5);

// shorten later, unstarted blocks (last first) toward their minimum until nothing overflows
export function squeeze(day, now){
  for (let guard = 0; guard < 200; guard++){
    const L = layout(day, now);
    if (!L.overflow.length) return;
    const cand = [...day.items].reverse().find(x => !x.done && !x.pinned && x.kind !== 'cushion'
      && L.cur !== x && x.dur > minOf(x) && L.res.get(x.id).s >= (Number.isFinite(now) ? now : -1));
    if (!cand) return;
    cand.dur = Math.max(minOf(cand), cand.dur - 5); cand.squeezed = true;
  }
}

// where a block dropped at minute T should go in the flowing order
export function insertIndex(day, L, T, excl){
  for (let i = 0; i < day.items.length; i++){
    const x = day.items[i];
    if (x === excl || x.pinned) continue;
    const r = L.res.get(x.id);
    if (r && r.s >= T - 1) return i;
  }
  return day.items.length;
}
