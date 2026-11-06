// App state: tape templates, sticky notes, per-day plans and time logs, the running timer.
// Everything is saved to this browser's localStorage after each change.

const KEY = 'miu-techo-v1';
export const uid = () => Math.random().toString(36).slice(2, 10);
const pad = n => String(n).padStart(2, '0');
export const dayKey = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const keyToDate = k => { const [y, m, d] = k.split('-').map(Number); return new Date(y, m - 1, d); };
export const shiftKey = (k, n) => { const d = keyToDate(k); d.setDate(d.getDate() + n); return dayKey(d); };
export const COLORS = ['matcha', 'sora', 'yamabuki', 'sakura', 'fuji'];

function fresh(){
  const t = (title, dur, color) => ({ id: uid(), title, dur, color });
  return {
    version: 1,
    templates: [
      t('晨间拉伸', 20, 'matcha'), t('深度工作', 90, 'sora'), t('看书', 30, 'matcha'), t('健身', 45, 'sakura'),
      t('学日语', 45, 'fuji'), t('复盘', 15, 'yamabuki'), t('陪 Miu 玩', 20, 'sakura'),
      { id: 'cushion', title: '', dur: 15, color: 'sakura', cushion: true },
    ],
    inbox: [],
    days: {},
    timer: null, // {itemId, day, mode:'stopwatch'|'pomodoro', phase:'focus'|'break', phaseStart:ms}
    settings: { focusMin: 25, breakMin: 5, timerMode: 'stopwatch' },
  };
}

function load(){
  try {
    const s = JSON.parse(localStorage.getItem(KEY));
    if (s && s.version === 1) return s;
  } catch (e) { /* private mode or broken data: start fresh */ }
  return fresh();
}

let state = load();
const subs = new Set();
let saveTimer = 0;

export const getState = () => state;
export function getDay(key){
  return state.days[key] || { flowStart: 8 * 60, items: [], logs: [] };
}
// day() creates the day record on first write
export function day(key){
  return state.days[key] || (state.days[key] = { flowStart: 8 * 60, items: [], logs: [] });
}
export function subscribe(fn){ subs.add(fn); return () => subs.delete(fn); }
export function update(fn){
  fn(state);
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }, 150);
  subs.forEach(f => f());
}
