import { getState, getDay, day, update, subscribe, uid, dayKey, keyToDate, shiftKey, COLORS } from './store.js';
import { layout, squeeze, insertIndex, DAY_END } from './schedule.js';

/* ---------- helpers ---------- */
const PPM = 1.2;                       // timeline pixels per minute (keep in sync with --ppm)
const $ = s => document.querySelector(s);
const pad = n => String(n).padStart(2, '0');
const fmt = m => { m = Math.max(0, Math.round(m)); return pad(Math.floor(m / 60)) + ':' + pad(m % 60); };
const dur = m => { m = Math.round(m); return Math.floor(m / 60) + ':' + pad(m % 60); };
const r5 = m => Math.round(m / 5) * 5;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const tallyStr = n => '正'.repeat(Math.floor(n / 5)) + ['', '一', '丅', '下', '止'][n % 5];
const nowMin = () => { const d = new Date(); return d.getHours() * 60 + d.getMinutes() + d.getSeconds() / 60; };
const todayKey = () => dayKey(new Date());
const nowFor = key => key === todayKey() ? nowMin() : key < todayKey() ? Infinity : -Infinity;
const colorOf = it => it.kind === 'popup' ? 'yamabuki' : (it.color || 'sora');
const loggedFor = (D, id) => D.logs.filter(l => l.itemId === id).reduce((a, l) => a + (l.end - l.start), 0);

let viewKey = todayKey();
let sel = null, selLog = null, L = null, lastMin = -1;
const plan = $('#plan'), act = $('#act'), tl = $('#tl'), center = $('#center'), pop = $('#pop');
const miu = window.MiuPixel ? window.MiuPixel.mount($('#miuHost')) : null;

/* ---------- timer ---------- */
function addLogMs(S, T, a, b){
  if (b - a < 60000) return;                       // under a minute: not worth a record
  const D = day(T.day), base = keyToDate(T.day).getTime();
  const s = Math.round((a - base) / 60000), e = Math.min(DAY_END, Math.round((b - base) / 60000));
  if (e - s < 1) return;
  const it = D.items.find(x => x.id === T.itemId);
  D.logs.push({ id: uid(), itemId: T.itemId, title: it ? it.title : '', color: it ? colorOf(it) : 'sora', start: s, end: e });
}
function closeTimer(S, endMs){
  const T = S.timer; if (!T) return;
  if (T.mode === 'stopwatch' || T.phase === 'focus') addLogMs(S, T, T.phaseStart, endMs);
  S.timer = null;
}
function startTimer(itemId){
  const k = todayKey();
  if (viewKey !== k){ viewKey = k; render(); scrollToNow(); }
  sel = null;
  update(S => {
    if (S.timer) closeTimer(S, Date.now());
    const D = day(k), it = D.items.find(x => x.id === itemId);
    if (!it || it.kind === 'cushion') return;
    it.done = false;
    // doing this now: it becomes the current block
    const Lx = layout(D, nowMin());
    if (!it.pinned && Lx.cur !== it){
      D.items.splice(D.items.indexOf(it), 1);
      const anchor = Lx.cur || D.items.find(x => !x.done && !x.pinned && x.kind !== 'cushion');
      D.items.splice(anchor ? D.items.indexOf(anchor) : D.items.length, 0, it);
    }
    // it was planned for later but you're starting now: the day's flow starts now
    const firstFlow = D.items.find(x => !x.pinned);
    if (firstFlow === it && D.flowStart > nowMin()) D.flowStart = Math.floor(nowMin() / 5) * 5;
    S.timer = { itemId, day: k, mode: S.settings.timerMode, phase: 'focus', phaseStart: Date.now() };
  });
}
function stopTimer(){ update(S => closeTimer(S, Date.now())); }
function tick(){
  const S = getState(), T = S.timer;
  if (T && T.mode === 'pomodoro'){
    const focus = S.settings.focusMin * 60000, brk = S.settings.breakMin * 60000, now = Date.now();
    if (T.phase === 'focus' && now - T.phaseStart >= focus){
      update(S2 => {
        const t = S2.timer, end = t.phaseStart + focus;
        addLogMs(S2, t, t.phaseStart, end);
        const it = day(t.day).items.find(x => x.id === t.itemId); if (it) it.tally = (it.tally || 0) + 1;
        t.phase = 'break'; t.phaseStart = end;
      });
    } else if (T.phase === 'break' && now - T.phaseStart >= brk){
      update(S2 => { S2.timer = null; });
    }
  }
  renderTimer();
  const m = Math.floor(nowMin());
  if (m !== lastMin && !drag && !rez && !logDrag && !draft){ lastMin = m; render(); }
}

/* ---------- render ---------- */
function render(){
  const D = getDay(viewKey), now = nowFor(viewKey);
  L = layout(D, now);
  renderHeader(); renderRack(); renderPile(); renderTimeline(D, now); renderSide(D); renderTimer();
  if (miu) miu.setMode(miuMode());
}
function renderHeader(){
  const d = keyToDate(viewKey);
  $('#date').textContent = (d.getMonth() + 1) + '.' + d.getDate();
  $('#dow').textContent = '日月火水木金土'[d.getDay()];
  $('#todayBtn').classList.toggle('show', viewKey !== todayKey());
}
function renderRack(){
  const S = getState();
  $('#rack').innerHTML = S.templates.map(tp => tp.cushion
    ? `<div class="roll cushion" data-drag="tpl" data-id="${tp.id}"><span class="core"></span><span class="strip"><svg style="width:34px;height:20px;color:var(--ink-soft)"><use href="#i-nap"/></svg></span></div>`
    : `<div class="roll" data-drag="tpl" data-id="${tp.id}"><span class="core" style="background:var(--${tp.color})"></span><span class="strip" style="background:var(--${tp.color});width:${Math.min(200, 52 + tp.dur * 1.6)}px">${esc(tp.title)}</span></div>`
  ).join('') + `<div class="roll add" id="addTpl" tabindex="0" aria-label="新胶带"><span class="core"><svg class="i" style="width:14px;height:14px"><use href="#i-plus"/></svg></span></div>`;
}
function renderPile(){
  const S = getState();
  $('#pile').innerHTML = `<div class="note add" id="addNote" tabindex="0" aria-label="新便利贴"><svg class="i" style="width:26px;height:26px"><use href="#i-plus"/></svg></div>` +
    S.inbox.map(n => `<div class="note" data-drag="note" data-id="${n.id}">${esc(n.title)}<span class="len" style="width:${Math.min(90, n.dur * 1.2)}%"></span></div>`).join('');
}
function renderTimeline(D, now){
  const S = getState(), T = S.timer;
  tl.style.height = (DAY_END * PPM + 150) + 'px';
  let h = '';
  for (let hr = 0; hr <= 24; hr++) h += `<div class="hr" style="top:${hr * 60 * PPM}px"><span>${hr}</span></div>`;
  for (const it of D.items){
    const r = L.res.get(it.id);
    if (!it.pinned && r.e > DAY_END + 0.01) continue;
    h += blockHTML(D, it, r, T);
  }
  h += `<div class="endline" style="top:${DAY_END * PPM}px"></div>`;
  if (Number.isFinite(now)) h += `<div class="now" style="top:${now * PPM}px"><span class="t">${fmt(now)}</span></div>`;
  const of = L.overflow;
  h += `<div class="tray zone ${of.length ? 'has' : ''}" data-zone="tray" style="top:${DAY_END * PPM + 22}px">
      <svg class="moon"><use href="#i-moon"/></svg>
      ${of.map(it => `<div class="mini k-${it.kind}" data-drag="blk" data-id="${it.id}" style="--c:var(--${colorOf(it)})">${esc(it.title)}</div>`).join('')}
      ${of.length ? `<span class="tbtns"><button data-act="squeeze" aria-label="压缩之后的块"><svg class="i"><use href="#i-squeeze"/></svg></button><button data-act="tomorrow" aria-label="挪到明天"><svg class="i"><use href="#i-next"/></svg></button></span>` : ''}
    </div>`;
  plan.innerHTML = h;
  // actual lane: overlapping records sit side by side
  let a = '';
  const cols = logColumns(D.logs);
  for (const l of D.logs) a += logHTML(l, cols.get(l.id));
  if (T && T.day === viewKey && (T.mode === 'stopwatch' || T.phase === 'focus')){
    const base = keyToDate(T.day).getTime(), s = (T.phaseStart - base) / 60000, e = Math.min(DAY_END, (Date.now() - base) / 60000);
    const it = D.items.find(x => x.id === T.itemId);
    a += `<div class="log live" style="top:${s * PPM}px;height:${Math.max(3, (e - s) * PPM)}px;--c:var(--${it ? colorOf(it) : 'sora'})"></div>`;
  }
  act.innerHTML = a;
}
function blockHTML(D, it, r, T){
  const top = r.s * PPM, ht = Math.max(0, (r.e - r.s) * PPM);
  if (it.kind === 'cushion'){
    const cls = ht < 3 ? 'spent' : ht < 14 ? 'thin' : '';
    return `<div class="blk k-cushion ${cls} ${sel === it.id ? 'sel' : ''}" data-drag="blk" data-id="${it.id}" style="top:${top}px;height:${Math.max(ht, 3)}px">
      <div class="bg"></div><svg class="nap"><use href="#i-nap"/></svg><div class="grip" data-grip></div></div>`;
  }
  const isCur = L.cur === it, planEnd = r.s + it.dur;
  const over = isCur && r.e > planEnd ? (r.e - planEnd) * PPM : 0;
  const got = loggedFor(D, it.id);
  const running = T && T.itemId === it.id && T.day === viewKey;
  const cls = ['blk', 'k-' + it.kind, it.done && 'done', isCur && 'cur', running && 'running', it.pinned && 'pinned',
    sel === it.id && 'sel', ht < 34 && 'compact', L.clashes.has(it.id) && 'clash', it.squeezed && 'squeezed'].filter(Boolean).join(' ');
  return `<div class="${cls}" data-drag="blk" data-id="${it.id}" style="top:${top}px;height:${ht}px;--c:var(--${colorOf(it)})">
    <div class="bg"></div>
    ${over ? `<div class="over" style="height:${over}px"></div>` : ''}
    <div class="txt"><span class="ti">${esc(it.title)}</span><span class="tm">${fmt(r.s)}–${fmt(r.e)}</span>${it.tally ? `<span class="tally">${tallyStr(it.tally)}</span>` : ''}</div>
    ${got ? `<div class="got"><i style="width:${Math.min(100, got / it.dur * 100)}%"></i></div>` : ''}
    ${it.done ? `<svg class="stamp"><use href="#i-stamp"/></svg>` : ''}
    <svg class="pinmark"><use href="#i-pin"/></svg>
    <div class="acts">
      <button data-act="timer" aria-label="开始计时"><svg class="i"><use href="#i-play"/></svg></button>
      <button data-act="log" aria-label="补记时间"><svg class="i"><use href="#i-pen"/></svg></button>
      <button data-act="done" class="${it.done ? 'on' : ''}" aria-label="完成"><svg class="i" style="width:20px;height:20px"><use href="#i-stamp"/></svg></button>
      <button data-act="pin" class="${it.pinned ? 'on' : ''}" aria-label="钉住时间"><svg class="i"><use href="#i-pin"/></svg></button>
    </div>
    ${it.pinned || it.done ? '' : '<div class="grip" data-grip></div>'}
  </div>`;
}
// group overlapping records and give each a column inside its group
function logColumns(logs){
  const out = new Map(), sorted = [...logs].sort((a, b) => a.start - b.start || a.end - b.end);
  let group = [], groupEnd = -1;
  const flush = () => {
    const ends = [];
    for (const l of group){
      let c = ends.findIndex(e => e <= l.start);
      if (c < 0){ c = ends.length; ends.push(0); }
      ends[c] = l.end; out.set(l.id, { c });
    }
    for (const l of group) out.get(l.id).n = ends.length;
    group = [];
  };
  for (const l of sorted){
    if (group.length && l.start >= groupEnd){ flush(); groupEnd = -1; }
    group.push(l); groupEnd = Math.max(groupEnd, l.end);
  }
  if (group.length) flush();
  return out;
}
function logHTML(l, col = { c: 0, n: 1 }){
  const ht = (l.end - l.start) * PPM;
  const w = 100 / col.n, pos = col.n > 1 ? `left:calc(${col.c * w}% + 8px);right:auto;width:calc(${w}% - 12px);` : '';
  return `<div class="log ${ht < 18 ? 'tiny' : ''} ${selLog === l.id ? 'sel' : ''}" data-log="${l.id}" style="${pos}top:${l.start * PPM}px;height:${Math.max(3, ht)}px;--c:var(--${l.color})">
    <span class="lt">${esc(l.title)}<b>${fmt(l.start)}–${fmt(l.end)}</b></span>
    <span class="h top" data-h="top"></span><span class="h bot" data-h="bot"></span>
    <button class="x" data-act="dellog" aria-label="删除这条记录"><svg class="i"><use href="#i-x"/></svg></button>
  </div>`;
}
function renderSide(D){
  const total = D.logs.reduce((a, l) => a + (l.end - l.start), 0);
  $('#sum').innerHTML = `<svg class="i"><use href="#i-clock"/></svg>${dur(total)}`;
  $('#tallyBig').textContent = tallyStr(D.items.reduce((a, it) => a + (it.tally || 0), 0));
  $('#stamps').innerHTML = D.items.filter(it => it.done).map(() => '<svg><use href="#i-stamp"/></svg>').join('');
}
const prog = $('#prog'), CIRC = 2 * Math.PI * 124;
prog.style.strokeDasharray = CIRC;
function renderTimer(){
  const S = getState(), T = S.timer, now = Date.now();
  let txt, frac = 0, brk = false;
  const mode = T ? T.mode : S.settings.timerMode;
  if (!T) txt = mode === 'pomodoro' ? pad(S.settings.focusMin) + ':00' : '00:00';
  else if (T.mode === 'stopwatch'){
    const s = Math.floor((now - T.phaseStart) / 1000);
    txt = s >= 3600 ? Math.floor(s / 3600) + ':' + pad(Math.floor(s / 60) % 60) + ':' + pad(s % 60) : pad(Math.floor(s / 60)) + ':' + pad(s % 60);
    frac = (s % 3600) / 3600;
  } else {
    const len = (T.phase === 'focus' ? S.settings.focusMin : S.settings.breakMin) * 60;
    const left = Math.max(0, Math.ceil(len - (now - T.phaseStart) / 1000));
    txt = pad(Math.floor(left / 60)) + ':' + pad(left % 60); frac = left / len; brk = T.phase === 'break';
  }
  const tEl = $('#timer'); tEl.textContent = txt; tEl.className = 'timer' + (brk ? ' break' : '');
  prog.style.stroke = brk ? 'var(--matcha)' : 'var(--yamabuki)';
  // stopwatch: the ring fills over each hour; pomodoro: it empties as the phase runs out
  prog.style.strokeDashoffset = T ? CIRC * (1 - frac) : CIRC;
  $('#go').disabled = !!T; $('#stop').disabled = !T;
  document.querySelectorAll('#modes button').forEach(b => { b.setAttribute('aria-checked', b.dataset.mode === mode); b.disabled = !!T; });
  const it = T && getDay(T.day).items.find(x => x.id === T.itemId);
  const tg = $('#target'), want = it ? `<span class="chip" style="--c:var(--${colorOf(it)})"></span>${esc(it.title)}` : '';
  if (tg.innerHTML !== want) tg.innerHTML = want;
}
function miuMode(){
  const T = getState().timer;
  if (T) return T.mode === 'pomodoro' && T.phase === 'break' ? 'break' : 'focus';
  const Lt = layout(getDay(todayKey()), nowMin());
  return Lt.overflow.length || Lt.clashes.size ? 'worried' : 'idle';
}
function scrollToNow(){
  const m = viewKey === todayKey() ? nowMin() - 150 : 7 * 60;
  center.scrollTop = Math.max(0, m * PPM);
}

/* ---------- block actions ---------- */
function editDay(fn){ update(S => fn(day(viewKey), S)); }
function toggleDone(id){
  let cheered = false;
  editDay((D, S) => {
    const it = D.items.find(x => x.id === id); if (!it) return;
    if (it.done){ it.done = false; return; }
    const r = L.res.get(it.id), got = loggedFor(D, it.id);
    it.actual = got > 0 ? Math.max(5, r5(got)) : L.cur === it ? Math.max(5, r5(nowMin() - r.s)) : it.dur;
    it.done = true; cheered = true;
    if (S.timer && S.timer.itemId === it.id && S.timer.day === viewKey) closeTimer(S, Date.now());
  });
  if (cheered && miu) setTimeout(() => miu.cheer(), 0);
}
function togglePin(id){
  editDay(D => {
    const it = D.items.find(x => x.id === id); if (!it) return;
    const r = L.res.get(it.id);
    if (it.pinned){ it.pinned = false; D.items.splice(D.items.indexOf(it), 1); D.items.splice(insertIndex(D, L, it.start, it), 0, it); }
    else { it.pinned = true; it.start = r5(r.s); }
  });
}
function placeAt(D, it, T){
  const idx = insertIndex(D, L, T, it);
  D.items.splice(idx, 0, it);
  const firstFlow = D.items.find(x => !x.pinned);
  if (firstFlow === it) D.flowStart = clamp(r5(T), 0, DAY_END - 5);   // dropped before everything: the day starts here
}

/* ---------- popovers ---------- */
function openPop(x, y, html, onReady){
  pop.innerHTML = html; pop.hidden = false;
  const w = pop.offsetWidth, h = pop.offsetHeight;
  pop.style.left = clamp(x, 8, innerWidth - w - 8) + 'px';
  pop.style.top = clamp(y, 8, innerHeight - h - 8) + 'px';
  if (onReady) onReady(pop);
}
function closePop(){ pop.hidden = true; pop.innerHTML = ''; }
function pickItem(x, y, onPick){
  const D = getDay(viewKey), items = D.items.filter(it => it.kind !== 'cushion');
  openPop(x, y, items.length
    ? `<div class="pick">${items.map(it => `<button data-pick="${it.id}"><span class="chip" style="--c:var(--${colorOf(it)})"></span>${esc(it.title)}</button>`).join('')}</div>`
    : `<div class="empty">先放一个块到计划里</div>`, p => {
      p.onclick = e => { const b = e.target.closest('[data-pick]'); if (b){ closePop(); onPick(b.dataset.pick); } };
    });
}
function logForm(it, x, y){
  const r = L.res.get(it.id), now = nowFor(viewKey);
  let s = r5(r.s), e = r5(r.s + it.dur);
  if (Number.isFinite(now) && now > s && now < e) e = r5(now);
  const toMin = v => { const [hh, mm] = v.split(':').map(Number); return hh * 60 + mm; };
  openPop(x, y, `<form><input type="time" name="s" value="${fmt(s)}" step="300" required>–<input type="time" name="e" value="${fmt(e)}" step="300" required>
    <button class="ok" aria-label="记录"><svg class="i"><use href="#i-pen"/></svg></button></form>`, p => {
    const f = p.querySelector('form'); f.s.focus();
    f.onsubmit = ev => {
      ev.preventDefault();
      const a = toMin(f.s.value), b = toMin(f.e.value);
      if (!(b > a)){ f.e.focus(); return; }
      closePop();
      editDay(D => D.logs.push({ id: uid(), itemId: it.id, title: it.title, color: colorOf(it), start: a, end: Math.min(b, DAY_END) }));
    };
  });
}

/* ---------- clicks ---------- */
let swallowClick = false;   // the click that ends a drag shouldn't also close what the drag opened
document.addEventListener('click', e => {
  if (swallowClick){ swallowClick = false; return; }
  if (!pop.hidden && !e.target.closest('#pop')) closePop();
  const b = e.target.closest('[data-act]');
  if (b){
    const blk = b.closest('[data-id]'), id = blk && blk.dataset.id, a = b.dataset.act;
    if (a === 'timer') return startTimer(id);
    if (a === 'log'){ const it = getDay(viewKey).items.find(x => x.id === id); const rc = b.getBoundingClientRect(); return logForm(it, rc.right + 8, rc.top - 10); }
    if (a === 'done') return toggleDone(id);
    if (a === 'pin') return togglePin(id);
    if (a === 'squeeze') return editDay(D => squeeze(D, nowFor(viewKey)));
    if (a === 'tomorrow') return update(S => {
      const D = day(viewKey), N = day(shiftKey(viewKey, 1)), moving = L.overflow.slice();
      for (const it of moving){ D.items.splice(D.items.indexOf(it), 1); Object.assign(it, { done: false, squeezed: false }); N.items.push(it); }
    });
    if (a === 'dellog'){ const id2 = b.closest('[data-log]').dataset.log; selLog = null; return editDay(D => { D.logs = D.logs.filter(l => l.id !== id2); }); }
    return;
  }
  if (!e.target.closest('.theme')) $('#theme').classList.remove('open');
});
$('#themeBtn').onclick = () => $('#theme').classList.toggle('open');
$('#prevDay').onclick = () => { viewKey = shiftKey(viewKey, -1); sel = selLog = null; render(); scrollToNow(); };
$('#nextDay').onclick = () => { viewKey = shiftKey(viewKey, 1); sel = selLog = null; render(); scrollToNow(); };
$('#todayBtn').onclick = () => { viewKey = todayKey(); sel = selLog = null; render(); scrollToNow(); };
$('#modes').onclick = e => { const b = e.target.closest('[data-mode]'); if (b && !getState().timer) update(S => { S.settings.timerMode = b.dataset.mode; }); };
$('#go').onclick = () => {
  const D = getDay(todayKey()), Lt = layout(D, nowMin());
  const pick = (viewKey === todayKey() && sel && D.items.find(x => x.id === sel && x.kind !== 'cushion')) || Lt.cur;
  if (pick) return startTimer(pick.id);
  const g = $('#go'); g.classList.remove('nudge'); void g.offsetWidth; g.classList.add('nudge');   // nothing to time yet
};
$('#stop').onclick = stopTimer;

// new sticky note / new tape
function inlineInput(host, onDone){
  if (host.querySelector('input')) return;
  host.insertAdjacentHTML('beforeend', '<input maxlength="24" aria-label="名字">');
  const inp = host.querySelector('input'); inp.focus();
  let done = false;
  const commit = ok => { if (done) return; done = true; const v = inp.value.trim(); if (ok && v) onDone(v); else render(); };
  inp.addEventListener('keydown', ev => { if (ev.key === 'Enter') commit(true); if (ev.key === 'Escape') commit(false); });
  inp.addEventListener('blur', () => commit(true));
}
$('#pile').addEventListener('click', e => {
  const add = e.target.closest('#addNote'); if (!add) return;
  add.innerHTML = '';
  inlineInput(add, v => update(S => { S.inbox.unshift({ id: uid(), title: v, dur: 30 }); }));
});
$('#rack').addEventListener('click', e => {
  const add = e.target.closest('#addTpl'); if (!add) return;
  inlineInput(add, v => update(S => {
    const used = S.templates.filter(t => !t.cushion).length;
    S.templates.splice(S.templates.findIndex(t => t.cushion), 0, { id: uid(), title: v, dur: 30, color: COLORS[used % COLORS.length] });
  }));
});
['#pile', '#rack'].forEach(s => $(s).addEventListener('keydown', e => { if (e.key === 'Enter' && (e.target.id === 'addNote' || e.target.id === 'addTpl')) e.target.click(); }));

// rename a block: double-click its name
plan.addEventListener('dblclick', e => {
  const ti = e.target.closest('.ti'); if (!ti) return;
  const id = ti.closest('[data-id]').dataset.id;
  ti.contentEditable = 'true'; ti.focus();
  document.getSelection().selectAllChildren(ti);
  const finish = () => {
    ti.removeEventListener('blur', finish);
    const v = ti.textContent.trim();
    editDay(D => { const it = D.items.find(x => x.id === id); if (it && v) it.title = v.slice(0, 40); });
  };
  ti.addEventListener('blur', finish);
  ti.addEventListener('keydown', ev => { if (ev.key === 'Enter'){ ev.preventDefault(); ti.blur(); } if (ev.key === 'Escape'){ ti.textContent = ''; ti.blur(); } });
});

document.addEventListener('keydown', e => {
  if (e.target.closest('input,[contenteditable=true]')) return;
  if (e.key === 'Escape'){ closePop(); sel = selLog = null; render(); }
  if ((e.key === 'Delete' || e.key === 'Backspace') && selLog){
    const id = selLog; selLog = null; editDay(D => { D.logs = D.logs.filter(l => l.id !== id); });
  }
});

/* ---------- drag & drop, resize, logging on the actual lane ---------- */
let drag = null, rez = null, logDrag = null, draft = null;
const ins = $('#ins');
const timeAtY = y => (y - tl.getBoundingClientRect().top) / PPM;

document.addEventListener('pointerdown', e => {
  if (e.button !== 0 || e.target.closest('#pop')) return;
  const grip = e.target.closest('[data-grip]');
  if (grip){
    const it = getDay(viewKey).items.find(x => x.id === grip.closest('[data-id]').dataset.id);
    rez = { id: it.id, y0: e.clientY, d0: it.dur }; e.preventDefault(); return;
  }
  const lg = e.target.closest('[data-log]');
  if (lg && !e.target.closest('[data-act]') && !lg.classList.contains('live')){
    const l = getDay(viewKey).logs.find(x => x.id === lg.dataset.log);
    logDrag = { id: l.id, mode: e.target.dataset.h || 'move', y0: e.clientY, s0: l.start, e0: l.end, moved: false };
    e.preventDefault(); return;
  }
  if (e.target === act){                       // draw a new record on the actual lane
    const s = clamp(r5(timeAtY(e.clientY)), 0, DAY_END - 5);
    draft = { s, e: s, el: document.createElement('div') };
    draft.el.className = 'draft'; act.appendChild(draft.el); e.preventDefault(); return;
  }
  const src = e.target.closest('[data-drag]');
  if (!src || e.target.closest('[data-act],input,[contenteditable=true]')) return;
  const rc = src.getBoundingClientRect();
  drag = { src, type: src.dataset.drag, id: src.dataset.id, x0: e.clientX, y0: e.clientY, ox: e.clientX - rc.left, oy: e.clientY - rc.top, w: rc.width, h: rc.height, started: false };
});

document.addEventListener('pointermove', e => {
  if (rez){
    const nd = Math.max(5, r5(rez.d0 + (e.clientY - rez.y0) / PPM));
    const it = getDay(viewKey).items.find(x => x.id === rez.id);
    if (it && nd !== it.dur) editDay(D => { D.items.find(x => x.id === rez.id).dur = nd; });
    return;
  }
  if (logDrag){
    const dm = r5((e.clientY - logDrag.y0) / PPM);
    if (dm) logDrag.moved = true;
    editDay(D => {
      const l = D.logs.find(x => x.id === logDrag.id); if (!l) return;
      if (logDrag.mode === 'move'){ const len = logDrag.e0 - logDrag.s0; l.start = clamp(logDrag.s0 + dm, 0, DAY_END - len); l.end = l.start + len; }
      if (logDrag.mode === 'top') l.start = clamp(logDrag.s0 + dm, 0, l.end - 5);
      if (logDrag.mode === 'bot') l.end = clamp(logDrag.e0 + dm, l.start + 5, DAY_END);
    });
    return;
  }
  if (draft){
    draft.e = clamp(r5(timeAtY(e.clientY)), 0, DAY_END);
    const a = Math.min(draft.s, draft.e), b = Math.max(draft.s, draft.e);
    Object.assign(draft.el.style, { top: a * PPM + 'px', height: Math.max(2, (b - a) * PPM) + 'px' });
    draft.el.innerHTML = `<span>${fmt(a)}–${fmt(b)}</span>`;
    return;
  }
  if (!drag) return;
  if (!drag.started){
    if (Math.hypot(e.clientX - drag.x0, e.clientY - drag.y0) < 5) return;
    drag.started = true;
    const g = drag.src.cloneNode(true);
    g.classList.add('ghost'); g.classList.remove('sel');
    Object.assign(g.style, { width: drag.w + 'px', height: drag.h + 'px', top: 0, left: 0, position: 'fixed' });
    document.body.appendChild(g); drag.ghost = g;
    if (drag.type !== 'tpl') drag.src.classList.add('lifted');
    document.body.classList.add('dragging'); sel = null;
  }
  drag.ghost.style.transform = `translate(${e.clientX - drag.ox}px,${e.clientY - drag.oy}px) rotate(2.5deg)`;
  const z = zoneAt(e.clientX, e.clientY);
  document.querySelectorAll('.zone.hot').forEach(n => n.classList.remove('hot'));
  if (z.el) z.el.classList.add('hot');
  if (z.name === 'tl'){
    const D = getDay(viewKey), T = timeAtY(e.clientY - drag.oy);
    const it = drag.type === 'blk' && D.items.find(x => x.id === drag.id);
    let at;
    if (it && it.pinned) at = r5(T);
    else {
      // where the block will really land: before the next flowing block, or at the drop time if it becomes the first
      const i = insertIndex(D, L, T, it || null), nx = D.items[i];
      const first = D.items.slice(0, i).every(x => x.pinned || x === it);
      at = first ? r5(T) : nx ? L.res.get(nx.id).s : lastEnd(D, it, T);
    }
    at = clamp(at, 0, DAY_END);
    ins.style.display = 'block'; ins.style.top = at * PPM + 'px'; ins.querySelector('span').textContent = fmt(at);
  } else ins.style.display = 'none';
  const cr = center.getBoundingClientRect();
  if (e.clientX > cr.left && e.clientX < cr.right){
    if (e.clientY < cr.top + 60) center.scrollTop -= 14; else if (e.clientY > cr.bottom - 50) center.scrollTop += 14;
  }
});
function lastEnd(D, excl, T){
  const flow = D.items.filter(x => x !== excl && !x.pinned);
  if (!flow.length) return r5(T);
  return Math.max(...flow.map(x => L.res.get(x.id).e));
}
function zoneAt(x, y){
  const el = document.elementFromPoint(x, y), z = el && el.closest('[data-zone]');
  return z ? { el: z, name: z.dataset.zone } : {};
}

document.addEventListener('pointerup', e => {
  if (rez){ rez = null; render(); return; }
  if (logDrag){
    const d = logDrag; logDrag = null;
    if (!d.moved){ selLog = selLog === d.id ? null : d.id; sel = null; }
    render(); return;
  }
  if (draft){
    const d = draft; draft = null;
    const a = Math.min(d.s, d.e), b = Math.max(d.s, d.e);
    if (b - a < 5){ d.el.remove(); return; }
    swallowClick = true; setTimeout(() => { swallowClick = false; }, 0);
    pickItem(e.clientX + 10, e.clientY - 20, id => {
      const it = getDay(viewKey).items.find(x => x.id === id);
      editDay(D => D.logs.push({ id: uid(), itemId: id, title: it.title, color: colorOf(it), start: a, end: b }));
    });
    // keep the outline visible until the popover closes
    const obs = new MutationObserver(() => { if (pop.hidden){ d.el.remove(); obs.disconnect(); } });
    obs.observe(pop, { attributes: true });
    return;
  }
  if (!drag) return;
  const d = drag; drag = null;
  if (!d.started){
    if (d.type === 'blk'){ sel = sel === d.id ? null : d.id; selLog = null; render(); }
    return;
  }
  const z = zoneAt(e.clientX, e.clientY);
  const T = timeAtY(e.clientY - d.oy);
  swallowClick = true; setTimeout(() => { swallowClick = false; }, 0);
  d.ghost.remove(); ins.style.display = 'none';
  document.body.classList.remove('dragging');
  document.querySelectorAll('.zone.hot').forEach(n => n.classList.remove('hot'));
  drop(d, z.name, T);
  render();
});

function drop(d, zone, T){
  if (!zone) return;
  const toTL = zone === 'tl' || zone === 'tray';
  const at = zone === 'tray' ? DAY_END + 999 : clamp(T, 0, DAY_END - 5);
  update(S => {
    const D = day(viewKey);
    if (d.type === 'tpl'){
      const tp = S.templates.find(x => x.id === d.id); if (!tp) return;
      if (toTL) placeAt(D, tp.cushion ? { id: uid(), title: '', dur: tp.dur, kind: 'cushion' } : { id: uid(), title: tp.title, dur: tp.dur, color: tp.color, kind: 'routine', tally: 0 }, at);
      else if (zone === 'pile' && !tp.cushion) S.inbox.unshift({ id: uid(), title: tp.title, dur: tp.dur });
      else if (zone === 'trash' && !tp.cushion) S.templates.splice(S.templates.indexOf(tp), 1);
    }
    if (d.type === 'note'){
      const n = S.inbox.find(x => x.id === d.id); if (!n) return;
      if (toTL){ S.inbox.splice(S.inbox.indexOf(n), 1); placeAt(D, { id: n.id, title: n.title, dur: n.dur, kind: 'popup', tally: 0 }, at); }
      else if (zone === 'rack'){ S.inbox.splice(S.inbox.indexOf(n), 1); S.templates.splice(S.templates.findIndex(t => t.cushion), 0, { id: uid(), title: n.title, dur: n.dur, color: 'matcha' }); }
      else if (zone === 'trash') S.inbox.splice(S.inbox.indexOf(n), 1);
    }
    if (d.type === 'blk'){
      const it = D.items.find(x => x.id === d.id); if (!it) return;
      if (toTL){
        if (it.pinned) it.start = clamp(r5(T), 0, DAY_END - it.dur);
        else { D.items.splice(D.items.indexOf(it), 1); placeAt(D, it, at); }
        return;
      }
      if (S.timer && S.timer.itemId === it.id && S.timer.day === viewKey) closeTimer(S, Date.now());
      D.items.splice(D.items.indexOf(it), 1);
      if (zone === 'pile' && it.kind !== 'cushion') S.inbox.unshift({ id: it.id, title: it.title, dur: it.dur });
      if (zone === 'rack' && it.kind !== 'cushion' && !S.templates.some(x => x.title === it.title))
        S.templates.splice(S.templates.findIndex(t => t.cushion), 0, { id: uid(), title: it.title, dur: it.dur, color: it.kind === 'popup' ? 'matcha' : it.color });
    }
  });
}

/* ---------- boot ---------- */
subscribe(() => { if (!drag) render(); });
render();
scrollToNow();
setInterval(tick, 500);   // real-time deltas, so the timer stays right in background tabs too
